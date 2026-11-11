"""Latest Duix per-frame mouth crops; original SCRFD/PFPLD/WHENet stay unchanged.

No smoothing is applied in the current original `preprocess_audio_and_3dmm2`.
`process_batch` retains frame indices, including rejected face/pose indices.
The caller receives rejected indices. The original service attempts to restore
those frames after generation, but aliases its source arrays during pasteback;
the native runner deliberately preserves the unchanged input instead.
"""
import cv2
import numpy as np


def largest_face(boxes):
    if len(boxes)==1:return boxes[0].astype(int)
    return boxes[np.nanargmax(np.abs(boxes[:,2]-boxes[:,0])*np.abs(boxes[:,3]-boxes[:,1]))].astype(int)


def detection_box(image,boxes):
    if not len(boxes):return []
    h,w=image.shape[:2]
    x1,y1,x2,y2,_=largest_face(boxes)
    x1=max(0,x1-int((x2-x1)*.1));y1=max(0,y1)
    x2=min(w,x2+int((x2-x1)*.1));y2=min(h,y2+int((y2-y1)*.1))
    return np.array([y1,y2,x1,x2])


def head_pose_box(image,landmarks):
    xmin,ymin,w,h=cv2.boundingRect(landmarks.astype(np.int32))
    xc=xmin+w/2
    return np.array([max(0,int(ymin-h*.35)),min(image.shape[0],int(ymin+h*1.25)),max(0,int(xc-h*.8)),min(image.shape[1],int(xc+h*.8))])


class LatestPreprocessor:
    def __init__(self,wh,detector,predictor,headpose,img_size=256,driver_flag=False):
        self.wh=wh;self.scrfd_detector=detector;self.scrfd_predictor=predictor;self.hp=headpose
        self.img_size=img_size;self.target_size=img_size+int(img_size/256)*10
        self.driver_flag=driver_flag
        self.pose_threshold=[[-70,50],[-100,100],[-70,70]]

    def detect_entry(self,index,entry):
        image=entry['imgs_data'];boxes,_=self.scrfd_detector.get_bboxes(image)
        dets=detection_box(image,boxes);entry['bounding_box_p']=dets;entry['pots']=[]
        if len(dets):
            points=self.scrfd_predictor.forward(image[dets[0]:dets[1],dets[2]:dets[3]])[0]
            entry['pots']=points
            landmarks=points+np.array([dets[2],dets[0]])[None]
            top,bottom,left,right=head_pose_box(image,landmarks)
            pose=self.hp.get_head_pose(image[top:bottom,left:right])
            if not all(lo<angle<hi for angle,(lo,hi) in zip(pose,self.pose_threshold)):
                entry['bounding_box_p']=[]
        return entry

    def crop_entry(self,index,entry,no_face):
        image=entry['imgs_data'];dets=entry['bounding_box_p']
        if len(dets)==0:
            no_face.append(index);dets=[0.,0.,0.,0.];entry['bounding_box_p']=dets
            points=self.scrfd_predictor.forward(image[:100,:100])[0]
        else:points=entry['pots']
        landmarks=points+np.array([dets[2],dets[0]])[None]
        entry['landmarks']=landmarks
        xmin,ymin,w,h=cv2.boundingRect(landmarks.astype(np.int32));xc=xmin+w/2
        left=max(0,int(xc-w/self.wh*.75));right=min(image.shape[1],int(xc+w/self.wh*.75))
        top=max(0,int(ymin-w/self.wh*.15));bottom=min(image.shape[0],int(ymin+w/self.wh*1.35))
        entry['bounding_box']=np.array([top,bottom,left,right])
        lm=np.zeros(landmarks.shape)
        lm[:,0]=self.target_size*(landmarks[:,0]-left)/(right-left)
        lm[:,1]=self.target_size*(landmarks[:,1]-top)/(bottom-top)
        crop=cv2.resize(image[top:bottom,left:right],(self.target_size,self.target_size),interpolation=cv2.INTER_CUBIC)
        if self.driver_flag:crop=cv2.cvtColor(crop,cv2.COLOR_BGR2RGB)
        entry['crop_lm']=lm;entry['crop_img']=crop
        return entry

    def process_batch(self,frames,batch_size_count=0):
        entries={i:{'imgs_data':image,'idx':i} for i,image in enumerate(frames)} if not isinstance(frames,dict) else frames
        no_face=[]
        for i,entry in entries.items():self.detect_entry(i,entry)
        for i,entry in entries.items():self.crop_entry(i,entry,no_face)
        return entries,no_face
