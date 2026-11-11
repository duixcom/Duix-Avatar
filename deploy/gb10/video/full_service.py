"""Duix /easy service with the current original model pipeline."""
import argparse
from http.server import ThreadingHTTPServer
import logging
from urllib.parse import urlsplit

from api_compat import response
from full_jobs import JobManager
from full_runner import FullOriginalRunner
from server import Handler


class FullHandler(Handler):
    def _json(self, payload, status=200):
        if 'code' in payload and 'success' not in payload:
            payload = response(payload['code'], payload.get('msg'), payload.get('data'))
        super()._json(payload, status)

    def do_GET(self):
        if urlsplit(self.path).path in ('/health', '/healthz'):
            manager = self.server.manager
            renderer = manager.runner
            worker_alive = manager.worker.is_alive()
            healthy = renderer.full_loaded and worker_alive and manager.persistence_error is None
            self._json(dict(status='ok' if healthy else 'error', engine=renderer.engine, model_loaded=renderer.full_loaded,
                            cuda_required=True, max_duration=renderer.max_duration,
                            geometry='original current pose-aware crop', blend=renderer.blend_dynamic,
                            source_enhancement=renderer.enhancement, enhancement_runtime='TensorRT FP32',
                            bounded_frame_cache=8, source_fps=True, worker_alive=worker_alive,
                            persistence_error=manager.persistence_error), 200 if healthy else 503)
        else:
            super().do_GET()


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--root', default='/models/video')
    p.add_argument('--full-root', default='/models/video')
    p.add_argument('--data-root', default='/data')
    p.add_argument('--host', default='0.0.0.0')
    p.add_argument('--port', type=int, default=8383)
    p.add_argument('--blend', choices=('lmk', 'xseg', 'static'), default='lmk')
    args = p.parse_args()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    renderer = FullOriginalRunner(args.root, args.full_root, blend_dynamic=args.blend)
    renderer._load()
    manager = JobManager(args.data_root, renderer)
    server = ThreadingHTTPServer((args.host, args.port), FullHandler)
    server.daemon_threads = True
    server.manager = manager
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
        manager.close()


if __name__ == '__main__':
    main()
