"""Download, install and verify original video assets outside the Git tree."""
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'video'))
from model_assets import main

if __name__ == '__main__':
    main()
