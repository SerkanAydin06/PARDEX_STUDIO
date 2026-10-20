"""Phase 3 — PARDEX company HQ local web panel (stdlib only).

Binds to 127.0.0.1 only. Every state-changing request needs the per-launch session token
and a localhost Host/Origin, so other websites cannot drive the panel (CSRF / DNS rebinding).
Usage:  python app/hq_server.py [--port 8765] [--no-browser]
"""
import argparse
import json
import re
import secrets
import sys
import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import hq_ceo  # noqa: E402
import hq_store as store  # noqa: E402
import hq_workers as workers  # noqa: E402

STATIC = Path(__file__).resolve().parent / 'hq_static'
STATIC_FILES = {'app.css': 'text/css; charset=utf-8', 'app.js': 'application/javascript; charset=utf-8'}
MAX_BODY = 64 * 1024


class Panel:
    """Holds per-server config so tests can use temporary databases."""

    def __init__(self, db=None, queue_db=None, token=None, caller=None):
        self.db, self.queue_db = db, queue_db
        self.token = token or secrets.token_urlsafe(24)
        self.caller = caller
        self.run_state = {'running': '', 'last': None, 'error': ''}
        self.lock = threading.Lock()

    # ---- read ----
    def dashboard(self):
        try:
            workers.sync_code_jobs(self.db, self.queue_db)
        except Exception as exc:  # queue optional; dashboard must still load
            store.event('sistem', 'sync-failed', '', type(exc).__name__, self.db)
        d = store.dashboard(self.db)
        d['run'] = dict(self.run_state)
        return d

    def settings_view(self):
        s = store.settings(self.db)
        try:
            import brain
            projects = [{'path': p, **v} for p, v in brain.list_projects().items()]
        except Exception:
            projects = []
        return {'settings': s, 'projects': projects, 'tiers': store.TIERS,
                'departments': {k: {'name': v[0], 'mission': v[1], 'tier': v[3]} for k, v in store.DEPARTMENTS.items()}}

    # ---- background run ----
    def run_async(self, ident):
        with self.lock:
            if self.run_state['running']:
                raise ValueError('Şu anda başka bir iş çalışıyor')
            self.run_state.update(running=ident, error='')

        def work():
            try:
                self.run_state['last'] = workers.run_job(ident, self.db, self.queue_db, caller=self.caller)
            except Exception as exc:
                self.run_state['error'] = str(exc)[:300]
            finally:
                self.run_state['running'] = ''
        t = threading.Thread(target=work, daemon=True)
        t.start()
        return t


def _int(body, key, default=3):
    v = body.get(key, default)
    if type(v) is not int:
        raise ValueError(f'{key} tam sayı olmalı')
    return v


