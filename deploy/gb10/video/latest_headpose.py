"""Current original Duix WHENet wrapper; original ONNX weights unchanged."""
import cv2
import numpy as np
import onnxruntime as ort


class Headpose:
    def __init__(self, onnx_path, cpu=True, session=None):
        self.whenet_session = session or ort.InferenceSession(str(onnx_path), providers=['CPUExecutionProvider'] if cpu else ['CUDAExecutionProvider'])
        self.whenet_input_name = self.whenet_session.get_inputs()[0].name
        self.whenet_output_names = [x.name for x in self.whenet_session.get_outputs()]
        self.whenet_H = self.whenet_session.get_inputs()[0].shape[2]
        self.whenet_W = self.whenet_session.get_inputs()[0].shape[3]
        self.mean = [0.485,0.456,0.406]
        self.std = [0.229,0.224,0.225]
        self.idx_tensor_yaw = [np.array(i,dtype=np.float32) for i in range(120)]
        self.idx_tensor = [np.array(i,dtype=np.float32) for i in range(66)]

    def softmax(self, x):
        x = np.exp(x - np.max(x, axis=1, keepdims=True))
        return x / np.sum(x, axis=1, keepdims=True)

    def get_head_pose(self,image):
        image = image[:,:,::-1]
        image = cv2.resize(image,(self.whenet_W,self.whenet_H))
        rgb = np.asarray(image) / 255
        rgb = (rgb-self.mean)/self.std
        nchw = rgb.transpose(2,0,1)[np.newaxis].astype(np.float32)
        output = self.whenet_session.run(output_names=self.whenet_output_names,input_feed={self.whenet_input_name:nchw})
        yaw = np.sum(self.softmax(output[0]) * self.idx_tensor_yaw,axis=1) * 3 - 180
        pitch = np.sum(self.softmax(output[1]) * self.idx_tensor,axis=1) * 3 - 99
        roll = np.sum(self.softmax(output[2]) * self.idx_tensor,axis=1) * 3 - 99
        return roll[0],pitch[0],yaw[0]
