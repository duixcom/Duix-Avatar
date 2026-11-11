"""HTTP media encoding, multi-reference mapping and failure contracts."""
import asyncio
import io
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient

from duix_fish.service import create_app, InvokeRequest


class Backend:
    def __init__(self):
        self.calls = []
        self.audio = np.sin(np.arange(16000) * .1).astype(np.float32) * .2

    def synthesize(self, request, references):
        self.calls.append((request, references))
        return 16000, self.audio

    def stream(self, request, references):
        self.calls.append((request, references))
        buffer = io.BytesIO()
        sf.write(buffer, self.audio, 16000, format='WAV', subtype='PCM_16')
        data = buffer.getvalue()
        yield data[:44]
        yield data[44:16044]
        yield data[16044:]


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.root = Path(self.directory.name)
        self.backend = Backend()
        for name in ('one.wav', 'two.wav'):
            sf.write(self.root / name, self.backend.audio, 16000)
        self.app = create_app(self.root, self.backend,
                              lambda path, lang: '第一段' if path.name == 'one.wav' else '第二段',
                              '/unused-in-protocol-test')
        self.client = TestClient(self.app)
        self.request = dict(text='这是新文案', reference_audio='one.wav|||two.wav',
                            reference_text='第一段|||第二段', topP=.61, seed=4,
                            is_norm=0, normalize=False)

    def tearDown(self):
        self.client.close()
        self.directory.cleanup()

    def test_original_multi_reference_preprocess_response(self):
        original = (self.root / 'one.wav').read_bytes()
        with patch('duix_fish.service.preprocess_reference_audio',
                   return_value=[self.root / 'one.wav', self.root / 'two.wav']):
            response = self.client.post('/v1/preprocess_and_tran',
                                       json=dict(reference_audio='one.wav', lang='zh')).json()
        self.assertEqual(response['code'], 0)
        self.assertEqual(response['reference_audio_text'], '第一段|||第二段')
        self.assertEqual(response['asr_format_audio_url'].split('|||'),
                         [str(self.root / 'one.wav'), str(self.root / 'two.wav')])
        self.assertEqual((self.root / 'one.wav').read_bytes(), original)

    def test_wav_mp3_pcm_and_stream_have_audio_and_matching_references(self):
        for format in ('wav', 'mp3', 'pcm'):
            response = self.client.post('/v1/invoke', json=dict(self.request, format=format))
            self.assertEqual(response.status_code, 200, response.text[:200] if response.status_code != 200 else '')
            if format == 'pcm':
                decoded = np.frombuffer(response.content, dtype='<i2') / 32768
                self.assertEqual(len(decoded), len(self.backend.audio))
            else:
                decoded, rate = sf.read(io.BytesIO(response.content))
                self.assertEqual(rate, 16000)
                self.assertEqual(len(decoded), len(self.backend.audio))
            self.assertGreater(np.max(np.abs(decoded)), .15)
        response = self.client.post('/v1/invoke', json=dict(self.request, streaming=True))
        self.assertEqual(response.status_code, 200)
        decoded, rate = sf.read(io.BytesIO(response.content))
        self.assertEqual(len(decoded), len(self.backend.audio))
        for request, references in self.backend.calls:
            self.assertEqual(request.top_p, .61)
            self.assertEqual(request.seed, 4)
            self.assertFalse(request.normalize)
            self.assertEqual(request.is_norm, 0)
            self.assertEqual([item[1] for item in references], ['第一段', '第二段'])
            self.assertTrue(all(item[0].startswith(b'RIFF') for item in references))

    def test_rejects_mismatched_references_streaming_mp3_and_escaped_path(self):
        for payload in [dict(self.request, reference_text='一段'),
                        dict(self.request, streaming=True, format='mp3'),
                        dict(self.request, reference_audio='../outside.wav')]:
            self.assertEqual(self.client.post('/v1/invoke', json=payload).status_code, 400)
        self.assertEqual(len(self.backend.calls), 0)

    def test_model_failure_never_returns_successful_audio(self):
        with patch.object(self.backend, 'synthesize', side_effect=RuntimeError('test model failure')):
            response = self.client.post('/v1/invoke', json=self.request)
        self.assertEqual(response.status_code, 500)
        self.assertIn('test model failure', response.json()['detail'])

    def test_original_zero_token_limit_reaches_backend(self):
        response = self.client.post('/v1/invoke', json=dict(self.request, max_new_tokens=0))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(self.backend.calls[-1][0].max_new_tokens, 0)

    def test_disconnected_stream_drains_model_and_releases_next_request(self):
        resume = threading.Event()
        finished = threading.Event()

        def stream(request, references):
            try:
                yield b'header'
                if not resume.wait(2):
                    raise RuntimeError('Test did not resume the producer')
                # More than the bounded queue can hold: a disconnected client
                # must discard these chunks rather than block model completion.
                for _ in range(12):
                    yield b'audio'
            finally:
                finished.set()

        endpoint = next(route.endpoint for route in self.app.routes if route.path == '/v1/invoke')

        async def exercise():
            response = endpoint(InvokeRequest(**dict(self.request, streaming=True)))
            self.assertEqual(await anext(response.body_iterator), b'header')
            await response.body_iterator.aclose()
            resume.set()
            self.assertTrue(await asyncio.to_thread(finished.wait, 2))
            following = await asyncio.wait_for(asyncio.to_thread(
                endpoint, InvokeRequest(**self.request)), timeout=2)
            self.assertEqual(following.status_code, 200)

        with patch.object(self.backend, 'stream', side_effect=stream):
            asyncio.run(exercise())


if __name__ == '__main__':
    unittest.main()