def make_handler(panel):
    class Handler(BaseHTTPRequestHandler):
        server_version = 'PARDEX-HQ'

        def log_message(self, *_):
            pass

        # ---- helpers ----
        def _host_ok(self):
            port = self.server.server_address[1]
            host = self.headers.get('Host', '')
            if host not in (f'127.0.0.1:{port}', f'localhost:{port}'):
                return False
            origin = self.headers.get('Origin')
            return origin in (None, f'http://127.0.0.1:{port}', f'http://localhost:{port}')

        def _send(self, code, data, ctype='application/json; charset=utf-8'):
            body = data if isinstance(data, bytes) else json.dumps(data, ensure_ascii=False, default=str).encode()
            self.send_response(code)
            self.send_header('Content-Type', ctype)
            self.send_header('Content-Length', str(len(body)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.send_header('X-Frame-Options', 'DENY')
            self.send_header('Referrer-Policy', 'no-referrer')
            self.send_header('Content-Security-Policy',
                             "default-src 'self'; img-src 'self' data:; connect-src 'self'; "
                             "frame-ancestors 'none'; base-uri 'none'; form-action 'none'")
            self.end_headers()
            self.wfile.write(body)

        def _err(self, code, msg):
            self._send(code, {'ok': False, 'error': msg})

        # ---- GET ----
        def do_GET(self):
            if not self._host_ok():
                return self._err(403, 'Yalnızca yerel erişim')
            p = self.path.split('?', 1)[0]
            if p in ('/', '/index.html'):
                html = (STATIC / 'index.html').read_text(encoding='utf-8').replace('__PARDEX_TOKEN__', panel.token)
                return self._send(200, html.encode(), 'text/html; charset=utf-8')
            if p.startswith('/static/'):
                name = p[len('/static/'):]
                if name not in STATIC_FILES:
                    return self._err(404, 'Yok')
                return self._send(200, (STATIC / name).read_bytes(), STATIC_FILES[name])
            if not p.startswith('/api/'):
                return self._err(404, 'Yok')
            if self.headers.get('X-PARDEX-Token') != panel.token:
                return self._err(403, 'Oturum anahtarı geçersiz; paneli yeniden aç')
            try:
                routes = {
                    '/api/dashboard': panel.dashboard,
                    '/api/jobs': lambda: store.jobs(path=panel.db),
                    '/api/ideas': lambda: store.ideas(panel.db),
                    '/api/ledger': lambda: store.ledger(path=panel.db),
                    '/api/events': lambda: store.events(path=panel.db),
                    '/api/goals': lambda: store.goals(path=panel.db),
                    '/api/settings': panel.settings_view,
                }
                if p not in routes:
                    return self._err(404, 'Yok')
                return self._send(200, routes[p]())
            except Exception as exc:
                return self._err(500, type(exc).__name__ + ': ' + str(exc)[:200])

        # ---- POST ----
        def do_POST(self):
            if not self._host_ok():
                return self._err(403, 'Yalnızca yerel erişim')
            if self.headers.get('X-PARDEX-Token') != panel.token:
                return self._err(403, 'Oturum anahtarı geçersiz; paneli yeniden aç')
            if not self.headers.get('Content-Type', '').startswith('application/json'):
                return self._err(415, 'JSON gerekli')
            try:
                n = int(self.headers.get('Content-Length', '0'))
            except ValueError:
                return self._err(400, 'Uzunluk hatalı')
            if not 0 <= n <= MAX_BODY:
                return self._err(413, 'İstek çok büyük')
            try:
                body = json.loads(self.rfile.read(n) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError('JSON nesnesi gerekli')
                return self._send(200, {'ok': True, 'data': self._route(self.path.split('?', 1)[0], body)})
            except (ValueError, KeyError) as exc:
                return self._err(400, str(exc)[:300])
            except Exception as exc:
                return self._err(500, type(exc).__name__ + ': ' + str(exc)[:200])

        def _route(self, p, b):
            db, qdb = panel.db, panel.queue_db
            if p == '/api/goal':
                project = store.settings(db)['default_project']
                if b.get('ai'):
                    return hq_ceo.create_from_goal_ai(str(b.get('text', '')), project, db, caller=panel.caller)
                return hq_ceo.create_from_goal(str(b.get('text', '')), project, db)
            m = re.fullmatch(r'/api/job/(J-[0-9a-f]{10})/(approve|reject|accept|run)', p)
            if m:
                ident, act = m.groups()
                if act == 'approve':
                    return workers.approve(ident, db, qdb)
                if act == 'reject':
                    return workers.reject(ident, str(b.get('reason', ''))[:300], db, qdb)
                if act == 'accept':
                    return workers.accept(ident, db, qdb)
                panel.run_async(ident)
                return {'started': ident}
            if p == '/api/dept-job':
                return workers.add_department_job(str(b.get('dept', '')), str(b.get('title', '')), db)
            if p == '/api/idea':
                return store.add_idea(str(b.get('title', '')), _int(b, 'revenue'), _int(b, 'effort'),
                                      _int(b, 'cost'), _int(b, 'fit'), 'patron', str(b.get('note', '')), db)
            m = re.fullmatch(r'/api/idea/(I-[0-9a-f]{9})/stage', p)
            if m:
                store.move_idea(m.group(1), str(b.get('stage', '')), db)
                return {'moved': m.group(1)}
            m = re.fullmatch(r'/api/idea/(I-[0-9a-f]{9})/build', p)
            if m:
                idea = next((i for i in store.ideas(db) if i['id'] == m.group(1)), None)
                if not idea:
                    raise KeyError('Fikir bulunamadı')
                store.move_idea(idea['id'], 'uretim', db)
                return hq_ceo.create_from_goal(idea['title'], store.settings(db)['default_project'], db)
            if p == '/api/ledger':
                kind = b.get('kind')
                if kind not in ('income', 'expense'):
                    raise ValueError('Yalnızca gelir veya gider girilebilir')
                return store.record(str(b.get('dept', 'finans')), kind, b.get('amount'), note=str(b.get('note', '')), path=db)
            if p == '/api/settings':
                return store.update_settings(b, db)
            if p == '/api/pause':
                return store.update_settings({'paused': bool(b.get('paused'))}, db)
            raise KeyError('Bilinmeyen işlem')
    return Handler


def serve(port=8765, open_browser=True, panel=None):
    panel = panel or Panel()
    httpd = ThreadingHTTPServer(('127.0.0.1', port), make_handler(panel))
    url = f'http://127.0.0.1:{httpd.server_address[1]}/'
    print('PARDEX Şirket Merkezi açık: ' + url)
    print('Kapatmak için bu pencereyi kapat veya Ctrl+C.')
    if open_browser:
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()


def main(argv=None):
    ap = argparse.ArgumentParser(description='PARDEX Şirket Merkezi (yerel web paneli)')
    ap.add_argument('--port', type=int, default=8765)
    ap.add_argument('--no-browser', action='store_true')
    a = ap.parse_args(argv)
    serve(a.port, not a.no_browser)


if __name__ == '__main__':
    main()
