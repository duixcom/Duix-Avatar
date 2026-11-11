"""Build and publish an original GFPGAN FP32 engine only after numerical validation."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import tempfile

from model_assets import atomic_json, sha256


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--model-root', type=Path, required=True)
    parser.add_argument('--trtexec', default='/opt/tensorrt/bin/trtexec')
    args = parser.parse_args()
    from original_enhancement import verify_model
    from gfpgan_validation import verify
    root = args.model_root.resolve()
    onnx_path = root / 'models/pretrain_models/face_lib/face_restore/gfpgan/GFPGANv1.4.onnx'
    verify_model(onnx_path)
    manifest_path = root / 'full-model-manifest.json'
    manifest = json.loads(manifest_path.read_text())
    with tempfile.TemporaryDirectory(prefix='.gfpgan-build-', dir=root) as directory:
        engine = Path(directory) / 'gfpgan.engine'
        subprocess.run([args.trtexec, '--onnx=' + str(onnx_path), '--saveEngine=' + str(engine),
                        '--noTF32', '--memPoolSize=workspace:2048', '--builderOptimizationLevel=3',
                        '--maxAuxStreams=0', '--skipInference'], check=True)
        report = verify(onnx_path, engine)
        atomic_json(root / 'gfpgan-build-validation.json', report)
        if not report['passed'] or report['engine_sha256'] != sha256(engine):
            raise RuntimeError('Engine not installed: original ONNX differential check failed')
        relative = 'models/gfpgan-gb10-fp32.engine'
        record = {'path': relative, 'sha256': report['engine_sha256'], 'bytes': engine.stat().st_size,
                  'source_sha256': report['onnx_sha256'], 'precision': 'FP32, TF32 disabled'}
        manifest['files'] = [row for row in manifest['files'] if row['path'] != relative] + [record]
        os.replace(engine, root / relative)
        atomic_json(manifest_path, manifest)
    print('Original GFPGAN engine validated and installed; SHA256:', record['sha256'])


if __name__ == '__main__':
    main()
