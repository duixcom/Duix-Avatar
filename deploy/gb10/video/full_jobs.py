"""Persistent original-protocol Duix jobs, with bounded single-GPU scheduling."""

import copy
import json
import logging
import os
from pathlib import Path
import queue
import re
import threading
import time
import uuid

from api_compat import parse_submit, response, submit_success, query_success


CODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,127}\Z")


class JobManager:
    def __init__(self, root, runner):
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.temp = self.root / "temp"
        self.temp.mkdir(exist_ok=True)
        self.state_dir = self.root / "jobs"
        self.state_dir.mkdir(exist_ok=True)
        if self.temp.is_symlink() or self.state_dir.is_symlink():
            raise ValueError("Data directories must not be symbolic links")
        self.runner = runner
        self.lock = threading.RLock()
        self.jobs = {}
        self.queue = queue.Queue()
        self.closed = False
        self.persistence_error = None
        self._pending_persistence = set()
        for state_path in self.state_dir.glob("*.json"):
            if state_path.is_symlink() or not CODE.fullmatch(state_path.stem):
                continue
            try:
                job = json.loads(state_path.read_text(encoding="utf-8"))
                if job.get("code") != state_path.stem or not isinstance(job.get("data"), dict):
                    raise ValueError("Invalid saved job")
                self.jobs[job["code"]] = job
                if job["data"].get("status") == 1:
                    job["data"].update(status=3, result="", msg="Service restarted before this job completed")
                    self._save_state(job)
            except (OSError, ValueError, TypeError):
                logging.exception("Cannot restore job %s", state_path.name)
        self.worker = threading.Thread(target=self._work, name="duix-original-worker", daemon=True)
        self.worker.start()

    def _persist(self, job):
        destination = self.state_dir / (job["code"] + ".json")
        temporary = self.state_dir / ("." + uuid.uuid4().hex + ".tmp")
        try:
            with temporary.open("x", encoding="utf-8") as stream:
                json.dump(job, stream, ensure_ascii=False, allow_nan=False)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, destination)
        finally:
            try:
                temporary.unlink(missing_ok=True)
            except OSError:
                # A stale temporary file must not hide a successful atomic
                # replacement, or mask the original write failure.
                logging.exception("Cannot remove temporary job state %s", temporary.name)

    def _save_state(self, job):
        """Record storage failure without terminating the GPU worker.

        Failed submissions are not retained for retry: only already accepted
        jobs enter the pending set. Their latest in-memory state is retried on
        later job boundaries, including completed/failed terminal states.
        """
        try:
            self._persist(job)
        except Exception as error:
            self.persistence_error = "%s: %s" % (type(error).__name__, error)
            if job["code"] in self.jobs:
                self._pending_persistence.add(job["code"])
            logging.exception("Cannot persist job %s", job["code"])
            return False
        self._pending_persistence.discard(job["code"])
        if not self._pending_persistence:
            self.persistence_error = None
        return True

    def _retry_persistence(self):
        with self.lock:
            for code in tuple(self._pending_persistence):
                self._save_state(self.jobs[code])

    def resolve_input(self, value):
        if not isinstance(value, str) or not value or "\x00" in value or "\\" in value:
            raise ValueError("Input must be a local path inside the temp directory")
        path = Path(value)
        if ".." in path.parts or ":" in value:
            raise ValueError("Parent traversal and URL inputs are not allowed")
        candidate = path if path.is_absolute() else self.temp / path
        resolved = candidate.resolve(strict=True)
        if not resolved.is_relative_to(self.temp) or not resolved.is_file():
            raise ValueError("Input file must stay inside the temp directory")
        return resolved

    def submit(self, payload):
        try:
            request = parse_submit(payload)
            code = request.code
            if not isinstance(code, str) or not CODE.fullmatch(code):
                raise ValueError("Invalid code: use 1-128 letters, digits, underscores or hyphens")
            video = self.resolve_input(request.video_url)
            audio = self.resolve_input(request.audio_url)
            if video == audio:
                raise ValueError("Video and audio inputs must be separate files")
            output = self.temp / (code + ".mp4")
            with self.lock:
                if self.closed:
                    raise ValueError("Service is shutting down")
                if code in self.jobs or (self.state_dir / (code + ".json")).exists():
                    raise ValueError("Job code already exists; choose a new code")
                if output.exists() or output.is_symlink():
                    raise ValueError("Output file already exists; choose a new code")
                job = {
                    "code": code,
                    "video": str(video),
                    "audio": str(audio),
                    "created_at": time.time(),
                    "options": {name: getattr(request, name) for name in
                                ("pn", "chaofen", "watermark_switch", "digital_auth")},
                    "data": {"status": 1, "result": "", "progress": 0, "msg": "Queued",
                             "cost": 0, "video_duration": 0, "width": 0, "height": 0},
                }
                if not self._save_state(job):
                    return response(9999, msg="Cannot save job state; submission was not queued")
                self.jobs[code] = job
                self.queue.put(code)
            return submit_success()
        except (ValueError, OSError, TypeError) as error:
            return response(10002, msg=str(error))

    def query(self, code):
        with self.lock:
            job = self.jobs.get(code) if isinstance(code, str) else None
            if job is None:
                return response(10004)
            return query_success(code, **copy.deepcopy(job["data"]))

    def result_file(self, code):
        result = self.query(code)
        data = result.get("data")
        if not data or data["status"] != 2:
            raise FileNotFoundError("Completed result not found")
        return self.resolve_input(data["result"])

    def _work(self):
        while True:
            code = self.queue.get()
            if code is None:
                self.queue.task_done()
                return
            started = time.monotonic()
            output = self.temp / (code + ".mp4")
            output_owned = False

            def progress(value, message="Generating"):
                with self.lock:
                    job = self.jobs[code]
                    value, message = min(99, max(0, int(value))), str(message)
                    unchanged = job["data"]["progress"] == value and job["data"]["msg"] == message
                    job["data"].update(progress=value, msg=message,
                                       cost=round(time.monotonic() - started, 3))
                    if not unchanged:
                        self._save_state(job)

            try:
                self._retry_persistence()
                progress(1, "Starting")
                with self.lock:
                    job = self.jobs[code]
                    video = self.resolve_input(job["video"])
                    audio = self.resolve_input(job["audio"])
                if output.exists() or output.is_symlink():
                    raise ValueError("Output file already exists")
                output_owned = True
                metadata = self.runner(video, audio, output, progress, options=job.get("options", {"pn": 1}))
                if output.is_symlink() or not output.is_file() or output.stat().st_size == 0:
                    raise RuntimeError("Renderer did not produce a video file")
                with self.lock:
                    self.jobs[code]["data"].update(
                        status=2, result=output.name, progress=100, msg="Completed",
                        cost=round(time.monotonic() - started, 3),
                        video_duration=float(metadata["duration"]),
                        width=int(metadata["width"]), height=int(metadata["height"]),
                    )
                    self._save_state(self.jobs[code])
            except Exception as error:
                logging.exception("Video job %s failed", code)
                if output_owned:
                    try:
                        output.unlink(missing_ok=True)
                    except OSError:
                        logging.exception("Cannot remove failed video output for job %s", code)
                with self.lock:
                    self.jobs[code]["data"].update(
                        status=3, result="", msg=str(error) or type(error).__name__,
                        cost=round(time.monotonic() - started, 3),
                    )
                    self._save_state(self.jobs[code])
            finally:
                self._retry_persistence()
                self.queue.task_done()

    def close(self):
        with self.lock:
            if self.closed:
                return
            self.closed = True
            self.queue.put(None)
        self.worker.join(timeout=30)
