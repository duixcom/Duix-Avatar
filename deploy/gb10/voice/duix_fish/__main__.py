import argparse
import logging
import os
from pathlib import Path

from .backend import FishBackend
from .original_funasr_client import OriginalFunASR
from .service import create_app


def main():
    parser = argparse.ArgumentParser(description="Duix-compatible Fish Speech 1.5 service")
    parser.add_argument("--source-root", default=str(Path(__file__).resolve().parents[1] / "fish-speech"))
    parser.add_argument("--checkpoint-root", required=True)
    parser.add_argument("--media-root", required=True)
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=18180)
    parser.add_argument("--device", default="cuda")
    parser.add_argument("--asr-url", default="ws://asr:10095")
    parser.add_argument("--rnnoise-binary", default="/usr/local/bin/rnnoise_new")
    parser.add_argument("--reference-url-allow-network", action="append",
                        default=[net.strip() for net in os.environ.get('DUIX_REFERENCE_URL_ALLOW_NETWORKS', '').split(',') if net.strip()],
                        help="Explicit trusted reference-server IP/CIDR; repeat for additional LAN servers")
    parser.add_argument("--compile", action="store_true")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO)
    engine = FishBackend(args.source_root, args.checkpoint_root, args.device, args.compile)
    asr = OriginalFunASR(args.asr_url)
    def transcribe(path, language):
        return asr.transcribe(path)
    transcribe.model_name = "original Paraformer + FSMN VAD + CT punctuation + WFST + ITN"
    app = create_app(args.media_root, engine, transcribe, args.rnnoise_binary,
                     reference_url_allow_networks=args.reference_url_allow_network)
    import uvicorn
    uvicorn.run(app, host=args.host, port=args.port, workers=1)


if __name__ == "__main__":
    main()
