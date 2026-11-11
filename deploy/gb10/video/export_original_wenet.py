"""Convert official Duix WeNet encoder to portable TorchScript on x86 Python 3.9.

Calls original compiled load_ppg_model / PPGModel / ConformerEncoder. Only the
integer shape mask helper is scripted equivalently to avoid frozen trace sizes.
No service or licensing module is imported.
"""
import argparse
import hashlib
import importlib
import json
import platform
import sys
import time
from pathlib import Path

import torch
import numpy as np

from export_original_dinet import difference, portable_devices
from original_wenet_audio import log_mel


PINNED = {
    'extension': '8fc8b6e88600fb0db81bbf0b78851ff1486687c744f74df8aa3697f976869468',
    'checkpoint': '0f59bf2ebb02c7fa560b44370a656392e8cc8d8214a0d0a99e8fd8edde39c792',
    'config': 'b24fd0f76de243a7235df481113f82dfd42fb76ee4ba7b569e5e959c32326aa0',
}


def dynamic_pad_mask(lengths: torch.Tensor) -> torch.Tensor:
    # Same comparisons/dtype as official make_pad_mask. Shape remains dynamic.
    seq_range = torch.arange(0, torch.max(lengths), dtype=torch.int64, device=lengths.device)
    return seq_range.unsqueeze(0).expand(lengths.size(0), -1) >= lengths.unsqueeze(-1)


