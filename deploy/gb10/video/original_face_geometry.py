"""Portable recovery of original Duix legacy crop / paste-back geometry.

Source of truth: original image layer13 preprocess_audio_and_3dmm.cpython-39.pyc,
and main_multithreading_digitalhuman.py::get_complete_imgs. This does NOT claim
equivalence to the newer service.ai_service.so pipeline. No model is replaced.
The checkpoint supplies img_size and wh; callers must not guess those values.
"""

import cv2
import numpy as np
from scipy import signal


def target_size(img_size):
    # Preserve int-before-multiply from the original bytecode.
    return img_size + int(img_size / 256) * 10


def largest_face(face_boxes):
    if face_boxes.shape[0] == 1:
        return face_boxes[0].astype(int)
    return face_boxes[np.nanargmax(
        np.abs(face_boxes[:, 2] - face_boxes[:, 0])
        * np.abs(face_boxes[:, 3] - face_boxes[:, 1])
    )].astype(int)


def detection_box(image, face_boxes):
    """Original bounding_box_p: (row start, row end, col start, col end)."""
    if face_boxes.shape[0] == 0:
        return []
    h, w = image.shape[:2]
    x1, y1, x2, y2, score = largest_face(face_boxes)
    x1 = max(0, x1 - int((x2 - x1) * 0.1))
    y1 = max(0, y1)
    # Original uses the already-expanded x1 here.
    x2 = min(w, x2 + int((x2 - x1) * 0.1))
    y2 = min(h, y2 + int((y2 - y1) * 0.1))
    return np.array((y1, y2, x1, x2))


def legacy_smooth_one_based(entries):
    """Recover op.smooth_ exactly for its 1-based key convention.

    Reject zero-based keys: the original cached op and old main.py disagree
    about that convention. Keeping a silent off-by-one would corrupt geometry.
    """
    if not entries or set(entries) != set(range(1, max(entries) + 1)):
        raise ValueError("Original smoother requires contiguous keys 1..N")
    boxes = np.zeros((max(entries), 4))
    for idx in sorted(entries):
        if len(entries[idx]['bounding_box_p']) != 4:
            boxes[idx - 1, :] = boxes[idx - 2, :]
            continue
        boxes[idx - 1, :] = entries[idx]['bounding_box_p']
    kernel = np.ones((5, 1)) / 5
    smooth2 = signal.convolve2d(boxes, kernel, boundary='symm', mode='same')
    changed = np.where(np.abs(smooth2 - boxes).sum(1) > 12)[0]
    smooth3 = boxes + 0
    smooth3[changed] = boxes[changed]
    smooth4 = signal.convolve2d(smooth3, kernel, boundary='symm', mode='same')
    for idx in entries:
        entries[idx]['bounding_box_p'] = smooth4[idx - 1, :]


def crop_entry(entry, predictor, wh, img_size, driver_flag=False):
    """Original loc_crop_face, using the original pfpld predictor protocol."""
    image = entry['imgs_data']
    dets = entry['bounding_box_p']
    if len(dets) == 0:
        return entry
    face_landmarks = predictor.forward(
        image[int(dets[0]):int(dets[1]), int(dets[2]):int(dets[3])]
    )[0]
    landmarks = face_landmarks + np.array([dets[2], dets[0]])[np.newaxis]
    entry['landmarks'] = landmarks
    xmin, ymin, w, h = cv2.boundingRect(np.array(landmarks).astype(np.int32))
    xc = xmin + w / 2
    col_start = int(xc - w / wh * 0.75)
    col_end = int(xc + w / wh * 0.75)
    row_start = int(ymin - w / wh * 0.15)
    row_end = int(ymin + w / wh * 1.35)
    if col_start <= 0:
        col_start = 0
    if row_start <= 0:
        row_start = 0
    if col_end >= image.shape[1]:
        col_end = image.shape[1]
    if row_end >= image.shape[0]:
        row_end = image.shape[0]
    entry['bounding_box'] = np.array([row_start, row_end, col_start, col_end])
    size = target_size(img_size)
    lm_crop = np.zeros(landmarks.shape)
    lm_crop[..., 0] = size * (landmarks[..., 0] - col_start) / (col_end - col_start)
    lm_crop[..., 1] = size * (landmarks[..., 1] - row_start) / (row_end - row_start)
    crop = cv2.resize(image[row_start:row_end, col_start:col_end], (size, size),
                      interpolation=cv2.INTER_CUBIC)
    if driver_flag:
        crop = cv2.cvtColor(crop, cv2.COLOR_BGR2RGB)
    entry['crop_lm'] = lm_crop
    entry['crop_img'] = crop
    return entry


def paste_crop(image, crop, bounding_box, out_shape, output_resize=1):
    """Original get_complete_imgs per-frame operation, mutating image in place."""
    row_start, row_end, col_start, col_end = bounding_box
    restored = cv2.resize(crop, (col_end - col_start, row_end - row_start))
    if col_start < 0:
        restored = restored[:, -col_start:]
        col_start = 0
    if col_end > image.shape[1]:
        restored = restored[:, :-(col_end - image.shape[1])]
        col_end = image.shape[1]
    if row_start < 0:
        restored = restored[-row_start:, :]
        row_start = 0
    if row_end > image.shape[0]:
        restored = restored[:-(row_end - image.shape[0]), :]
        row_end = image.shape[0]
    image[row_start:row_end, col_start:col_end] = restored
    return cv2.resize(image, (out_shape[1] // output_resize, out_shape[0] // output_resize))
