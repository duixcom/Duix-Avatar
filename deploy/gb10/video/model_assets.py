"""Prepare pinned original assets without committing models or extracted vendor code."""
import argparse
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import urllib.parse
import urllib.request

HERE = Path(__file__).resolve().parent
DINET_CHECKPOINT = '9c4568b1f1f2890b4a92edc3f9457af63f908065961233af2125d060cb56fd9e'
WENET_CHECKPOINT = '0f59bf2ebb02c7fa560b44370a656392e8cc8d8214a0d0a99e8fd8edde39c792'


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for chunk in iter(lambda: stream.read(8 * 1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()


def atomic_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + '.tmp')
    temporary.write_text(json.dumps(value, indent=2) + '\n')
    os.replace(temporary, path)


def sources():
    return json.loads((HERE / 'model-sources.json').read_text())


def verify_file(path, record):
    path = Path(path)
    if record.get('bytes') is not None and path.stat().st_size != record['bytes']:
        raise ValueError('Original asset size mismatch: ' + path.name)
    if sha256(path) != record['sha256']:
        raise ValueError('Original asset checksum mismatch: ' + path.name)


def extract_code(archive_path, target):
    """Extract regular code files only; never execute a registry image or follow links."""
    target = Path(target)
    with tarfile.open(archive_path, 'r:gz') as archive:
        for item in archive:
            path = PurePosixPath(item.name)
            if path.is_absolute() or '..' in path.parts:
                raise ValueError('Unsafe path in source layer')
            if not item.isfile() or not path.parts or path.parts[0] != 'code':
                continue
            destination = target.joinpath(*path.parts[1:])
            if not destination.resolve().is_relative_to(target.resolve()):
                raise ValueError('Source extraction escapes its destination')
            destination.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(item) as source, destination.open('wb') as output:
                shutil.copyfileobj(source, output)


def download(cache_dir, code_root):
    spec = sources()
    cache_dir, code_root = Path(cache_dir), Path(code_root)
    cache_dir.mkdir(parents=True, exist_ok=True)
    archive = cache_dir / (spec['layer_sha256'] + '.tar.gz')
    record = {'sha256': spec['layer_sha256'], 'bytes': spec['layer_bytes']}
    if archive.exists():
        verify_file(archive, record)
    else:
        token_url = 'https://auth.docker.io/token?' + urllib.parse.urlencode({
            'service': 'registry.docker.io', 'scope': 'repository:%s:pull' % spec['repository']})
        with urllib.request.urlopen(token_url, timeout=40) as response:
            token = json.load(response)['token']
        url = 'https://registry-1.docker.io/v2/%s/blobs/sha256:%s' % (spec['repository'], spec['layer_sha256'])
        request = urllib.request.Request(url, headers={'Authorization': 'Bearer ' + token})
        partial = archive.with_suffix('.part')
        count = 0
        with urllib.request.urlopen(request, timeout=90) as response, partial.open('wb') as output:
            for chunk in iter(lambda: response.read(8 * 1024 * 1024), b''):
                count += len(chunk)
                if count > spec['layer_bytes']:
                    raise ValueError('Source layer exceeds pinned size')
                output.write(chunk)
        verify_file(partial, record)
        os.replace(partial, archive)
    if code_root.exists() and any(code_root.iterdir()):
        raise FileExistsError('Use a new code-root directory for the pinned source extraction')
    code_root.mkdir(parents=True, exist_ok=True)
    extract_code(archive, code_root)
    atomic_json(code_root / 'source-layer.json', record)


def install_raw(code_root, model_root):
    code_root, model_root = Path(code_root), Path(model_root)
    spec = sources()
    # Verify all inputs before writing any runtime destination.
    for record in spec['files']:
        verify_file(code_root / record['source'], record)
    for record in spec['files']:
        target = model_root / record['path']
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(code_root / record['source'], target)
    extra = [{'path': row['path'], 'bytes': row['bytes'], 'sha256': row['sha256']}
             for row in spec['files'] if row['path'].startswith('models/')]
    manifest = model_root / 'full-model-manifest.json'
    # Preserve a validated engine when reinstalling unchanged original ONNX files.
    if manifest.exists():
        for row in json.loads(manifest.read_text())['files']:
            if row['path'] == 'models/gfpgan-gb10-fp32.engine':
                verify_file(model_root / row['path'], row)
                extra.append(row)
    atomic_json(manifest, {'files': extra})


def finalize_exports(model_root):
    """Record locally serialized graphs only after their original-network comparisons pass."""
    root = Path(model_root)
    dinet = json.loads((root / 'export-fp32/export-report.json').read_text())
    wenet = json.loads((root / 'export-wenet/export-report.json').read_text())
    if dinet.get('completed') is not True or dinet.get('strict_state_dict_load') is not True:
        raise ValueError('Original DINet export has not completed strict validation')
    if dinet.get('metadata_weights_only_reload') is not True:
        raise ValueError('DINet metadata validation is missing')
    if dinet['provenance']['checkpoint']['sha256'] != DINET_CHECKPOINT:
        raise ValueError('Unexpected original DINet checkpoint')
    for key in ('eager_extension_vs_bytecode', 'eager_extension_vs_saved_torchscript'):
        rows = dinet.get(key, [])
        if len(rows) < 3 or not all(row.get('allclose_atol_1e-6_rtol_1e-5') is True for row in rows):
            raise ValueError('DINet comparison failed: ' + key)
    if wenet['provenance']['checkpoint']['sha256'] != WENET_CHECKPOINT:
        raise ValueError('Unexpected original WeNet checkpoint')
    coverage = wenet.get('checkpoint_coverage', {})
    if not coverage or any(coverage.get(key, [True]) for key in ('missing', 'unexpected', 'value_mismatches')):
        raise ValueError('WeNet checkpoint coverage is incomplete')
    rows = wenet.get('validation', [])
    if len(rows) < 6 or not all(row.get('allclose_atol_2e-5_rtol_1e-4') is True for row in rows):
        raise ValueError('Original WeNet graph comparison failed')
    verify_file(root / 'export-fp32/original-dinet.ts.pt', dinet['export'])
    verify_file(root / 'export-wenet/original-wenet.ts', wenet['artifact'])
    paths = ['export-fp32/original-dinet.ts.pt', 'export-fp32/original-metadata.pt',
             'export-wenet/original-wenet.ts']
    records = [{'path': path, 'bytes': (root / path).stat().st_size, 'sha256': sha256(root / path)} for path in paths]
    for record in sources()['files']:
        if record['path'].startswith('face-models/'):
            verify_file(root / record['path'], record)
            records.append({key: record[key] for key in ('path', 'bytes', 'sha256')})
    atomic_json(root / 'runtime-model-manifest.json', {
        'source_layer_sha256': sources()['layer_sha256'],
        'validation': 'Original strict-load and CPU graph comparisons passed; run CUDA checks before serving',
        'files': records})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    fetch = sub.add_parser('download')
    fetch.add_argument('--cache-dir', type=Path, required=True)
    fetch.add_argument('--code-root', type=Path, required=True)
    install = sub.add_parser('install')
    install.add_argument('--code-root', type=Path, required=True)
    install.add_argument('--model-root', type=Path, required=True)
    final = sub.add_parser('finalize')
    final.add_argument('--model-root', type=Path, required=True)
    args = parser.parse_args()
    if args.command == 'download':
        download(args.cache_dir, args.code_root)
    elif args.command == 'install':
        install_raw(args.code_root, args.model_root)
    else:
        finalize_exports(args.model_root)


if __name__ == '__main__':
    main()
