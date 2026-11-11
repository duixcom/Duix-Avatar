"""Port of the original Duix crop-level preprocessing and blending operations.

Source: official guiji2025/duix.avatar-5090 image layer 15, the bundled
landmark2face_wy/__pycache__/digitalhuman_interface.cpython-39.pyc,
SHA256 5be35d199aebf69241b433713697614b1bed3d88becc909e402f66593afb054c.
The operations below were transcribed from CPython 3.9 bytecode, not inferred
from a different talking-head model. This module does not implement the
upstream full-frame crop/warp, WeNet feature extraction or service licensing.

The original methods mutate crop_img and (with dynamic blending) crop_lm in
face_data_dict. These side effects are retained for differential verification.
"""
import math
from typing import Mapping

import cv2
import numpy as np
import torch


class OriginalCropAdapter:
    def __init__(self, netG, metadata: Mapping, device="cuda"):
        self.netG = netG
        self.device = torch.device(device)
        self.img_size = int(metadata["model_input_size"][0])
        self.nblend = metadata["nblend"]
        self.drivered_wh = metadata["wh"]
        self.fuse_mask = cv2.resize(metadata["fuse_mask"], (self.img_size, self.img_size))
        # The upstream constructor explicitly uses half-precision masks. Input
        # images are uint8/255 and retain PyTorch's original promotion behavior.
        self.mask_re_cuda = torch.tensor(metadata["input_mask_re"], device=self.device).unsqueeze(0).unsqueeze(0).half()
        self.mask_cuda = torch.tensor(metadata["input_mask"], device=self.device).unsqueeze(0).unsqueeze(0).half()
        self.fuse_mask_cuda = torch.tensor(self.fuse_mask, device=self.device).unsqueeze(0).unsqueeze(0).repeat(1, 3, 1, 1).half()

    @staticmethod
    def tensor_norm(img_tensor, mask=None):
        img_tensor = img_tensor / 127.5 - 1
        return (img_tensor + 1) * mask - 1 if mask is not None else img_tensor

    @staticmethod
    def tensor_norm_no_training(img_tensor, mask=None):
        img_tensor = img_tensor / 255.0
        return img_tensor * mask if mask is not None else img_tensor

    @staticmethod
    def get_face_mask(img, landmarks):
        """Exact original dynamic-mouth-mask geometry, including array mutation."""
        imgshape = img.shape[0]
        landmarks0 = landmarks.copy()
        rad = math.atan(math.radians(landmarks[1, 1] - landmarks[15, 1]) /
                        (landmarks[15, 0] - landmarks[1, 0]))
        tmp = 12 * (imgshape // 266) + 1
        for i in range(3, 14):
            landmarks[i, 0] = min(landmarks[i, 0] + tmp * math.sin(rad), imgshape)
            landmarks[i, 1] = min(landmarks[i, 1] + tmp * math.cos(rad), imgshape)
        wanted_numpy = np.concatenate([landmarks0[2:15], landmarks[2:15], landmarks[29:30]]).astype(int)
        mask = np.zeros((imgshape, imgshape), dtype=np.uint8)
        wanted_numpy = cv2.convexHull(wanted_numpy)
        cv2.fillConvexPoly(mask, wanted_numpy, 255)
        amask = (mask > 0).astype(np.uint8) * 255
        kernel_size = (2 * (imgshape // 266) + 1, 2 * (imgshape // 266) + 1)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, kernel_size)
        return cv2.dilate(amask, kernel, iterations=1)

    @torch.inference_mode()
    def inference_notraining(self, audio_info, face_data_dict, this_batch, start_idx,
                            blend_dynamic=False, params=None):
        """Run original normalized DINet inputs and paste into aligned crops.

        audio_info[i] is the original WeNet context array with time first and
        feature channels second. face_data_dict[i]['crop_img'] is the original
        BGR aligned crop (including its preserved border), not a guessed bbox.
        The full-frame alignment/inverse warp remains the caller's job.
        """
        if this_batch <= 0:
            raise ValueError("this_batch must be positive")
        B_img_list, B_img__list, mask_B_list, mask_B_pre_list = [], [], [], []
        blend_mask_list, lab_list = [], []
        lo, hi = int(5 * self.img_size / 256), int(-5 * self.img_size / 256)
        for i in range(this_batch):
            img_idx = start_idx + i
            mask_B_pre = face_data_dict[img_idx]["crop_img"]
            mask_B = mask_B_pre[lo:hi, lo:hi]
            B_img = mask_B.copy()
            mask_B = torch.from_numpy(mask_B[:, :, [2, 1, 0]].transpose(2, 0, 1))
            B_img_ = B_img.copy()
            B_img_ = torch.from_numpy(B_img_[:, :, [2, 1, 0]].transpose(2, 0, 1))
            if blend_dynamic:
                lm = face_data_dict[img_idx]["crop_lm"]
                blend_mask = self.get_face_mask(mask_B_pre, lm)[lo:hi, lo:hi]
                blend_mask = cv2.resize(blend_mask, (self.img_size, self.img_size))
                blend_mask_list.append(blend_mask)
            B_img_list.append(torch.from_numpy(B_img[:, :, [2, 1, 0]].transpose(2, 0, 1)))
            B_img__list.append(B_img_)
            mask_B_pre_list.append(mask_B_pre)
            mask_B_list.append(mask_B)
            lab_list.append(audio_info[start_idx + i].transpose(1, 0))

        lab = torch.tensor(np.asarray(lab_list), device=self.device)
        mask_B = torch.stack(mask_B_list).to(self.device)
        mask_B = self.tensor_norm_no_training(mask_B, self.mask_cuda.repeat(this_batch, 3, 1, 1))
        B_img_ = torch.stack(B_img__list).to(self.device)
        B_img_ = self.tensor_norm_no_training(B_img_, self.mask_re_cuda.repeat(this_batch, 3, 1, 1))
        B_img = self.tensor_norm_no_training(torch.stack(B_img_list).to(self.device))
        fake_B = self.netG(mask_B, B_img_, lab)
        if not torch.isfinite(fake_B).all().item():
            raise RuntimeError('Original DINet returned non-finite pixels')
        if self.nblend:
            fake_B = torch.where(self.mask_re_cuda == 0, B_img, fake_B)
        if blend_dynamic:
            weights = []
            kernel = 16 * int(self.img_size / 256) + 1
            for i in range(this_batch):
                weight = cv2.GaussianBlur(blend_mask_list[i], (kernel, kernel), 0) / 255
                weight = torch.tensor(weight, device=self.device).unsqueeze(0).repeat(3, 1, 1)
                weights.append(weight)
            self.fuse_mask_cuda_copy = torch.stack(weights).to(self.device)
        else:
            self.fuse_mask_cuda_copy = self.fuse_mask_cuda.repeat(this_batch, 1, 1, 1)
        fuse_res = fake_B * self.fuse_mask_cuda_copy + (1 - self.fuse_mask_cuda_copy) * B_img
        output_img_list = []
        for i in range(this_batch):
            mask_B_pre_list[i][lo:hi, lo:hi] = (fuse_res[i] * 255).permute(1, 2, 0).byte().cpu().numpy()[..., ::-1]
            output_img_list.append(mask_B_pre_list[i])
        return output_img_list
