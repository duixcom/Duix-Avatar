"""Original Duix enhancement ONNX models with oracle-verified preprocessing.

The network files are hash-pinned original artifacts; this module changes only
their Python/ORT host interface. It does not implement any license mechanism.
"""
import hashlib
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


MODEL_SHA256 = {
    "GFPGANv1.4.onnx": "f061a99cb6c8025dd5d29bf04e4d0349d613bb8dc1484555ea79403cee2cf448",
    "79999_iter.onnx": "506b4c6e514a348980a49fd3f19d53ce3807dac57fedac127e917165fac0e928",
    "xseg_211104_4790000.onnx": "8867760aeb83176e392d58c9ca123945cc36732c16763915b1d97f3acb0f1d64",
    "face_attr_epoch_12_220318.onnx": "0fa6604beacd1e560ffc4cae6fa1537591d5f1a765a9f55473a295a1d22da3af",
}


def verify_model(path):
    path = Path(path)
    with path.open("rb") as file:
        actual = hashlib.sha256(file.read()).hexdigest()
    if path.name not in MODEL_SHA256 or actual != MODEL_SHA256[path.name]:
        raise ValueError("Original model hash mismatch: " + str(path))
    return path


def make_session(path, providers, threads=2):
    path = verify_model(path)
    providers = list(providers)
    available = ort.get_available_providers()
    if any(name not in available for name in providers):
        raise RuntimeError("Requested ORT provider unavailable: " + repr(providers))
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(threads)
    options.inter_op_num_threads = 1
    return ort.InferenceSession(str(path), options, providers=providers)


class OriginalGFPGAN:
    """BGR uint8 aligned face -> original restored 512x512 BGR float32 [0,1].

    Input may have another spatial size; the original cv2box blob operator
    resizes it to 512x512 before RGB normalization. No frame paste-back occurs
    here: original alignment and mask blending belong to the caller.
    """
    input_size = (512, 512)
    input_mean = input_std = 127.5

    def __init__(self, model_path, providers=("CPUExecutionProvider",), threads=2, session=None):
        if session is None:
            self.session = make_session(model_path, providers, threads)
            self.input_name = self.session.get_inputs()[0].name
        else:
            verify_model(model_path)
            self.session = session
            self.input_name = "input"  # fixed original GFPGAN ONNX input name

    @classmethod
    def preprocess(cls, face_image):
        # Original cv2box==0.5.9 CVImage.blob(..., rgb=True).
        return cv2.dnn.blobFromImages([face_image], 1.0 / cls.input_std,
                                     cls.input_size, (cls.input_mean,) * 3,
                                     swapRB=True)

    @staticmethod
    def postprocess(output):
        output = output[0].transpose(1, 2, 0)
        output = (output.clip(-1, 1) + 1) / 2
        return cv2.cvtColor(output, cv2.COLOR_RGB2BGR)

    def forward(self, face_image):
        blob = self.preprocess(face_image)
        result = self.session.run(None, {self.input_name: blob})[0]
        if not np.isfinite(result).all():
            raise RuntimeError("Original GFPGAN returned non-finite values")
        return self.postprocess(result)


