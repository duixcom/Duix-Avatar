"""Portable original Duix SCRFD + pfpld inference, with unchanged ONNX weights.

Transcribed from the official image's CPython 3.9 bytecode and checked against
its compiled x86 extensions. This preserves Duix's swapRB=False, 98-to-68
landmark mapping, normalization, resize, anchor ordering, and NMS arithmetic.
The public ndarray APIs preserve channel order exactly as the original API;
they do not silently convert BGR/RGB. CPU ORT is the portable default.
"""
import hashlib
from pathlib import Path

import cv2
import numpy as np
import onnxruntime as ort


MODEL_SHA256 = {
    "scrfd_500m_bnkps_shape640x640.onnx": "b467f878e26ff1e7ee05cd9936fdff63fa2a5af5d732ed17ee231f2dd5cc07ae",
    "pfpld_robust_sim_bs1_8003.onnx": "8bd9913817152831562cccde7e51ed431d1cf4547d8f21e0876b58a0d82baa55",
}


def model_path(root, name):
    path = Path(root) / name
    if not path.is_file():
        path = Path(root) / "resources" / name
    if hashlib.sha256(path.read_bytes()).hexdigest() != MODEL_SHA256[name]:
        raise RuntimeError("Original model SHA256 mismatch: " + str(path))
    return str(path)


def session_options(threads):
    options = ort.SessionOptions()
    options.intra_op_num_threads = int(threads)
    options.inter_op_num_threads = 1
    return options


def distance2bbox(points, distance, max_shape=None):
    x1 = points[:, 0] - distance[:, 0]
    y1 = points[:, 1] - distance[:, 1]
    x2 = points[:, 0] + distance[:, 2]
    y2 = points[:, 1] + distance[:, 3]
    if max_shape is not None:
        x1 = x1.clamp(min=0, max=max_shape[1])
        y1 = y1.clamp(min=0, max=max_shape[0])
        x2 = x2.clamp(min=0, max=max_shape[1])
        y2 = y2.clamp(min=0, max=max_shape[0])
    return np.stack([x1, y1, x2, y2], axis=-1)


def distance2kps(points, distance, max_shape=None):
    preds = []
    for i in range(0, distance.shape[1], 2):
        px = points[:, i % 2] + distance[:, i]
        py = points[:, i % 2 + 1] + distance[:, i + 1]
        if max_shape is not None:
            px = px.clamp(min=0, max=max_shape[1])
            py = py.clamp(min=0, max=max_shape[0])
        preds.append(px)
        preds.append(py)
    return np.stack(preds, axis=-1)


