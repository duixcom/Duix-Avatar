"""Compare a local TensorRT engine with the pinned original ONNX on generated inputs."""
import argparse
import json
from pathlib import Path
import platform
import time

import numpy as np

from model_assets import sha256
from original_enhancement import OriginalGFPGAN, verify_model


def synthetic_faces():
    """No reference videos, photos or private oracle files are required."""
    y, x = np.indices((256, 256), dtype=np.uint16)
    yield np.stack((x, y, (x + y) // 2), axis=-1).astype(np.uint8)
    yield np.full((512, 512, 3), 127, dtype=np.uint8)
    yield np.random.default_rng(731).integers(0, 256, (320, 240, 3), dtype=np.uint8)


def compare(expected, actual):
    if expected.shape != actual.shape:
        return {'passed': False, 'error': 'Output shape mismatch'}
    delta = np.abs(expected.astype(np.float64) - actual.astype(np.float64))
    pixels = np.abs((expected * 255).clip(0, 255).astype(np.uint8).astype(np.int16)
                    - (actual * 255).clip(0, 255).astype(np.uint8).astype(np.int16))
    finite = bool(np.isfinite(actual).all())
    close = bool(np.allclose(expected, actual, atol=2e-4, rtol=1e-4))
    return {'finite': finite, 'max_abs': float(delta.max()), 'mean_abs': float(delta.mean()),
            'float_allclose': close, 'uint8_max_abs': int(pixels.max()),
            'passed': finite and close and int(pixels.max()) <= 1}


def verify(onnx_path, engine_path, threads=4):
    import torch
    import tensorrt as trt
    from trt_session import TensorRTSession
    if platform.machine() != 'aarch64' or not torch.cuda.is_available():
        raise RuntimeError('Run TensorRT validation on native ARM64 CUDA')
    verify_model(onnx_path)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    expected_model = OriginalGFPGAN(onnx_path, threads=threads)
    actual_model = OriginalGFPGAN(onnx_path, session=TensorRTSession(engine_path))
    report = {'comparison': 'Pinned original ONNX CPU vs local TensorRT FP32; generated inputs',
              'onnx_sha256': sha256(onnx_path), 'engine_sha256': sha256(engine_path),
              'tensorrt': trt.__version__, 'gpu': torch.cuda.get_device_name(0),
              'criteria': {'float_atol': 2e-4, 'float_rtol': 1e-4, 'uint8_max_abs': 1}, 'cases': []}
    for index, face in enumerate(synthetic_faces()):
        start = time.perf_counter()
        expected = expected_model.forward(face)
        cpu_seconds = time.perf_counter() - start
        start = time.perf_counter()
        actual = actual_model.forward(face)
        item = compare(expected, actual)
        item.update(index=index, input_shape=list(face.shape), cpu_seconds=cpu_seconds,
                    trt_seconds=time.perf_counter() - start)
        report['cases'].append(item)
    report['passed'] = all(row['passed'] for row in report['cases'])
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--onnx', type=Path, required=True)
    parser.add_argument('--engine', type=Path, required=True)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    report = verify(args.onnx, args.engine)
    args.report.parent.mkdir(parents=True, exist_ok=True)
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    print(json.dumps(report, indent=2))
    if not report['passed']:
        raise SystemExit('GFPGAN engine did not match the original ONNX')


if __name__ == '__main__':
    main()
