"""Asset-free protocol tests plus opt-in differential checks against the original API."""
import ast
from enum import Enum
import hashlib
import json
import os
from pathlib import Path
from types import SimpleNamespace
import unittest

from api_compat import ParameterError, parse_submit, response, query_success, submit_success
from original_mux import mux_command


def original_api():
    configured = os.environ.get('DUIX_ORIGINAL_CODE_ROOT')
    if not configured:
        raise unittest.SkipTest('Set DUIX_ORIGINAL_CODE_ROOT for original-image differential tests')
    source = Path(configured) / 'app_local.py'
    if hashlib.sha256(source.read_bytes()).hexdigest() != '61c376361974ad19f3fcf1655f4897238ac6636d6d52b4047d5ae5cec1741d37':
        raise ValueError('Original API source checksum mismatch')
    tree = ast.parse(source.read_text())
    keep = {'EasyResponse', 'ResponseCode', 'easy_submit', 'easy_query'}
    tree.body = [node for node in tree.body
                 if isinstance(node, (ast.ClassDef, ast.FunctionDef)) and node.name in keep]
    for node in tree.body:
        if isinstance(node, ast.FunctionDef):
            node.decorator_list = []
    captured = []

    class Task:
        def __init__(self, *args):
            captured.append(args)

        def work(self):
            raise AssertionError('Unit test must never execute a service worker')

    ns = {'Enum': Enum, 'json': json, 'request': SimpleNamespace(),
          'get_run_flag': lambda: True, 'TransDhTask': Task,
          'threading': SimpleNamespace(Thread=lambda **kw: SimpleNamespace(start=lambda: None)),
          'gc': SimpleNamespace(collect=lambda: None),
          'logger': SimpleNamespace(warning=lambda *args: None),
          'traceback': SimpleNamespace(print_exc=lambda: None),
          'task_dic': {}, 'Status': Enum('Status', {'run': 1, 'success': 2, 'error': 3})}
    exec(compile(tree, str(source), 'exec'), ns)
    return ns, captured


class CompatibilityTests(unittest.TestCase):
    def test_default_playback_and_strict_switch_values(self):
        base = {'code': 'task-1', 'audio_url': 'audio.wav', 'video_url': 'video.mp4'}
        self.assertEqual(parse_submit(base).pn, 1)
        for value in (True, False, None, 1.0, 'true', '01', 2):
            self.assertEqual(parse_submit(dict(base, pn=value)).pn, 0)
        for value in ('1', 1):
            self.assertEqual(parse_submit(dict(base, pn=value)).pn, 1)
        self.assertEqual(parse_submit(dict(base, pn='')).pn, 1)

    def test_required_strings_reject_incomplete_and_mistyped_requests(self):
        for name in ('audio_url', 'video_url', 'code'):
            base = {'code': 'task-1', 'audio_url': 'audio.wav', 'video_url': 'video.mp4'}
            del base[name]
            with self.assertRaises(ParameterError):
                parse_submit(base)
            base[name] = 1
            with self.assertRaises(ParameterError):
                parse_submit(base)

    def test_original_success_and_missing_job_envelopes(self):
        self.assertEqual(submit_success(), {'code': 10000, 'success': True, 'msg': 10000, 'data': {}})
        self.assertEqual(response(10004), {'code': 10004, 'success': True, 'msg': '任务不存在', 'data': {}})
        self.assertEqual(query_success('x', 2, 100, 'x.mp4')['data']['result'], 'x.mp4')

    def test_switch_matrix_matches_original_entrypoint(self):
        ns, calls = original_api()
        base = {'code': 'task-1', 'audio_url': 'audio.wav', 'video_url': 'video.mp4'}
        variants = [None, '', 0, 1, 2, '0', '1', '01', 'true', True, False, 1.0]
        for name in ('watermark_switch', 'digital_auth', 'chaofen', 'pn'):
            for value in variants:
                payload = dict(base, **{name: value})
                ns['request'].data = json.dumps(payload).encode()
                actual = json.loads(ns['easy_submit']())
                parsed = parse_submit(payload)
                self.assertEqual(actual, submit_success())
                self.assertEqual(calls[-1], (parsed.code, parsed.audio_url, parsed.video_url,
                    parsed.watermark_switch, parsed.digital_auth, parsed.chaofen, parsed.pn))
        self.assertEqual(parse_submit(base).pn, 1)

    def test_missing_required_fields_match_original(self):
        ns, _ = original_api()
        for name in ('audio_url', 'video_url'):
            payload = {'code': 'x', 'audio_url': 'a.wav', 'video_url': 'v.mp4'}
            del payload[name]
            ns['request'].data = json.dumps(payload).encode()
            self.assertEqual(json.loads(ns['easy_submit']()), response(10002, name + '参数缺失'))

    def test_query_success_and_unknown_match_original(self):
        ns, _ = original_api()
        ns['request'].args = SimpleNamespace(to_dict=lambda: {'code': 'x'})
        self.assertEqual(json.loads(ns['easy_query']()), response(10004))
        ns['task_dic']['x'] = (ns['Status'].success, 100, 'x-r.mp4', '', 3.5, 2.4, 640, 480)
        self.assertEqual(json.loads(ns['easy_query']()), query_success('x', 2, 100, 'x-r.mp4', '',
            cost=3.5, video_duration=2.4, width=640, height=480))
        self.assertNotIn('x', ns['task_dic'])  # Original consumes terminal state.

    def test_mux_preserves_original_codec_flags_and_quotes_as_arguments(self):
        video, audio, output = 'video name;literal.mp4', '语音$(literal).wav', 'result file.mp4'
        self.assertEqual(mux_command(video, audio, output),
            ['ffmpeg', '-loglevel', 'warning', '-y', '-i', video, '-i', audio,
             '-c:a', 'aac', '-c:v', 'libx264', '-crf', '15', '-strict', '-2', output])


if __name__ == '__main__':
    unittest.main()