def sha(path):
    h = hashlib.sha256()
    with open(path, 'rb') as f:
        for block in iter(lambda: f.read(8 * 1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--code-root', type=Path, required=True)
    p.add_argument('--output', type=Path, required=True)
    p.add_argument('--threads', type=int, default=4)
    a = p.parse_args()
    if sys.version_info[:2] != (3, 9) or platform.machine() != 'x86_64':
        raise RuntimeError('Export original extension on x86_64 CPython 3.9')
    torch.set_num_threads(a.threads)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.manual_seed(20261111)
    root = a.code_root.resolve()
    a.output.mkdir(parents=True, exist_ok=True)
    report = {'python': sys.version, 'torch': torch.__version__,
              'scope': 'Original WeNet PPG encoder only; waveform preprocessing separately verified',
              'provenance': {}, 'validation': []}
    start = time.perf_counter()

    def progress(stage):
        report['stage'] = stage
        report['elapsed_seconds'] = round(time.perf_counter() - start, 3)
        (a.output / 'export-report.json').write_text(json.dumps(report, indent=2))
        print(json.dumps({'stage': stage, 'elapsed_seconds': report['elapsed_seconds']}), flush=True)

    paths = {
        'extension': root / 'wenet/compute_ctc_att_bnf.cpython-39-x86_64-linux-gnu.so',
        'checkpoint': root / 'wenet/examples/aishell/aidata/exp/conformer/wenetmodel.pt',
        'config': root / 'wenet/examples/aishell/aidata/conf/train_conformer_multi_cn.yaml',
    }
    for kind, path in paths.items():
        digest = sha(path)
        if digest != PINNED[kind]:
            raise RuntimeError('Unrecognized official ' + kind + ': ' + digest)
        report['provenance'][kind] = {'path': str(path), 'bytes': path.stat().st_size, 'sha256': digest}
    sys.path.insert(0, str(root))
    original = importlib.import_module('wenet.compute_ctc_att_bnf')
    model = original.load_ppg_model(str(paths['config']), str(paths['checkpoint']), device='cpu')
    model.eval()
    # Original loader merges checkpoint into initialized state. Verify that it
    # did not silently leave ANY encoder parameter/buffer at initialization.
    checkpoint = torch.load(paths['checkpoint'], map_location='cpu', weights_only=True)
    selected = {k: v for k, v in checkpoint.items()
                if 'encoder' in k and 'encoder.global_cmvn' not in k}
    state = model.state_dict()
    missing, unexpected = sorted(set(state) - set(selected)), sorted(set(selected) - set(state))
    mismatched = [k for k in state if k in selected and not torch.equal(state[k], selected[k])]
    report['checkpoint_coverage'] = {
        'model_keys': len(state), 'checkpoint_keys': len(checkpoint),
        'selected_encoder_keys': len(selected), 'missing': missing,
        'unexpected': unexpected, 'value_mismatches': mismatched,
        'excluded_keys': [k for k in checkpoint if k not in selected],
    }
    if missing or unexpected or mismatched:
        progress('FAILED checkpoint coverage')
        raise AssertionError(report['checkpoint_coverage'])
    del checkpoint, selected
    progress('original model loaded; every encoder tensor exactly covered')

    # Distinct durations, odd/even subsampling boundaries and a padded batch.
    specs = [(37, [37]), (101, [101]), (401, [401]), (803, [803]),
             (136, [136, 79])]
    cases = []
    for i, (frames, lengths) in enumerate(specs):
        g = torch.Generator().manual_seed(71 + i)
        feats = torch.randn((len(lengths), frames, 80), generator=g)
        lens = torch.tensor(lengths, dtype=torch.int64)
        with torch.inference_mode():
            expected = model(feats, lens)
        if not torch.isfinite(expected).all():
            raise AssertionError('Original eager output not finite')
        cases.append({'inputs': (feats, lens), 'expected': expected})
    # Also validate the actual log-mel range, including a silence interval;
    # normalized random inputs alone do not exercise the production frontend.
    samples = np.arange(32000, dtype=np.float64)
    waveform = 0.07 * np.sin(2 * np.pi * 220 * samples / 16000)
    waveform += 0.03 * np.sin(2 * np.pi * 719 * samples / 16000)
    waveform[10000:17000] = 0
    waveform = np.concatenate((np.zeros(6400), waveform, np.zeros(6400)))
    mel = log_mel(waveform)
    feats = torch.from_numpy(mel).float().unsqueeze(0)
    lens = torch.tensor([mel.shape[0]], dtype=torch.int64)
    with torch.inference_mode():
        expected = model(feats, lens)
    cases.append({'inputs': (feats, lens), 'expected': expected,
                  'kind': 'original log-mel harmonic waveform with silence'})
    progress('recorded original compiled forward for six feature cases')

    encoder_module = importlib.import_module('wenet.transformer.encoder')
    original_mask = encoder_module.make_pad_mask
    scripted_mask = torch.jit.script(dynamic_pad_mask)
    report['mask_equivalence'] = []
    for _, lengths in specs:
        lens = torch.tensor(lengths, dtype=torch.int64)
        equal = torch.equal(original_mask(lens), scripted_mask(lens))
        report['mask_equivalence'].append({'lengths': lengths, 'equal': equal})
        assert equal
    encoder_module.make_pad_mask = scripted_mask
    report['compatibility_changes'] = [
        'Only make_pad_mask Python int/item shape construction converted to mathematically identical scripted dynamic arange/expand',
        'Traced CPU device constants changed to input tensor device for ARM CUDA portability',
    ]
    try:
        with torch.inference_mode():
            traced = torch.jit.trace(model, cases[2]['inputs'], strict=True, check_trace=False)
            traced = torch.jit.freeze(traced.eval())
        report['relocated_device_constants'] = portable_devices(traced)
        torch.jit.save(traced, str(a.output / 'original-wenet.ts'))
        restored = torch.jit.load(str(a.output / 'original-wenet.ts'), map_location='cpu').eval()
        for case in cases:
            with torch.inference_mode():
                actual = restored(*case['inputs'])
            metrics = difference(case['expected'], actual)
            item = {'input_shapes': [list(t.shape) for t in case['inputs']],
                    'lengths': case['inputs'][1].tolist(), 'output_shape': list(actual.shape),
                    'kind': case.get('kind', 'random'), **metrics}
            # Fused/eager arithmetic reorder may differ by a few ulps.
            accepted = bool(torch.allclose(case['expected'], actual, atol=2e-5, rtol=1e-4))
            item['allclose_atol_2e-5_rtol_1e-4'] = accepted
            report['validation'].append(item)
            if not accepted:
                progress('FAILED serialized graph vs original eager')
                raise AssertionError(item)
        torch.save(cases, a.output / 'original-wenet-verification.pt')
        report['artifact'] = {'path': str(a.output / 'original-wenet.ts'),
                              'sha256': sha(a.output / 'original-wenet.ts')}
        (a.output / 'original-wenet.graph.txt').write_text(str(restored.graph))
        progress('PASS original WeNet exported and serialized graph validated')
    finally:
        encoder_module.make_pad_mask = original_mask


if __name__ == '__main__':
    main()
