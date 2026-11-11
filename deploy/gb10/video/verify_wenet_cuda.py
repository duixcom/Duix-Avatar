"""Verify the exported original WeNet on a native target (ARM64 / CUDA)."""
import argparse
import json
import platform
import time
from pathlib import Path

import torch


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--model', type=Path, required=True)
    p.add_argument('--verification', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--device', default='cuda')
    p.add_argument('--atol', type=float, default=1e-4)
    p.add_argument('--rtol', type=float, default=1e-4)
    args = p.parse_args()
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    model = torch.jit.load(str(args.model), map_location=args.device).eval()
    cases = torch.load(args.verification, map_location='cpu', weights_only=True)
    report = {'machine': platform.machine(), 'torch': torch.__version__,
              'cuda': torch.version.cuda, 'device': args.device,
              'gpu': torch.cuda.get_device_name() if args.device.startswith('cuda') else None,
              'comparison': 'native serialized graph vs original x86 compiled eager output',
              'tolerance': {'atol': args.atol, 'rtol': args.rtol}, 'cases': []}
    # CUDA vs CPU float32 changes reduction order. Use a small explicit 1e-4
    # absolute / relative tolerance, without precision reduction or reweighting.
    for case in cases:
        inputs = tuple(x.to(args.device) for x in case['inputs'])
        if args.device.startswith('cuda'):
            torch.cuda.synchronize()
        start = time.perf_counter()
        with torch.inference_mode():
            actual = model(*inputs).cpu()
        elapsed = time.perf_counter() - start
        expected = case['expected']
        delta = (actual - expected).abs()
        item = {'kind': case.get('kind', 'random'),
                'input_shapes': [list(x.shape) for x in inputs],
                'lengths': inputs[1].cpu().tolist(), 'shape': list(actual.shape),
                'max_abs': float(delta.max()), 'mean_abs': float(delta.mean()),
                'rmse': float(delta.square().mean().sqrt()),
                'finite': bool(torch.isfinite(actual).all()),
                'allclose': bool(torch.allclose(actual, expected, atol=args.atol, rtol=args.rtol)),
                'seconds': round(elapsed, 6)}
        report['cases'].append(item)
        print(json.dumps(item), flush=True)
    report['pass'] = all(x['finite'] and x['allclose'] for x in report['cases'])
    args.output.write_text(json.dumps(report, indent=2))
    if not report['pass']:
        raise SystemExit('FAILED native WeNet comparison; see ' + str(args.output))


if __name__ == '__main__':
    main()
