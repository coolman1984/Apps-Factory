"""Reference integration of af-guide: a tiny shop page plus the two server routes every product adds.

    python packages/af-guide/demo/server.py [port]      # then open http://127.0.0.1:<port>/

GET  /api/guide/state     -> af_guide.state(catalogue, role, saved record, live states)
POST /api/guide/progress  -> {"update": {...}} -> af_guide.apply(...) then save per person; 400 on a bad update
The person and role come from the product's session; here from the demo_user / demo_role cookies. Served with a strict
Content-Security-Policy (no inline script or style) so the widget is proven to work under the factory CSP.
"""
import json
import sqlite3
import sys
import threading
from http import cookies
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_guide  # noqa: E402

EXAMPLE = PKG / 'examples' / 'shop'
CAT = json.loads((EXAMPLE / 'catalogue.json').read_text(encoding='utf-8'))
FILES = {'/': (PKG / 'demo' / 'index.html', 'text/html'), '/demo.js': (PKG / 'demo' / 'demo.js', 'text/javascript'),
         '/af-guide.js': (PKG / 'af-guide.js', 'text/javascript'), '/af-guide.css': (PKG / 'af-guide.css', 'text/css')}
for name in ('catalogue', 'ar', 'en', 'ui-ar', 'ui-en'):
    FILES[f'/guide/{name}.json'] = (EXAMPLE / f'{name}.json', 'application/json')
# The strictest product policy in the fleet (Store's): no inline script or style, no eval, nothing from elsewhere.
CSP = ("default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'; connect-src 'self'; "
       "object-src 'none'; base-uri 'none'; frame-ancestors 'none'; form-action 'self'")
LOCK = threading.Lock()
DB = sqlite3.connect(':memory:', check_same_thread=False)
DB.execute(af_guide.SQL)
STATES = {}


class Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def who(self):
        c = cookies.SimpleCookie(self.headers.get('Cookie', ''))
        user = c['demo_user'].value if 'demo_user' in c else 'u1'
        role = c['demo_role'].value if 'demo_role' in c else 'cashier'
        return user, role

    def send(self, code, body, ctype='application/json'):
        data = body if isinstance(body, bytes) else json.dumps(body, ensure_ascii=False).encode()
        self.send_response(code)
        self.send_header('Content-Type', ctype + '; charset=utf-8')
        self.send_header('Content-Security-Policy', CSP)
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split('?')[0]
        if path == '/api/guide/state':
            user, role = self.who()
            with LOCK:
                rec = af_guide.load(DB, user)
            return self.send(200, af_guide.state(CAT, role, rec, STATES.get(user, set())))
        if path == '/favicon.ico':
            return self.send(204, b'', 'image/x-icon')
        if path in FILES:
            f, ctype = FILES[path]
            return self.send(200, f.read_bytes(), ctype)
        self.send(404, {'error': 'not found'})

    def do_POST(self):
        user, role = self.who()
        try:
            body = json.loads(self.rfile.read(int(self.headers.get('Content-Length') or 0)) or b'{}')
        except ValueError:
            return self.send(400, {'error': 'bad json'})
        if self.path == '/api/guide/progress':
            with LOCK:
                try:
                    rec = af_guide.apply(af_guide.load(DB, user), body.get('update'), CAT)
                except ValueError as e:
                    return self.send(400, {'error': str(e)})
                af_guide.save(DB, user, rec)
            return self.send(200, af_guide.state(CAT, role, rec, STATES.get(user, set())))
        if self.path == '/api/demo/state':
            if body.get('state') not in CAT['states']:
                return self.send(400, {'error': 'unknown state'})
            STATES.setdefault(user, set()).add(body['state'])
            return self.send(200, {'ok': True})
        self.send(404, {'error': 'not found'})


def serve(port=0):
    httpd = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    return httpd


if __name__ == '__main__':
    srv = serve(int(sys.argv[1]) if len(sys.argv) > 1 else 8765)
    print(f'http://127.0.0.1:{srv.server_address[1]}/')
    try:
        threading.Event().wait()
    except KeyboardInterrupt:
        pass
