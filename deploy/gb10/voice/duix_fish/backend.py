"""Load the upstream 1.5 models without replacing them with newer model families."""

import queue
import sys
import threading
from pathlib import Path


class FishBackend:
    def __init__(self, source_root, checkpoint_root, device="cuda", compile_model=False):
        source_root = Path(source_root).resolve()
        checkpoint_root = Path(checkpoint_root).resolve()
        required = ["model.pth", "config.json", "tokenizer.tiktoken",
                    "firefly-gan-vq-fsq-8x1024-21hz-generator.pth"]
        missing = [name for name in required if not (checkpoint_root / name).is_file()]
        if missing:
            raise RuntimeError(f"Fish Speech 1.5 checkpoint is incomplete: {', '.join(missing)}")
        sys.path.insert(0, str(source_root))
        import torch
        from lightning_utilities.core.rank_zero import rank_zero_only
        if not hasattr(rank_zero_only, "rank"):
            rank_zero_only.rank = 0
        from tools.inference_engine import TTSInferenceEngine
        from tools.llama.generate import WrappedGenerateResponse, generate_long, load_model
        from tools.vqgan.inference import load_model as load_decoder

        if device.startswith("cuda") and not torch.cuda.is_available():
            raise RuntimeError("CUDA is unavailable; refusing silent CPU fallback")
        precision = torch.bfloat16
        # Load synchronously so a checkpoint/dependency error fails startup, instead
        # of leaving the original background launcher's Event waiting forever.
        model, decode_one_token = load_model(checkpoint_root, device, precision, compile=compile_model)
        with torch.device(device):
            model.setup_caches(max_batch_size=1, max_seq_len=model.config.max_seq_len,
                               dtype=next(model.parameters()).dtype)
        input_queue = queue.Queue()

        def worker():
            while True:
                item = input_queue.get()
                if item is None:
                    return
                try:
                    for chunk in generate_long(model=model, decode_one_token=decode_one_token, **item.request):
                        item.response_queue.put(WrappedGenerateResponse(status="success", response=chunk))
                except Exception as exc:
                    item.response_queue.put(WrappedGenerateResponse(status="error", response=exc))

        threading.Thread(target=worker, name="fish-llama", daemon=True).start()
        decoder = load_decoder("firefly_gan_vq", str(checkpoint_root / required[-1]), device)
        self.engine = TTSInferenceEngine(llama_queue=input_queue, decoder_model=decoder,
                                         precision=precision, compile=compile_model)

    def request(self, request, references, streaming=False):
        from tools.schema import ServeReferenceAudio, ServeTTSRequest
        text = request.text
        if request.is_norm == 0:
            from tools.text_norm.front_end.tts_front_end import TTSFrontEnd
            if not hasattr(self, 'normalizer'):
                self.normalizer = TTSFrontEnd('CN_EN')
            text = ','.join(part for part in self.normalizer.call(text) if part != '')
        return ServeTTSRequest(
            text=text, references=[ServeReferenceAudio(audio=audio, text=transcript)
                                   for audio, transcript in references],
            format=request.format, streaming=streaming, seed=request.seed,
            max_new_tokens=request.max_new_tokens, chunk_length=request.chunk_length,
            top_p=request.top_p, repetition_penalty=request.repetition_penalty,
            temperature=request.temperature, normalize=request.normalize,
            use_memory_cache=request.use_memory_cache,
        )

    def synthesize(self, request, references):
        for result in self.engine.inference(self.request(request, references)):
            if result.code == 'error':
                raise RuntimeError(str(result.error))
            if result.code == 'final' and result.audio is not None:
                return result.audio
        raise RuntimeError('Fish Speech returned no final audio')

    def stream(self, request, references):
        import numpy as np
        count = 0
        for result in self.engine.inference(self.request(request, references, streaming=True)):
            if result.code == 'error':
                raise RuntimeError(str(result.error))
            if result.code == 'header' and result.audio is not None:
                yield result.audio[1]
            elif result.code == 'segment' and result.audio is not None:
                audio = np.asarray(result.audio[1])
                if not np.isfinite(audio).all():
                    raise RuntimeError('Fish Speech returned non-finite samples')
                count += 1
                yield (audio * 32768).astype(np.int16).tobytes()
            elif result.code == 'final':
                if not count:
                    raise RuntimeError('Fish Speech returned no streaming audio')
                return
        raise RuntimeError('Fish Speech stream ended without a final result')
