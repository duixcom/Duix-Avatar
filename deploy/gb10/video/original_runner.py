"""Shared loader for the original DINet, WeNet and face models."""
import hashlib
import json
from pathlib import Path



class OriginalDuixRunner:
    engine = 'Duix DINetV1 + WeNet (original weights)'

    def __init__(self, root, batch_size=4):
        self.root = Path(root).resolve()
        self.batch_size = batch_size
        self.loaded = False
        if not 1 <= batch_size <= 8:
            raise ValueError('Batch size must be between 1 and 8')

    def _load(self):
        if self.loaded:
            return
        manifest = json.loads((self.root / 'runtime-model-manifest.json').read_text())
        for item in manifest['files']:
            path = self.root / item['path']
            digest = hashlib.sha256()
            with path.open('rb') as stream:
                for block in iter(lambda: stream.read(8 * 1024 * 1024), b''):
                    digest.update(block)
            if path.stat().st_size != item['bytes'] or digest.hexdigest() != item['sha256']:
                raise RuntimeError('Original runtime model checksum mismatch: ' + item['path'])
        import cv2
        import numpy as np
        import torch
        from original_crop_adapter import OriginalCropAdapter
        from original_face_detect import OriginalFaceDetector, OriginalLandmarks
        from original_wenet_audio import OriginalWenet
        if not torch.cuda.is_available():
            raise RuntimeError('Original Duix port requires native CUDA')
        torch.set_num_threads(4)
        torch.backends.cuda.matmul.allow_tf32 = False
        torch.backends.cudnn.allow_tf32 = False
        torch.backends.cudnn.benchmark = False
        model = torch.jit.load(str(self.root / 'export-fp32/original-dinet.ts.pt'), map_location='cuda').eval()
        meta = torch.load(self.root / 'export-fp32/original-metadata.pt', map_location='cpu', weights_only=True)
        meta = {key: value.numpy() if isinstance(value, torch.Tensor) else value for key, value in meta.items()}
        if meta['model_name'] != 'dinet_v1' or tuple(meta['model_input_size']) != (256, 256):
            raise ValueError('Unexpected original model metadata')
        self.adapter = OriginalCropAdapter(model, meta, device='cuda')
        self.metadata = meta
        self.wenet = OriginalWenet(self.root / 'export-wenet/original-wenet.ts', device='cuda')
        self.detector = OriginalFaceDetector(self.root / 'face-models')
        self.landmarks = OriginalLandmarks(self.root / 'face-models')
        self.cv2, self.np, self.torch = cv2, np, torch
        self.loaded = True
