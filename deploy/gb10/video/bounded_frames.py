"""Random-access source frames with a bounded decoded block cache.

The service can use the original forward/reverse timeline without retaining
the entire reference video in RAM. Returned frames are independent copies:
face restoration and compositing must never mutate a later loop's reference.
"""
from pathlib import Path


def source_frame_index(index, count, serialize=True):
    """Original av_transfer frame order, including repeated ping-pong endpoints."""
    if index < 0 or count < 1:
        raise ValueError('Invalid frame index or source length')
    if not serialize:
        return index % count
    offset = index % (2 * count)
    return offset if offset < count else 2 * count - 1 - offset


class BoundedFrames:
    def __init__(self, path, block_size=8):
        import cv2
        if not isinstance(block_size, int) or not 1 <= block_size <= 64:
            raise ValueError('Decoded block size must be in 1..64')
        self.cv2 = cv2
        self.path = Path(path)
        self.capture = cv2.VideoCapture(str(path))
        self.count = int(self.capture.get(cv2.CAP_PROP_FRAME_COUNT))
        self.fps = float(self.capture.get(cv2.CAP_PROP_FPS))
        self.block_size = block_size
        self.cache = {}
        self.position = 0
        self.peak_cached_frames = 0
        if not self.capture.isOpened() or self.count < 1:
            self.close()
            raise ValueError('Cannot decode source video')

    def read(self, index):
        if not isinstance(index, int) or not 0 <= index < self.count:
            raise IndexError('Source frame index out of range')
        if index not in self.cache:
            start = index // self.block_size * self.block_size
            self.cache.clear()
            if self.position != start:
                if not self.capture.set(self.cv2.CAP_PROP_POS_FRAMES, start):
                    raise RuntimeError('Source decoder cannot seek to frame %d' % start)
                self.position = start
            for offset in range(start, min(start + self.block_size, self.count)):
                ok, frame = self.capture.read()
                if not ok:
                    raise ValueError('Cannot decode source frame %d' % offset)
                self.position += 1
                self.cache[offset] = frame
            self.peak_cached_frames = max(self.peak_cached_frames, len(self.cache))
        return self.cache[index].copy()

    def close(self):
        self.capture.release()
        self.cache.clear()

    def __enter__(self):
        return self

    def __exit__(self, *args):
        self.close()
