"""Execute the exported original DINet on native GB10 and compare CPU oracle."""
import argparse
import hashlib
import json
import platform
import time
from pathlib import Path

import torch


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', type=Path, required=True)
    p.add_argument('--report', type=Path, required=True)
    args = p.parse_args()
    if platform.machine() != 'aarch64' or not torch.cuda.is_available():
        raise RuntimeError('This acceptance check requires native ARM64 CUDA')
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    root = args.root
    model_path = root / 'original-dinet.ts.pt'
    model = torch.jit.load(str(model_path), map_location='cuda').eval()
    vectors = torch.load(root / 'validation-vectors.pt', map_location='cpu', weights_only=True)
    report = {
        'machine': platform.machine(), 'torch': torch.__version__,
        'cuda': torch.version.cuda, 'gpu': torch.cuda.get_device_name(0),
        'capability': list(torch.cuda.get_device_capability(0)),
        'model_sha256': hashlib.sha256(model_path.read_bytes()).hexdigest(),
        'tf32': False, 'cases': [],
        'scope': 'Original DINet tensor inference only; end-to-end video is separate',
        'criteria': {'float_atol': 0.0001, 'float_rtol': 0.001, 'uint8_max_abs': 1},
    }
    success = True
    with torch.inference_mode():
        for case in vectors:
            inputs = tuple(t.to('cuda') for t in case['inputs'])
            model(*inputs)
            torch.cuda.synchronize()
            start = time.perf_counter()
            actual = model(*inputs)
            torch.cuda.synchronize()
            seconds = time.perf_counter() - start
            actual = actual.cpu()
            expected = case['expected']
            delta = (actual - expected).abs()
            pixels = ((actual * 255).to(torch.uint8).to(torch.int16)
                      - (expected * 255).to(torch.uint8).to(torch.int16)).abs()
            close = torch.allclose(actual, expected, atol=0.0001, rtol=0.001)
            finite = bool(torch.isfinite(actual).all())
            passed = finite and close and int(pixels.max()) <= 1
            item = {'seed': case['seed'], 'batch': inputs[0].shape[0],
                    'max_abs': float(delta.max()), 'mean_abs': float(delta.mean()),
                    'rmse': float(delta.square().mean().sqrt()),
                    'uint8_max_abs': int(pixels.max()), 'uint8_mean_abs': float(pixels.float().mean()),
                    'allclose': close, 'finite': finite, 'passed': passed,
                    'warm_forward_seconds': seconds}
            report['cases'].append(item)
            print(json.dumps(item), flush=True)
            success = success and passed
    report['passed'] = success
    args.report.write_text(json.dumps(report, indent=2) + '\n')
    if not success:
        raise RuntimeError('GB10 output did not meet the declared CPU oracle tolerance')


if __name__ == '__main__':
    main()
