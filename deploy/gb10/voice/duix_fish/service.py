import asyncio
import io
import logging
import queue
import tempfile
import threading
import uuid
from pathlib import Path
from typing import Literal

import numpy as np
import soundfile as sf
from fastapi import FastAPI, HTTPException
from fastapi.responses import Response, StreamingResponse
from pydantic import AliasChoices, BaseModel, Field, field_validator

from .original_voice_preprocess import preprocess_reference_audio
from .reference_download import ReferenceDownloader, resolve_reference

logger = logging.getLogger(__name__)


class PreprocessRequest(BaseModel):
    reference_audio: str = Field(min_length=1)
    lang: str = "zh"
    format: str = "wav"


class InvokeRequest(BaseModel):
    text: str = Field(min_length=1, max_length=20000)
    reference_audio: str = Field(min_length=1)
    reference_text: str = Field(min_length=1)
    format: Literal["wav", "mp3", "pcm"] = "wav"
    streaming: bool = False
    top_p: float = Field(default=0.7, ge=0.1, le=1.0, validation_alias=AliasChoices("topP", "top_p"))
    # Original Fish uses zero to generate until its model context/end token.
    max_new_tokens: int = Field(default=1024, ge=0, le=4096)
    chunk_length: int = Field(default=200, ge=100, le=300)
    repetition_penalty: float = Field(default=1.2, ge=0.9, le=2.0)
    temperature: float = Field(default=0.7, ge=0.1, le=1.0)
    seed: int | None = None
    is_norm: int | None = None
    normalize: bool = True
    use_memory_cache: Literal["on", "off"] = "off"

    @field_validator("text", "reference_text")
    @classmethod
    def nonblank(cls, value):
        value = value.strip()
        if not value:
            raise ValueError("Text cannot be blank")
        return value


def resolve_media(root: Path, value: str) -> Path:
    if value.startswith(("http://", "https://")):
        raise ValueError("Upload audio into the shared media directory before using this local service")
    candidate = Path(value)
    if not candidate.is_absolute():
        candidate = root / candidate
    candidate = candidate.resolve()
    if not candidate.is_relative_to(root):
        raise ValueError("Audio path is outside the shared media directory")
    if not candidate.is_file():
        raise ValueError("Reference audio file does not exist")
    return candidate


def create_app(media_root, backend, transcribe, rnnoise_binary, reference_url_allow_networks=()) -> FastAPI:
    root = Path(media_root).resolve()
    root.mkdir(parents=True, exist_ok=True)
    sessions = root / "fish-references"
    sessions.mkdir(exist_ok=True)
    inference_lock = threading.Lock()
    asr_lock = threading.Lock()
    downloader = ReferenceDownloader(allowed_networks=reference_url_allow_networks)
    app = FastAPI(title="Duix Fish Speech 1.5 ARM64 adapter", version="0.2.0")

    @app.get("/v1/health")
    @app.post("/v1/health")
    def health():
        asr_name = getattr(transcribe, "model_name", "FunASR original Paraformer")
        return {"status": "ok", "model": "fish-speech-1.5", "ready": True,
                "asr": asr_name, "denoise": "original RNNoise", "streaming": True}

    @app.post("/v1/preprocess_and_tran")
    def preprocess(request: PreprocessRequest):
        try:
            session = sessions / uuid.uuid4().hex
            session.mkdir()
            source = resolve_reference(root, request.reference_audio, session, downloader, resolve_media)
            paths = preprocess_reference_audio(source, session, rnnoise_binary)
            valid = []
            with asr_lock:
                for path in paths:
                    text = transcribe(path, request.lang).strip()
                    if text:
                        valid.append((path, text))
            if not valid:
                raise ValueError("ASR returned no transcript; provide a clear spoken recording")
            return {"code": 0, "msg": "success",
                    "reference_audio_text": "|||".join(text for _, text in valid),
                    "asr_format_audio_url": "|||".join(str(path) for path, _ in valid)}
        except Exception as exc:
            logger.exception("Reference preprocessing failed")
            return {"code": -1, "msg": str(exc)}

    @app.post("/v1/invoke")
    def invoke(request: InvokeRequest):
        if request.streaming and request.format != 'wav':
            raise HTTPException(400, 'Streaming only supports WAV format')
        paths = request.reference_audio.split("|||")
        texts = request.reference_text.split("|||")
        if len(paths) != len(texts) or any(not text.strip() for text in texts):
            raise HTTPException(400, "Reference audio and transcript counts must match")
        try:
            references = []
            for path, text in zip(paths, texts):
                with tempfile.TemporaryDirectory(prefix='reference-download-', dir=sessions) as session:
                    reference = resolve_reference(root, path, session, downloader, resolve_media)
                    references.append((reference.read_bytes(), text))
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc
        if request.streaming:
            async def generate():
                messages = queue.Queue(maxsize=4)
                disconnected = threading.Event()

                def publish(kind, value=None):
                    while not disconnected.is_set():
                        try:
                            messages.put((kind, value), timeout=0.1)
                            return
                        except queue.Full:
                            continue

                def produce():
                    # The producer owns model state independently of the HTTP
                    # iterator. A disconnected consumer stops receiving data,
                    # while this thread finishes inference and releases the
                    # lock before the next request can change the seed/cache.
                    with inference_lock:
                        try:
                            for chunk in backend.stream(request, references):
                                publish('chunk', chunk)
                        except Exception as exc:
                            logger.exception('Fish Speech streaming failed')
                            publish('error', exc)
                        finally:
                            publish('end')

                threading.Thread(target=produce, name='fish-stream-producer', daemon=True).start()
                try:
                    while True:
                        try:
                            kind, value = await asyncio.to_thread(messages.get, True, 0.25)
                        except queue.Empty:
                            continue
                        if kind == 'end':
                            break
                        if kind == 'error':
                            raise value
                        yield value
                finally:
                    disconnected.set()
            return StreamingResponse(generate(), media_type='audio/wav',
                headers={'Content-Disposition': 'attachment; filename=audio.wav'})
        try:
            with inference_lock:
                sample_rate, audio = backend.synthesize(request, references)
            audio = np.asarray(audio, dtype=np.float32)
            if not audio.size or not np.isfinite(audio).all():
                raise RuntimeError("Fish Speech produced no valid audio")
            if request.format == 'pcm':
                body = (audio * 32768).astype('<i2').tobytes()
                content_type = 'application/octet-stream'
            else:
                buffer = io.BytesIO()
                sf.write(buffer, audio, sample_rate, format=request.format)
                body = buffer.getvalue()
                content_type = 'audio/wav' if request.format == 'wav' else 'audio/mpeg'
            return Response(body, media_type=content_type,
                            headers={'Content-Disposition': 'attachment; filename=audio.' + request.format})
        except Exception as exc:
            logger.exception("Fish Speech synthesis failed")
            raise HTTPException(500, str(exc)) from exc

    return app
