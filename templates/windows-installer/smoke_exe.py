"""Starts a built Al-Store.exe in a temporary practice shop and checks that it really serves the pages (used by the Windows workflow).

    python tools/smoke_exe.py "C:\\Program Files\\Al-Store\\Al-Store.exe"      (or: python tools/smoke_exe.py python server/app.py)

Optional, product-agnostic licence check on that same fresh data folder (off unless asked):

    python tools/smoke_exe.py --license-path /your/licence/status --license-state trial App.exe

``AF_SMOKE_LICENSE_PATH`` and ``AF_SMOKE_LICENSE_STATE`` are the same switches.
The route and the expected fresh state belong to the product. Stdlib only. Exit code 0 = healthy.
"""
import json
import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request


def get(port, path):
    req = urllib.request.Request(f'http://127.0.0.1:{port}{path}')
    with urllib.request.urlopen(req, timeout=10) as r:
        return r.status, dict(r.headers), r.read()


def parse_smoke_args(argv):
    """Pull optional licence switches out of the program command.

    A flag on the command line wins over the matching environment variable.
    Anything else is left for the program under test.
    """
    license_path = os.environ.get('AF_SMOKE_LICENSE_PATH') or None
    license_state = os.environ.get('AF_SMOKE_LICENSE_STATE') or None
    cmd = []
    i = 0
    while i < len(argv):
        if argv[i] == '--license-path' and i + 1 < len(argv):
            license_path = argv[i + 1]
            i += 2
            continue
        if argv[i] == '--license-state' and i + 1 < len(argv):
            license_state = argv[i + 1]
            i += 2
            continue
        cmd.append(argv[i])
        i += 1
    return license_path or None, license_state or None, cmd


def licence_status_required(payload, state=None):
    """A brand-new data folder of a sold build must say a licence is required.

    ``payload`` is the JSON object the product returns from its own status route.
    ``state`` is checked only when the caller names the fresh-install state.
    """
    if not isinstance(payload, dict) or payload.get('required') is not True:
        raise AssertionError('a fresh install must report the licence as required')
    if state is not None and payload.get('state') != state:
        raise AssertionError(
            f'a fresh install reported licence state {payload.get("state")!r}, expected {state!r}'
        )
    return payload


def main(*argv):
    license_path, license_state, cmd = parse_smoke_args(argv)
    if not cmd:
        sys.exit('usage: smoke_exe.py [--license-path /route] [--license-state name] <program> [args...]')
    if license_path and not str(license_path).startswith('/'):
        sys.exit('license path must start with /')
    out = subprocess.run([*cmd, '--version'], capture_output=True, text=True, timeout=60)
    print('version:', out.stdout.strip())
    assert out.returncode == 0 and 'Al-Store' in out.stdout, out
    s = socket.socket()
    s.bind(('127.0.0.1', 0))
    port = s.getsockname()[1]
    s.close()
    home = tempfile.mkdtemp(prefix='store-smoke-')
    log_path = os.path.join(home, 'smoke-output.txt')
    log_file = open(log_path, 'w', encoding='utf-8', errors='replace')
    proc = subprocess.Popen([*cmd, '--practice', '--no-browser', '--port', str(port), '--host', '127.0.0.1', '--home', home],
                            stdout=log_file, stderr=subprocess.STDOUT)

    def fail(message):
        log_file.flush()
        print(open(log_path, encoding='utf-8', errors='replace').read()[-4000:])
        for name in ('store.log',):
            path = os.path.join(home, name)
            if os.path.exists(path):
                print(f'--- {name} ---')
                print(open(path, encoding='utf-8', errors='replace').read()[-3000:])
        sys.exit(message)

    try:
        for _ in range(120):
            try:
                st, _, body = get(port, '/api/boot')
                break
            except OSError:
                if proc.poll() is not None:
                    fail(f'the program stopped early with code {proc.returncode}')
                time.sleep(0.5)
        else:
            fail('the program did not answer in 60 seconds')
        boot = json.loads(body)
        assert boot.get('practice') is True, boot
        st, headers, page = get(port, '/')
        assert st == 200 and b'<html' in page.lower(), 'the home page is not served'
        assert "script-src 'self'" in headers.get('Content-Security-Policy', ''), 'the security policy header is missing'
        for asset in ('/js/app.js', '/css/tokens.css', '/img/icons.svg', '/fonts/readex-pro-arabic-wght-normal.woff2', '/i18n/ar.js'):
            st, _, data = get(port, asset)
            assert st == 200 and data, f'{asset} is not served from the program folder'
        print('OK: the program starts, serves its pages and assets, practice mode is on')
        if license_path:
            try:
                st, _, raw = get(port, license_path)
            except OSError as exc:
                fail(f'licence status {license_path} did not answer: {exc}')
            if st != 200:
                fail(f'licence status {license_path} answered {st}')
            try:
                payload = json.loads(raw.decode('utf-8'))
            except (UnicodeError, json.JSONDecodeError):
                fail('licence status was not JSON')
            try:
                licence_status_required(payload, state=license_state)
            except AssertionError as exc:
                fail(str(exc))
            print('OK: a fresh data folder reports the licence as required')
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()


if __name__ == '__main__':
    main(*sys.argv[1:])
