"""Exercise actual encoded video seeking, reverse traversal and cache isolation."""
from pathlib import Path
import tempfile
import unittest

import cv2
import numpy as np

from bounded_frames import BoundedFrames, source_frame_index


class BoundedFramesTests(unittest.TestCase):
    def test_original_oracle_frame_sequence(self):
        self.assertEqual([source_frame_index(i, 3, True) for i in range(12)],
                         [0,1,2,2,1,0,0,1,2,2,1,0])
        self.assertEqual([source_frame_index(i, 3, False) for i in range(12)],
                         [0,1,2,0,1,2,0,1,2,0,1,2])
        self.assertEqual([source_frame_index(i, 1) for i in range(8)], [0]*8)

    def test_forward_reverse_loop_exact_decoding_and_independent_mutation(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / 'source.avi'
            writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*'MJPG'), 25, (96, 64))
            self.assertTrue(writer.isOpened())
            rng = np.random.default_rng(123)
            for index in range(23):
                frame = rng.integers(0, 255, (64, 96, 3), dtype=np.uint8)
                frame[:20] = index * 10
                writer.write(frame)
            writer.release()
            expected = []
            capture = cv2.VideoCapture(str(path))
            while True:
                ok, frame = capture.read()
                if not ok:
                    break
                expected.append(frame)
            capture.release()
            self.assertEqual(len(expected), 23)
            with BoundedFrames(path, block_size=4) as source:
                indices = list(range(23)) + list(range(22, -1, -1)) + [5, 22, 0, 10, 5]
                for index in indices:
                    frame = source.read(index)
                    np.testing.assert_array_equal(frame, expected[index])
                    frame[:] = 0
                    self.assertLessEqual(len(source.cache), 4)
                self.assertEqual(source.peak_cached_frames, 4)
                with self.assertRaises(IndexError):
                    source.read(23)
                with self.assertRaises(IndexError):
                    source.read(-1)
            self.assertFalse(source.capture.isOpened())


if __name__ == '__main__':
    unittest.main()
