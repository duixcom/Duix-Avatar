"""Run inside the native video image with a writable model preparation directory."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'video'))
from build_gfpgan import main

if __name__ == '__main__':
    main()
