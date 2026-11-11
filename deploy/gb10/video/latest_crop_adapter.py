"""Current original Duix DINet crop preprocessing and landmark blending."""
import cv2
import numpy as np
import torch
from original_crop_adapter import OriginalCropAdapter
from latest_masks import mouth_mask


class LatestCropAdapter(OriginalCropAdapter):
    get_face_mask=staticmethod(mouth_mask)

    def __init__(self,*args,xseg=None,**kwargs):
        super().__init__(*args,**kwargs)
        self.xseg=xseg

    @torch.inference_mode()
    def inference_notraining(self, audio_info, face_data_dict, this_batch, start_idx,
                            blend_dynamic="lmk", params=None, frameId=None):
        """Run original normalized DINet inputs and paste into aligned crops.

        audio_info[i] is the original WeNet context array with time first and
        feature channels second. face_data_dict[i]['crop_img'] is the original
        BGR aligned crop (including its preserved border), not a guessed bbox.
        The full-frame alignment/inverse warp remains the caller's job.
        """
        blend_mode=blend_dynamic
        blend_dynamic=blend_mode in ('lmk','xseg')
        if blend_mode=='xseg' and self.xseg is None:
            raise ValueError('Original XSeg model is required for xseg blending')
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
                if blend_mode=='xseg':
                    # Original branch binarizes its 0..1 segmentation, yet
                    # later divides by 255 and reverses the fusion direction.
                    blend_mask=self.xseg.forward(B_img)
                    blend_mask=(blend_mask>.1).astype(blend_mask.dtype)
                else:
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
                weight = cv2.stackBlur(blend_mask_list[i], (kernel, kernel), 0)
                weight=weight/255
                weight = torch.tensor(weight, device=self.device).unsqueeze(0).repeat(3, 1, 1)
                weights.append(weight)
            self.fuse_mask_cuda_copy = torch.stack(weights).to(self.device)
        else:
            self.fuse_mask_cuda_copy = self.fuse_mask_cuda.repeat(this_batch, 1, 1, 1)
        if blend_mode=='xseg':
            fuse_res = fake_B * (1 - self.fuse_mask_cuda_copy) + self.fuse_mask_cuda_copy * B_img
        else:
            fuse_res = fake_B * self.fuse_mask_cuda_copy + (1 - self.fuse_mask_cuda_copy) * B_img
        output_img_list = []
        for i in range(this_batch):
            mask_B_pre_list[i][lo:hi, lo:hi] = (fuse_res[i] * 255).permute(1, 2, 0).byte().cpu().numpy()[..., ::-1]
            output_img_list.append(mask_B_pre_list[i])
        return output_img_list
