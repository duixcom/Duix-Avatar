"""Preparation failures must not publish an unvalidated model manifest."""
import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest
from unittest.mock import patch

import model_assets as assets


class ModelAssetTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def fixture_exports(self):
        for relative in ('export-fp32/original-dinet.ts.pt', 'export-fp32/original-metadata.pt',
                         'export-wenet/original-wenet.ts'):
            p = self.root / relative
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(b'unit-test artifact ' + relative.encode())
        dinet = {'completed': True, 'strict_state_dict_load': True, 'metadata_weights_only_reload': True,
                 'provenance': {'checkpoint': {'sha256': assets.DINET_CHECKPOINT}},
                 'export': {'sha256': assets.sha256(self.root / 'export-fp32/original-dinet.ts.pt')}}
        for key in ('eager_extension_vs_bytecode', 'eager_extension_vs_saved_torchscript'):
            dinet[key] = [{'allclose_atol_1e-6_rtol_1e-5': True}] * 3
        wenet = {'provenance': {'checkpoint': {'sha256': assets.WENET_CHECKPOINT}},
                 'checkpoint_coverage': {'missing': [], 'unexpected': [], 'value_mismatches': []},
                 'validation': [{'allclose_atol_2e-5_rtol_1e-4': True}] * 6,
                 'artifact': {'sha256': assets.sha256(self.root / 'export-wenet/original-wenet.ts')}}
        assets.atomic_json(self.root / 'export-fp32/export-report.json', dinet)
        assets.atomic_json(self.root / 'export-wenet/export-report.json', wenet)
        return dinet, wenet

    def test_failed_original_comparison_never_publishes_manifest(self):
        dinet, _ = self.fixture_exports()
        dinet['eager_extension_vs_saved_torchscript'][0] = {'allclose_atol_1e-6_rtol_1e-5': False}
        assets.atomic_json(self.root / 'export-fp32/export-report.json', dinet)
        with self.assertRaises(ValueError):
            assets.finalize_exports(self.root)
        self.assertFalse((self.root / 'runtime-model-manifest.json').exists())

    def test_changed_serialized_graph_is_rejected(self):
        self.fixture_exports()
        (self.root / 'export-wenet/original-wenet.ts').write_bytes(b'changed after validation')
        with self.assertRaises(ValueError):
            assets.finalize_exports(self.root)
        self.assertFalse((self.root / 'runtime-model-manifest.json').exists())

    def test_validated_local_artifact_hashes_are_not_machine_specific(self):
        self.fixture_exports()
        with patch.object(assets, 'sources', return_value={'layer_sha256': 'source-layer', 'files': []}):
            assets.finalize_exports(self.root)
        report = json.loads((self.root / 'runtime-model-manifest.json').read_text())
        self.assertEqual(len(report['files']), 3)
        for row in report['files']:
            self.assertEqual(row['sha256'], assets.sha256(self.root / row['path']))

    def test_archive_traversal_is_rejected(self):
        archive = self.root / 'malformed.tar.gz'
        with tarfile.open(archive, 'w:gz') as writer:
            entry = tarfile.TarInfo('code/../../outside')
            entry.size = 1
            writer.addfile(entry, io.BytesIO(b'x'))
        with self.assertRaises(ValueError):
            assets.extract_code(archive, self.root / 'output')
        self.assertFalse((self.root / 'outside').exists())


if __name__ == '__main__':
    unittest.main()
