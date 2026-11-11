"""Client for the original FunASR offline C++ websocket protocol."""
import json
import wave
from websocket import ABNF, create_connection


class OriginalFunASR:
    def __init__(self, url='ws://asr:10095', timeout=120):
        self.url, self.timeout = url, timeout

    def transcribe(self, wav_path):
        with wave.open(str(wav_path), 'rb') as audio:
            if audio.getsampwidth() != 2 or audio.getframerate() != 16000:
                raise ValueError('FunASR reference input must be 16 kHz PCM16')
            frames = audio.readframes(audio.getnframes())
        connection = create_connection(self.url, timeout=self.timeout,
                                       http_proxy_host=None, http_proxy_port=None)
        try:
            connection.send(json.dumps({
                'mode': 'offline', 'chunk_size': [5, 10, 5],
                'encoder_chunk_look_back': 4, 'decoder_chunk_look_back': 1,
                'chunk_interval': 10, 'wav_name': 'default', 'is_speaking': True,
            }))
            for offset in range(0, len(frames), 1920):
                connection.send(frames[offset:offset + 1920], ABNF.OPCODE_BINARY)
            connection.send(json.dumps({'is_speaking': False}))
            while True:
                packet = connection.recv()
                if not packet:
                    raise RuntimeError('FunASR closed before returning its transcript')
                result = json.loads(packet)
                if result.get('mode') == 'offline' and 'text' in result:
                    # Original server sets is_final=false even on the final
                    # offline result. Do not wait forever for a true flag.
                    return result['text']
        finally:
            connection.close()