class OriginalFaceParsing:
    """Original 19-class BGR parser; the caller chooses how to use labels."""
    input_size = 512
    input_mean = (0.485, 0.456, 0.406)
    input_std = (0.229, 0.224, 0.225)
    mask_colormap = (0, 255, 255, 255, 255, 255, 255, 255, 255, 255,
                     255, 255, 255, 255, 0, 255, 0, 0, 0)

    def __init__(self, model_path, providers=("CPUExecutionProvider",), threads=2):
        self.session = make_session(model_path, providers, threads)
        self.input_name = self.session.get_inputs()[0].name
        self.parsing_results = None
        self.face_image = None

    @classmethod
    def preprocess(cls, face_image):
        if face_image.shape[:2] != (cls.input_size, cls.input_size):
            face_image = cv2.resize(face_image, (cls.input_size, cls.input_size), interpolation=cv2.INTER_LINEAR)
        # Preserve cv2box blob_innormal arithmetic, float64 scalars and BGR
        # channel order. Original forward does not request rgb=True.
        face_image = np.ascontiguousarray(face_image, dtype=np.float32)
        mean = np.float64(np.array(cls.input_mean).reshape(1, -1))
        inverse_std = 1 / np.float64(np.array(cls.input_std).reshape(1, -1))
        mean *= 255
        inverse_std /= 255
        cv2.subtract(face_image, mean, face_image)
        cv2.multiply(face_image, inverse_std, face_image)
        return face_image.transpose(2, 0, 1)[np.newaxis]

    def forward(self, face_image):
        self.face_image = face_image
        blob = self.preprocess(face_image)
        result = self.session.run(None, {self.input_name: blob})[0]
        if not np.isfinite(result).all():
            raise RuntimeError("Original face parser returned non-finite values")
        self.parsing_results = result.squeeze(0).argmax(0)
        return self.parsing_results

    @staticmethod
    def get_face_mask(mask_shape):
        """Original soft oval mask; mask_shape is OpenCV (width,height)."""
        mask = np.zeros((512, 512), dtype=np.float32)
        cv2.ellipse(mask, (256, 256), (220, 160), 90, 0, 360, (255, 255, 255), -1)
        mask = cv2.stackBlur(mask, (201, 201))
        mask = cv2.resize(mask / 255, mask_shape)
        return mask[:, :, np.newaxis]


def recover_restored_roi(restored_face, frame, matrix_reverse, roi_box, face_mask=None):
    """Original GFPGAN thread reverse operation; mutates and returns BGR frame.

    roi_box is [x1,y1,x2,y2], already clipped by original apply_roi_func.
    The transform maps the aligned 512 face back into that ROI, not directly
    into full-frame coordinates. This is distinct from legacy DINet paste-back.
    """
    if restored_face is None:
        return frame
    import numexpr
    if face_mask is None:
        face_mask = OriginalFaceParsing.get_face_mask((512, 512))
    x1, y1, x2, y2 = roi_box
    background = frame[y1:y2, x1:x2]
    transformed = cv2.warpAffine(restored_face, matrix_reverse, background.shape[:2][::-1],
                                  borderMode=cv2.BORDER_REPLICATE)
    mask = cv2.warpAffine(face_mask, matrix_reverse, background.shape[:2][::-1], borderValue=0)[..., np.newaxis]
    # This expression and uint8 truncation are the original cv2box 0.5.9 path.
    blended = numexpr.evaluate("mask * (transformed * 255) + (1 - mask) * background",
                              local_dict={"mask": mask, "transformed": transformed, "background": background},
                              global_dict=None).astype(np.uint8)
    frame[y1:y2, x1:x2] = blended
    return frame


def restore_aligned_face(model, frame, aligned_face, matrix_reverse, roi_box):
    """Equivalent Restore -> Parse(oval mask) -> Reverse GFPGAN thread stages."""
    if aligned_face is None:
        return frame
    restored_face = model.forward(aligned_face)
    return recover_restored_roi(restored_face, frame, matrix_reverse, roi_box)


