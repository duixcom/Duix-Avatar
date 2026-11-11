"""Common Duix HTTP handler; full_service supplies model health."""
from http.server import BaseHTTPRequestHandler
import json
import logging
import os
import re
import shutil
from urllib.parse import parse_qs, unquote, urlsplit

class Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _json(self, payload, status=200):
        body = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        if urlsplit(self.path).path != "/easy/submit":
            self.close_connection = True
            self._json({"code": 10003, "msg": "Not found", "data": None}, 404)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if not 0 < length <= 65536 or self.headers.get("Transfer-Encoding"):
                raise ValueError("JSON request must contain 1-65536 bytes")
            body = self.rfile.read(length)
            if len(body) != length:
                raise ValueError("Incomplete request")
            payload = json.loads(body)
        except (ValueError, UnicodeError) as error:
            self.close_connection = True
            self._json({"code": 10002, "msg": str(error), "data": None}, 400)
            return
        self._json(self.server.manager.submit(payload))

    def do_GET(self):
        parsed = urlsplit(self.path)
        if parsed.path in ("/health", "/healthz"):
            self._json({
                "status": "ok", "engine": "Duix original models",
                "cuda_required": True,
                "model_loaded": bool(getattr(self.server.manager.runner, "loaded", False)),
                "max_duration": getattr(self.server.manager.runner, "max_duration", None),
            })
        elif parsed.path == "/easy/query":
            code = parse_qs(parsed.query).get("code", [""])[0]
            self._json(self.server.manager.query(code))
        elif parsed.path.startswith("/results/"):
            name = unquote(parsed.path[len("/results/"):])
            match = re.fullmatch(r"([A-Za-z0-9][A-Za-z0-9_-]{0,127})\.mp4", name)
            try:
                if not match:
                    raise FileNotFoundError()
                result = self.server.manager.result_file(match.group(1))
                with result.open("rb") as stream:
                    self.send_response(200)
                    self.send_header("Content-Type", "video/mp4")
                    self.send_header("Content-Length", str(os.fstat(stream.fileno()).st_size))
                    self.send_header("Content-Disposition", 'inline; filename="' + name + '"')
                    self.send_header("X-Content-Type-Options", "nosniff")
                    self.end_headers()
                    shutil.copyfileobj(stream, self.wfile)
            except (FileNotFoundError, ValueError):
                self._json({"code": 10003, "msg": "Result not found", "data": None}, 404)
        else:
            self._json({"code": 10003, "msg": "Not found", "data": None}, 404)

    def log_message(self, message, *args):
        logging.info("%s %s", self.address_string(), message % args)
