"""Current Duix landmark masks, recovered from the shipped x86 interface."""
import cv2
import numpy as np


def mouth_mask(img,landmarks):
    size=img.shape[0]
    scale=size//266
    points=np.concatenate([landmarks[2:15],landmarks[29:30]]).astype(int)
    mask=np.zeros((size,size),dtype=np.uint8)
    cv2.fillConvexPoly(mask,cv2.convexHull(points),255)
    int_lm=landmarks.astype(int)
    center=tuple(((int_lm[5]+int_lm[11])//2).astype(int))
    axes=(int((int_lm[11,0]-int_lm[5,0]+3*scale)//2),60*scale)
    cv2.ellipse(mask,center,axes,0,0,180,(255,255,255),-1)
    amask=(mask>0).astype(np.uint8)*255
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(5*scale+1,5*scale+1))
    return cv2.dilate(amask,kernel,iterations=1)


def full_face_mask(img,landmarks,delta=0):
    size=img.shape[0]
    mask=np.zeros((size,size),dtype=np.uint8)
    cv2.fillConvexPoly(mask,cv2.convexHull(landmarks.astype(int)),255)
    kernel=cv2.getStructuringElement(cv2.MORPH_RECT,(5,5))
    mask=cv2.dilate(mask,kernel,iterations=1)
    cv2.GaussianBlur(mask,(5,5),0)  # Original discards the blurred array.
    return mask


def restore_face_mask(mask_shape=(512,512)):
    mask=np.zeros((512,512),dtype=np.float32)
    cv2.ellipse(mask,(256,256),(220,160),90,0,360,(255,255,255),-1)
    mask=cv2.stackBlur(mask,(201,201))/255
    return cv2.resize(mask,mask_shape)[...,np.newaxis]
