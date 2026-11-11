"""Current Duix five-point alignment recovered against its original extension.

Uses the original template coordinates. In particular, arcface_512 and mtcnn
templates retain their fixed coordinate scale, as in the original wrapper.
"""
import json
from pathlib import Path

import cv2
import numpy as np
from skimage import transform as trans

_templates=json.loads((Path(__file__).with_name('align-oracle-api.json')).read_text())
def _array(name):
    item=_templates[name]
    return np.array(item['values'],dtype=item['dtype']) if isinstance(item,dict) else np.array(item)
multi_src=_array('multi_src')
multi_src_map={int(k):np.array(v['values'],dtype=v['dtype']) for k,v in _templates['multi_src_map'].items()}
multi_src_map[112]=multi_src
arcface_src=_array('arcface_src')
arcface_src_512=_array('arcface_src_512')
mtcnn_512=_array('mtcnn_512')
mtcnn_256=_array('mtcnn_256')


def get_src_modify(srcs,arcface):
    delta=arcface[2]-srcs[2,2]
    srcs[:,:,0]+=delta[0]
    srcs[:,:,1]+=delta[1]*1.8
    return srcs


def estimate_norm(lmk,image_size=112,mode='arcface'):
    assert lmk.shape==(5,2)
    if mode=='arcface':
        assert image_size==112
        src=arcface_src
    elif mode=='arcface_512':
        src=np.expand_dims(arcface_src_512,0)
    elif mode=='mtcnn_512':
        src=np.expand_dims(mtcnn_512,0)
    elif mode=='mtcnn_256':
        src=np.expand_dims(mtcnn_256,0)
    elif mode=='default_95':
        base=get_src_modify(multi_src,arcface_src[0])
        src={112:base,224:base*2*.95,256:base*256/112*.95,512:base*(512/112)*.95}[image_size]
    else:
        src=multi_src_map[image_size]
    tform=trans.SimilarityTransform()
    lmk_tran=np.insert(lmk,2,values=np.ones(5),axis=1)
    min_error=float('inf')
    min_M=None
    min_index=0
    for i in np.arange(src.shape[0]):
        tform.estimate(lmk,src[i])
        M=tform.params[0:2,:]
        results=np.dot(M,lmk_tran.T).T
        error=np.sum(np.sqrt(np.sum((results-src[i])**2,axis=1)))
        if error<min_error:
            min_error=error
            min_M=M
            min_index=i
    return min_M,min_index


def norm_crop(img,landmark,crop_size=112,mode='arcface'):
    M,pose_index=estimate_norm(landmark,crop_size,mode)
    warped=cv2.warpAffine(img,M,(crop_size,crop_size),borderMode=cv2.BORDER_REPLICATE)
    return warped,cv2.invertAffineTransform(M)


def apply_roi_func(img,box,facial5points):
    roi_box=np.round(box).astype(int)
    roi_box[0]=max(roi_box[0],0)
    roi_box[1]=max(roi_box[1],0)
    roi_box[2]=min(roi_box[2],img.shape[1])
    roi_box[3]=min(roi_box[3],img.shape[0])
    roi=img[roi_box[1]:roi_box[3],roi_box[0]:roi_box[2]]
    roi_facial5points=facial5points.copy()
    roi_facial5points[:,0]-=roi_box[0]
    roi_facial5points[:,1]-=roi_box[1]
    return roi,roi_box,roi_facial5points


def get_single_face(bboxes,kpss,image,crop_size=512,mode="mtcnn_512",apply_roi=True):
    index=np.argmax(bboxes[:,4])
    box=bboxes[index,:4]
    points=kpss[index]
    if apply_roi:
        roi,roi_box,points=apply_roi_func(image,box,points)
        aligned,reverse=norm_crop(roi,points,crop_size,mode)
        return aligned,reverse,roi_box
    return norm_crop(image,points,crop_size,mode)
