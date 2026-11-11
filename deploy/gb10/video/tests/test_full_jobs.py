"""Protocol, durable queue and error-recovery checks for the original port."""
import json
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from full_jobs import JobManager


class OriginalJobTests(unittest.TestCase):
    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        (self.root / 'temp').mkdir()
        for name in ('face.mp4', 'audio.wav'):
            (self.root / 'temp' / name).write_bytes(b'test input')
        self.managers = []

    def tearDown(self):
        for manager in self.managers:
            manager.close()
        self.scratch.cleanup()

    def manager(self, runner):
        manager = JobManager(self.root, runner)
        self.managers.append(manager)
        return manager

    def submit(self, manager, code='test', **overrides):
        return manager.submit(dict(code=code, video_url='face.mp4',
                                   audio_url='audio.wav', **overrides))

    def test_original_flags_envelope_metadata_and_durable_query(self):
        calls = []
        def render(video, audio, output, progress, options):
            calls.append(options)
            progress(55, 'Rendering')
            output.write_bytes(b'completed')
            return dict(duration=1.2, width=640, height=480)
        manager = self.manager(render)
        self.assertEqual(self.submit(manager, pn='0', chaofen='1', watermark_switch=1),
                         dict(code=10000, success=True, msg=10000, data={}))
        manager.queue.join()
        self.assertEqual(calls, [dict(pn=0, chaofen=1, watermark_switch=1, digital_auth=0)])
        result = manager.query('test')
        self.assertEqual(result['code'], 10000)
        self.assertTrue(result['success'])
        for key, value in dict(status=2, code='test', progress=100, result='test.mp4',
                               video_duration=1.2, width=640, height=480).items():
            self.assertEqual(result['data'][key], value)
        self.assertGreaterEqual(result['data']['cost'], 0)
        manager.close()
        restored = self.manager(render)
        self.assertEqual(restored.query('test'), result)
        self.assertEqual(restored.query('test'), result)
        self.assertEqual(restored.result_file('test').read_bytes(), b'completed')
        self.assertEqual(restored.query('missing'),
                         dict(code=10004, success=True, msg='任务不存在', data={}))

    def test_failed_job_does_not_block_next_or_publish_partial_result(self):
        calls = []
        def render(video, audio, output, progress, options):
            calls.append(output.stem)
            output.write_bytes(b'partial')
            if output.stem == 'bad':
                raise RuntimeError('No valid face')
            return dict(duration=2, width=640, height=480)
        manager = self.manager(render)
        with self.assertLogs(level='ERROR'):
            self.submit(manager, 'bad')
            self.submit(manager, 'good')
            manager.queue.join()
        self.assertEqual(calls, ['bad', 'good'])
        self.assertEqual(manager.query('bad')['data']['status'], 3)
        self.assertEqual(manager.query('good')['data']['status'], 2)
        self.assertFalse((self.root / 'temp/bad.mp4').exists())

    def test_duplicate_paths_and_interrupted_job(self):
        manager = self.manager(lambda *args, **kwargs: self.fail('Must not render'))
        (self.root / 'outside.wav').write_bytes(b'outside')
        (self.root / 'temp/escape.wav').symlink_to(self.root / 'outside.wav')
        for value in ('../outside.wav', 'escape.wav', 'http://example.com/a.wav'):
            response = manager.submit(dict(code='bad', video_url='face.mp4', audio_url=value))
            self.assertEqual(response['code'], 10002)
            self.assertFalse(response['success'])
        (self.root / 'temp/occupied.mp4').write_bytes(b'keep')
        self.assertEqual(self.submit(manager, 'occupied')['code'], 10002)
        self.assertEqual((self.root / 'temp/occupied.mp4').read_bytes(), b'keep')
        manager.close()
        (self.root / 'jobs/interrupted.json').write_text(json.dumps(
            dict(code='interrupted', data=dict(status=1, progress=43, result='', msg='Working'))))
        restarted = self.manager(lambda *args, **kwargs: self.fail('Must not rerun interrupted job'))
        self.assertEqual(restarted.query('interrupted')['data']['status'], 3)
        self.assertIn('restarted', restarted.query('interrupted')['data']['msg'])

    def test_submission_storage_failure_is_rejected_and_can_be_retried(self):
        calls = []
        def render(video, audio, output, progress, options):
            calls.append(output.stem)
            output.write_bytes(b'complete')
            return dict(duration=1, width=640, height=480)
        manager = self.manager(render)
        with patch.object(manager, '_persist', side_effect=OSError('disk full')):
            with self.assertLogs(level='ERROR'):
                result = self.submit(manager)
        self.assertEqual(result['code'], 9999)
        self.assertFalse(result['success'])
        self.assertNotIn('test', manager.jobs)
        self.assertTrue(manager.queue.empty())
        self.assertEqual(calls, [])
        self.assertIn('disk full', manager.persistence_error)
        self.assertTrue(manager.worker.is_alive())
        self.assertEqual(self.submit(manager)['code'], 10000)
        manager.queue.join()
        self.assertEqual(calls, ['test'])
        self.assertIsNone(manager.persistence_error)

    def test_terminal_storage_failure_keeps_worker_alive_and_retries_latest_state(self):
        def render(video, audio, output, progress, options):
            output.write_bytes(b'complete')
            return dict(duration=1, width=640, height=480)
        manager = self.manager(render)
        persist = manager._persist
        def fail_terminal(job):
            if job['code'] == 'first' and job['data']['status'] == 2:
                raise OSError('terminal state storage unavailable')
            persist(job)
        with patch.object(manager, '_persist', side_effect=fail_terminal):
            with self.assertLogs(level='ERROR'):
                self.submit(manager, 'first')
                self.submit(manager, 'second')
                manager.queue.join()
        self.assertTrue(manager.worker.is_alive())
        self.assertEqual(manager.query('first')['data']['status'], 2)
        self.assertEqual(manager.query('second')['data']['status'], 2)
        self.assertEqual(manager.result_file('first').read_bytes(), b'complete')
        self.assertIn('terminal state storage unavailable', manager.persistence_error)
        self.assertIn('first', manager._pending_persistence)
        # A later accepted job retries the previous terminal state once storage
        # recovers, rather than leaving a stale in-progress record on disk.
        self.submit(manager, 'third')
        manager.queue.join()
        saved = json.loads((self.root / 'jobs/first.json').read_text())
        self.assertEqual(saved['data']['status'], 2)
        self.assertIsNone(manager.persistence_error)
        self.assertFalse(manager._pending_persistence)

    def test_failed_output_cleanup_and_state_write_do_not_stop_next_job(self):
        def render(video, audio, output, progress, options):
            output.write_bytes(b'partial' if output.stem == 'bad' else b'complete')
            if output.stem == 'bad':
                raise RuntimeError('Renderer failed')
            return dict(duration=1, width=640, height=480)
        manager = self.manager(render)
        persist, unlink = manager._persist, Path.unlink
        def fail_state(job):
            if job['code'] == 'bad' and job['data']['status'] == 3:
                raise OSError('cannot save failure state')
            persist(job)
        def fail_cleanup(path, *args, **kwargs):
            if path == self.root / 'temp/bad.mp4':
                raise PermissionError('cannot delete partial file')
            return unlink(path, *args, **kwargs)
        with patch.object(manager, '_persist', side_effect=fail_state), patch.object(Path, 'unlink', fail_cleanup):
            with self.assertLogs(level='ERROR'):
                self.submit(manager, 'bad')
                self.submit(manager, 'good')
                manager.queue.join()
        self.assertTrue(manager.worker.is_alive())
        self.assertEqual(manager.query('bad')['data']['status'], 3)
        self.assertEqual(manager.query('good')['data']['status'], 2)
        self.assertTrue((self.root / 'temp/bad.mp4').exists())
        with self.assertRaises(FileNotFoundError):
            manager.result_file('bad')

    def test_repeated_identical_progress_does_not_write_again(self):
        def render(video, audio, output, progress, options):
            for _ in range(20):
                progress(55, 'Rendering')
            progress(55, 'Encoding')
            progress(56, 'Encoding')
            output.write_bytes(b'complete')
            return dict(duration=1, width=640, height=480)
        manager = self.manager(render)
        persist = manager._persist
        writes = []
        def record(job):
            writes.append((job['data']['status'], job['data']['progress'], job['data']['msg']))
            persist(job)
        with patch.object(manager, '_persist', side_effect=record):
            self.submit(manager)
            manager.queue.join()
        self.assertEqual(writes.count((1, 55, 'Rendering')), 1)
        self.assertEqual(writes.count((1, 55, 'Encoding')), 1)
        self.assertEqual(writes.count((1, 56, 'Encoding')), 1)
        self.assertEqual(manager.query('test')['data']['status'], 2)


if __name__ == '__main__':
    unittest.main()
