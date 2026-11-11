"""Small static-shape TensorRT session with ORT-compatible input/output methods.

Engines are built locally from the checksum-pinned original ONNX with TF32
disabled. No half-precision conversion or replacement model is used.
"""
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import torch
import tensorrt as trt


class TensorRTSession:
    def __init__(self, engine_path):
        self.logger = trt.Logger(trt.Logger.WARNING)
        self.runtime = trt.Runtime(self.logger)
        self.engine = self.runtime.deserialize_cuda_engine(Path(engine_path).read_bytes())
        if self.engine is None:
            raise RuntimeError('Cannot deserialize the local TensorRT engine')
        self.context = self.engine.create_execution_context()
        self.inputs, self.outputs, self.buffers = [], [], {}
        for index in range(self.engine.num_io_tensors):
            name = self.engine.get_tensor_name(index)
            shape = tuple(self.engine.get_tensor_shape(name))
            if any(size < 0 for size in shape):
                raise ValueError('This session requires a static original ONNX model')
            dtype = np.dtype(trt.nptype(self.engine.get_tensor_dtype(name)))
            tdtype = torch.from_numpy(np.empty((), dtype=dtype)).dtype
            tensor = torch.empty(shape, device='cuda', dtype=tdtype)
            self.buffers[name] = tensor
            self.context.set_tensor_address(name, tensor.data_ptr())
            item = SimpleNamespace(name=name, shape=shape, dtype=dtype)
            (self.inputs if self.engine.get_tensor_mode(name) == trt.TensorIOMode.INPUT
             else self.outputs).append(item)
        self.stream = torch.cuda.Stream()

    def get_inputs(self):
        return self.inputs

    def run(self, output_names, inputs):
        if set(inputs) != {item.name for item in self.inputs}:
            raise ValueError('Unexpected TensorRT input names')
        names = [item.name for item in self.outputs] if output_names is None else output_names
        if not set(names).issubset({item.name for item in self.outputs}):
            raise ValueError('Unexpected TensorRT output names')
        with torch.cuda.stream(self.stream):
            for item in self.inputs:
                array = np.asarray(inputs[item.name])
                if array.shape != item.shape or array.dtype != item.dtype:
                    raise ValueError('Unexpected TensorRT shape or dtype for ' + item.name)
                self.buffers[item.name].copy_(torch.from_numpy(np.ascontiguousarray(array)))
            if not self.context.execute_async_v3(self.stream.cuda_stream):
                raise RuntimeError('TensorRT execution failed')
            # D2H copy is synchronized before NumPy is exposed to the caller.
            results = [self.buffers[name].cpu() for name in names]
        self.stream.synchronize()
        return [tensor.numpy() for tensor in results]