def chaofen_source_batch(frame_list, gfpgan, detector, frame_id, face_attr,
                         need_chaofen=False, first_face_found=False,
                         batch_size=2, blur_threshold=0.3, align_face=None):
    """Original service.chaofen_src source-frame restoration and state flags.

    frame_id is the original count after collecting this batch, so the first
    complete batch normally passes frame_id == batch_size. Detector must expose
    get_bboxes(BGR) -> (Nx5 boxes, Nx5x2 points). Faces are aligned to 512 using
    the original mtcnn template, restored and pasted back into the source ROI.
    This runs before subsequent DINet crop/inference and does not remove green.
    """
    if align_face is None:
        from latest_face_geometry import get_single_face
        align_face = get_single_face
    if frame_id == batch_size or not first_face_found:
        need_chaofen = False
        first_face_found = False
        for frame in frame_list:
            boxes, points = detector.get_bboxes(frame)
            if len(boxes) == 0:
                continue
            face, _, _ = align_face(boxes, points, frame, crop_size=512,
                                     mode="mtcnn_512", apply_roi=True)
            # Explicit float preserves original NumPy 1.x scalar comparison
            # against a Python float on NumPy 2.x (notably float32(0.3)).
            need_chaofen = float(face_attr.forward(face)[0][-2]) > blur_threshold
            first_face_found = True
            break
    if need_chaofen:
        mask = OriginalFaceParsing.get_face_mask((512, 512))
        for frame in frame_list:
            boxes, points = detector.get_bboxes(frame)
            if len(boxes) == 0:
                continue
            face, matrix_reverse, roi_box = align_face(boxes, points, frame,
                crop_size=512, mode="mtcnn_512", apply_roi=True)
            recover_restored_roi(gfpgan.forward(face), frame, matrix_reverse, roi_box, mask)
    return frame_list, bool(need_chaofen), bool(first_face_found)


class OriginalSourceEnhancer:
    """One instance per render job; carries original first-face blur decision."""
    def __init__(self, gfpgan, detector, face_attr, batch_size=2,
                 blur_threshold=0.3, align_face=None):
        self.gfpgan, self.detector, self.face_attr = gfpgan, detector, face_attr
        self.batch_size, self.blur_threshold = batch_size, blur_threshold
        self.align_face = align_face
        self.need_chaofen = False
        self.first_face_found = False

    def process_batch(self, frames, frame_id):
        frames, self.need_chaofen, self.first_face_found = chaofen_source_batch(
            frames, self.gfpgan, self.detector, frame_id, self.face_attr,
            self.need_chaofen, self.first_face_found, self.batch_size,
            self.blur_threshold, self.align_face)
        return frames


class OriginalFaceAttr:
    """Original ten-value face-quality model; blur score is output[0][-2]."""
    input_size = 512
    input_mean = (132.38155592, 110.99284567, 102.62942472)
    input_std = (68.5106407, 61.65929394, 58.61700102)

    def __init__(self, model_path, providers=("CPUExecutionProvider",), threads=2):
        self.session = make_session(model_path, providers, threads)
        self.input_name = self.session.get_inputs()[0].name

    @classmethod
    def preprocess(cls, image):
        if image.shape[:2] != (512, 512):
            image = cv2.resize(image, (512, 512), interpolation=cv2.INTER_LINEAR)
        image = np.ascontiguousarray(image, dtype=np.float32)
        mean = np.float64(np.array(cls.input_mean).reshape(1, -1))
        inverse_std = 1 / np.float64(np.array(cls.input_std).reshape(1, -1))
        cv2.subtract(image, mean, image)
        cv2.multiply(image, inverse_std, image)
        return image.transpose(2, 0, 1)[np.newaxis]

    def forward(self, image):
        # Original FaceAttr rounds the entire ten-value matrix to 3 decimals
        # before chaofen_src compares its blur column with the threshold.
        return self.session.run(None, {self.input_name: self.preprocess(image)})[0].round(3)


class OriginalXseg:
    """Original DFL Xseg probability mask, without thresholding or clipping."""
    def __init__(self, model_path, providers=("CPUExecutionProvider",), threads=2):
        self.session = make_session(model_path, providers, threads)
        self.input_name = self.session.get_inputs()[0].name

    @staticmethod
    def preprocess(image):
        # Original CVImage.resize tuple comparison uses (height,width), but the
        # fixed square target makes that comparison equivalent here.
        if image.shape[:2] != (256, 256):
            image = cv2.resize(image, (256, 256))
        return (image.astype(np.float32) / 255)[np.newaxis]

    def forward(self, image):
        result = self.session.run(None, {self.input_name: self.preprocess(image)})[0]
        # Preserve the original API's swapped width/height on nonsquare input.
        # Its normal pipeline callers supply square aligned faces.
        mask = result[0]
        if tuple(image.shape[:2]) != mask.shape[:-1]:
            mask = cv2.resize(mask, tuple(image.shape[:2]))
        return mask
