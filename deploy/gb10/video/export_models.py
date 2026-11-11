"""Run the original-network x86 exporters and write a local artifact manifest."""
import argparse
from pathlib import Path
import subprocess
import sys

from model_assets import finalize_exports, install_raw


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--code-root', type=Path, required=True)
    parser.add_argument('--model-root', type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parent
    install_raw(args.code_root, args.model_root)
    subprocess.run([sys.executable, str(root / 'export_original_dinet.py'),
                    '--code-root', str(args.code_root), '--checkpoint',
                    str(args.code_root / 'landmark2face_wy/checkpoints/anylang/dinet_v1_20240131.pth'),
                    '--output', str(args.model_root / 'export-fp32')], check=True)
    subprocess.run([sys.executable, str(root / 'export_original_wenet.py'),
                    '--code-root', str(args.code_root),
                    '--output', str(args.model_root / 'export-wenet')], check=True)
    finalize_exports(args.model_root)


if __name__ == '__main__':
    main()