class SCRFD:
    def __init__(self, model_file=None, session=None, cpu=True, threads=2):
        self.model_file, self.session = model_file, session
        self.taskname, self.batched = "detection", False
        if session is None:
            assert model_file is not None and Path(model_file).exists()
            providers = ["CPUExecutionProvider"] if cpu else ["CUDAExecutionProvider"]
            self.session = ort.InferenceSession(str(model_file), session_options(threads), providers=providers)
        self.center_cache = {}
        self.nms_thresh = 0.35
        self._init_vars()

    def _init_vars(self):
        input_cfg = self.session.get_inputs()[0]
        input_shape = input_cfg.shape
        self.input_size = None if isinstance(input_shape[2], str) else tuple(input_shape[2:4][::-1])
        self.input_name = input_cfg.name
        outputs = self.session.get_outputs()
        if len(outputs[0].shape) == 3:
            self.batched = True
        self.output_names = [o.name for o in outputs]
        self.use_kps, self._num_anchors = False, 1
        if len(outputs) in (6, 9):
            self.fmc, self._feat_stride_fpn, self._num_anchors = 3, [8, 16, 32], 2
            self.use_kps = len(outputs) == 9
        elif len(outputs) in (10, 15):
            self.fmc, self._feat_stride_fpn = 5, [8, 16, 32, 64, 128]
            self.use_kps = len(outputs) == 15

    def prepare(self, ctx_id, **kwargs):
        if ctx_id < 0:
            self.session.set_providers(["CPUExecutionProvider"])
        if kwargs.get("nms_thresh") is not None:
            self.nms_thresh = kwargs["nms_thresh"]
        if kwargs.get("input_size") is not None and self.input_size is None:
            self.input_size = kwargs["input_size"]

    def forward(self, img, thresh):
        scores_list, bboxes_list, kpss_list = [], [], []
        input_size = tuple(img.shape[0:2][::-1])
        blob = cv2.dnn.blobFromImage(img, 1.0 / 128, input_size, (127.5, 127.5, 127.5), swapRB=False)
        net_outs = self.session.run(self.output_names, {self.input_name: blob})
        input_height, input_width, fmc = blob.shape[2], blob.shape[3], self.fmc
        for idx, stride in enumerate(self._feat_stride_fpn):
            if self.batched:
                scores = net_outs[idx][0]
                bbox_preds = net_outs[idx + fmc][0] * stride
                if self.use_kps:
                    kps_preds = net_outs[idx + fmc * 2][0] * stride
            else:
                scores = net_outs[idx]
                bbox_preds = net_outs[idx + fmc] * stride
                if self.use_kps:
                    kps_preds = net_outs[idx + fmc * 2] * stride
            height, width = input_height // stride, input_width // stride
            key = (height, width, stride)
            if key in self.center_cache:
                anchor_centers = self.center_cache[key]
            else:
                anchor_centers = np.stack(np.mgrid[:height, :width][::-1], axis=-1).astype(np.float32)
                anchor_centers = (anchor_centers * stride).reshape((-1, 2))
                if self._num_anchors > 1:
                    anchor_centers = np.stack([anchor_centers] * self._num_anchors, axis=1).reshape((-1, 2))
                if len(self.center_cache) < 100:
                    self.center_cache[key] = anchor_centers
            pos_inds = np.where(scores >= thresh)[0]
            bboxes = distance2bbox(anchor_centers, bbox_preds)
            scores_list.append(scores[pos_inds])
            bboxes_list.append(bboxes[pos_inds])
            if self.use_kps:
                kpss = distance2kps(anchor_centers, kps_preds)
                kpss = kpss.reshape((kpss.shape[0], -1, 2))
                kpss_list.append(kpss[pos_inds])
        return scores_list, bboxes_list, kpss_list

    def detect(self, img, thresh=0.5, input_size=None, max_num=0, metric="default"):
        assert input_size is not None or self.input_size is not None
        input_size = self.input_size if input_size is None else input_size
        im_ratio = float(img.shape[0]) / img.shape[1]
        model_ratio = float(input_size[1]) / input_size[0]
        if im_ratio > model_ratio:
            new_height = input_size[1]
            new_width = int(new_height / im_ratio)
        else:
            new_width = input_size[0]
            new_height = int(new_width * im_ratio)
        det_scale = float(new_height) / img.shape[0]
        resized_img = cv2.resize(img, (new_width, new_height))
        det_img = np.zeros((input_size[1], input_size[0], 3), dtype=np.uint8)
        det_img[:new_height, :new_width, :] = resized_img
        scores_list, bboxes_list, kpss_list = self.forward(det_img, thresh)
        scores = np.vstack(scores_list)
        order = scores.ravel().argsort()[::-1]
        bboxes = np.vstack(bboxes_list) / det_scale
        if self.use_kps:
            kpss = np.vstack(kpss_list) / det_scale
        pre_det = np.hstack((bboxes, scores)).astype(np.float32, copy=False)
        pre_det = pre_det[order, :]
        keep = self.nms(pre_det)
        det = pre_det[keep, :]
        if self.use_kps:
            kpss = kpss[order, :, :]
            kpss = kpss[keep, :, :]
        else:
            kpss = None
        if max_num > 0 and det.shape[0] > max_num:
            area = (det[:, 2] - det[:, 0]) * (det[:, 3] - det[:, 1])
            img_center = (img.shape[0] // 2, img.shape[1] // 2)
            offsets = np.vstack([(det[:, 0] + det[:, 2]) / 2 - img_center[1],
                                 (det[:, 1] + det[:, 3]) / 2 - img_center[0]])
            offset_dist_squared = np.sum(np.power(offsets, 2.0), 0)
            values = area if metric == "max" else area - offset_dist_squared * 2.0
            bindex = np.argsort(values)[::-1][0:max_num]
            det = det[bindex, :]
            if kpss is not None:
                kpss = kpss[bindex, :]
        return det, kpss

    def nms(self, dets):
        x1, y1, x2, y2, scores = (dets[:, i] for i in range(5))
        areas = (x2 - x1 + 1) * (y2 - y1 + 1)
        order = scores.argsort()[::-1]
        keep = []
        while order.size > 0:
            i = order[0]
            keep.append(i)
            xx1 = np.maximum(x1[i], x1[order[1:]])
            yy1 = np.maximum(y1[i], y1[order[1:]])
            xx2 = np.minimum(x2[i], x2[order[1:]])
            yy2 = np.minimum(y2[i], y2[order[1:]])
            w = np.maximum(0.0, xx2 - xx1 + 1)
            h = np.maximum(0.0, yy2 - yy1 + 1)
            inter = w * h
            ovr = inter / (areas[i] + areas[order[1:]] - inter)
            inds = np.where(ovr <= self.nms_thresh)[0]
            order = order[inds + 1]
        return keep


def convert98to68(list_info):
    points = list_info[0, 0:196]
    result = []
    for index in list(range(0, 34, 2)) + list(range(33, 38)) + list(range(42, 47)) + list(range(51, 61)):
        result.extend((points[index * 2], points[index * 2 + 1]))
    # Preserve the original float32 -> Python float promotions before means.
    for first, second in ((60, 62), (62, 64), (64, None), (64, 66), (60, 66),
                          (68, None), (68, 70), (70, 72), (72, None), (72, 74), (68, 74)):
        for axis in (0, 1):
            if second is None:
                result.append(points[first * 2 + axis])
            else:
                result.append((float(points[first * 2 + axis]) + float(points[second * 2 + axis])) / 2.0)
    for index in range(76, 96):
        result.extend((points[index * 2], points[index * 2 + 1]))
    for j in range(len(list_info[196:])):
        result.append(list_info[196 + j])
    return np.array(result)


class OriginalFaceDetector:
    def __init__(self, model_root, cpu=True, threads=2):
        self.det_model = SCRFD(model_path(model_root, "scrfd_500m_bnkps_shape640x640.onnx"), cpu=cpu, threads=threads)
        self.det_model.prepare(ctx_id=0, input_size=(640, 640))

    def get_bboxes(self, image, thresh=0.5, max_num=0):
        if type(image) is str:
            image = cv2.cvtColor(cv2.imread(image), cv2.COLOR_BGR2RGB)
        return self.det_model.detect(image, thresh=thresh, max_num=max_num, metric="max")

    def detect(self, image, thresh=0.5, max_num=0):
        return self.get_bboxes(image, thresh=thresh, max_num=max_num)[0]


class OriginalLandmarks:
    def __init__(self, model_root, cpu=True, threads=2):
        providers = ["CPUExecutionProvider"] if cpu else ["CUDAExecutionProvider"]
        self.ort_session = ort.InferenceSession(model_path(model_root, "pfpld_robust_sim_bs1_8003.onnx"), session_options(threads), providers=providers)
        self.input_name = self.ort_session.get_inputs()[0].name

    def forward(self, image):
        size = image.shape
        tensor = (cv2.resize(image, (112, 112)) / 255).astype(np.float32).transpose(2, 0, 1)[None]
        pred = self.ort_session.run(None, {self.input_name: tensor})
        pred = convert98to68(pred[1])
        return pred.reshape(-1, 68, 2) * size[:2][::-1]
