"""HTTP reference I/O and policy tests using an isolated local test server."""
import io
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch
import numpy as np
import soundfile as sf
from fastapi.testclient import TestClient
from duix_fish.reference_download import ReferenceDownloader, ReferenceDownloadError
from duix_fish.service import create_app


class ReferenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        buf=io.BytesIO();sf.write(buf,np.sin(np.arange(16000)*.1)*.1,16000,format='WAV')
        cls.wav=buf.getvalue()
        class Handler(BaseHTTPRequestHandler):
            def do_GET(self):
                if self.path=='/redirect':
                    self.send_response(302);self.send_header('Location','/audio.wav');self.end_headers();return
                if self.path=='/restricted':
                    self.send_response(302);self.send_header('Location','http://127.0.0.2/private');self.end_headers();return
                if self.path=='/loop':
                    self.send_response(302);self.send_header('Location','/loop');self.end_headers();return
                if self.path=='/failure':
                    self.send_error(404);return
                self.send_response(200);self.send_header('Content-Type','audio/wav')
                if self.path!='/no-length':self.send_header('Content-Length',str(len(cls.wav)))
                self.end_headers();self.wfile.write(cls.wav)
            def log_message(self,*args):pass
        cls.server=ThreadingHTTPServer(('127.0.0.1',0),Handler)
        cls.thread=threading.Thread(target=cls.server.serve_forever,daemon=True);cls.thread.start()
        cls.url=f'http://127.0.0.1:{cls.server.server_port}'

    @classmethod
    def tearDownClass(cls):
        cls.server.shutdown();cls.server.server_close();cls.thread.join()

    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name)
        self.target=self.root/'download.wav'
        self.allowed=ReferenceDownloader(allowed_networks=['127.0.0.1/32'])

    def tearDown(self):self.temp.cleanup()

    def test_real_http_and_relative_redirect_match_bytes(self):
        self.allowed.download(self.url+'/redirect',self.target)
        self.assertEqual(self.target.read_bytes(),self.wav)

    def test_private_default_and_redirect_to_untrusted_address_are_denied(self):
        with self.assertRaisesRegex(ReferenceDownloadError,'restricted'):
            ReferenceDownloader().download(self.url+'/audio.wav',self.target)
        with self.assertRaisesRegex(ReferenceDownloadError,'restricted'):
            self.allowed.download(self.url+'/restricted',self.target)
        self.assertFalse(self.target.exists())

    def test_limits_bad_status_credentials_and_existing_file(self):
        for path in ('/audio.wav','/no-length'):
            with self.assertRaisesRegex(ReferenceDownloadError,'size limit'):
                ReferenceDownloader(allowed_networks=['127.0.0.1/32'],max_bytes=300).download(self.url+path,self.target)
            self.assertFalse(self.target.exists())
        with self.assertRaisesRegex(ReferenceDownloadError,'redirect limit'):
            self.allowed.download(self.url+'/loop',self.target)
        with self.assertRaisesRegex(ReferenceDownloadError,'HTTP 404'):
            self.allowed.download(self.url+'/failure',self.target)
        secret=self.url.replace('://','://user:secret@')+'/audio.wav?token=hidden'
        with self.assertRaises(ReferenceDownloadError) as caught:self.allowed.download(secret,self.target)
        self.assertNotIn('secret',str(caught.exception));self.assertNotIn('hidden',str(caught.exception))
        self.target.write_bytes(b'preserve caller file')
        with self.assertRaises(ReferenceDownloadError):self.allowed.download(self.url+'/audio.wav',self.target)
        self.assertEqual(self.target.read_bytes(),b'preserve caller file')

    def test_ipv4_mapped_ipv6_and_metadata_are_restricted(self):
        downloader=ReferenceDownloader()
        for address in ('127.0.0.1','169.254.169.254','10.0.0.1','::1','::ffff:127.0.0.1','224.0.0.1'):
            self.assertFalse(downloader._permitted(address),address)
        self.assertTrue(downloader._permitted('8.8.8.8'))

    def test_explicit_fake_ip_proxy_does_not_allow_other_private_targets(self):
        downloader=ReferenceDownloader(allowed_networks=['198.18.0.0/15'])
        self.assertTrue(downloader._permitted('198.18.0.20'))
        for address in ('127.0.0.1','169.254.169.254','10.1.2.3'):
            self.assertFalse(downloader._permitted(address))
        with patch.dict(os.environ,{'DUIX_REFERENCE_URL_MAX_BYTES':'4096'}):
            self.assertEqual(ReferenceDownloader().max_bytes,4096)

    def test_invoke_mixed_url_and_local_and_preprocess_url(self):
        from test_full_service import Backend
        backend=Backend();(self.root/'local.wav').write_bytes(self.wav)
        app=create_app(self.root,backend,lambda path,lang:'真实接口契约测试','/unused',
                       reference_url_allow_networks=['127.0.0.1/32'])
        with TestClient(app) as client:
            response=client.post('/v1/invoke',json={'text':'测试','reference_audio':self.url+'/redirect|||local.wav',
                                                   'reference_text':'网络参考|||本地参考'})
            self.assertEqual(response.status_code,200)
            self.assertEqual(backend.calls[0][1],[(self.wav,'网络参考'),(self.wav,'本地参考')])
            self.assertFalse(list((self.root/'fish-references').glob('reference-download-*')))
            with patch('duix_fish.service.preprocess_reference_audio',side_effect=lambda source,*args:[source]):
                result=client.post('/v1/preprocess_and_tran',json={'reference_audio':self.url+'/audio.wav'}).json()
            self.assertEqual(result['code'],0)
            self.assertEqual(Path(result['asr_format_audio_url']).read_bytes(),self.wav)
            bad=client.post('/v1/invoke',json={'text':'测试','reference_audio':self.url+'/restricted',
                                              'reference_text':'参考'})
            self.assertEqual(bad.status_code,400)


if __name__=='__main__':unittest.main()
