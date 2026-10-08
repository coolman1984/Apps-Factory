"""Licence Studio command line.

  python -m licence_studio serve [--port 8770] [--home DIR] [--no-browser]   the owner's page (127.0.0.1 only)
  python -m licence_studio mcp                                                MCP bridge for an AI agent (stdio)
  python -m licence_studio doctor                                             check this machine
  python -m licence_studio verify CODE --product al-store [--device XXXXX-XXXXX]
"""
import argparse
import json
import os
import sys
import threading
import webbrowser
from pathlib import Path


def home_dir(arg=None):
    return Path(arg or os.environ.get('LS_HOME') or Path.home() / '.af-licence-studio')


def main(argv=None):
    p = argparse.ArgumentParser(prog='python -m licence_studio')
    sub = p.add_subparsers(dest='cmd', required=True)
    s = sub.add_parser('serve')
    s.add_argument('--port', type=int, default=int(os.environ.get('LS_PORT', 8770)))
    s.add_argument('--home')
    s.add_argument('--no-browser', action='store_true')
    sub.add_parser('mcp')
    sub.add_parser('doctor')
    v = sub.add_parser('verify')
    v.add_argument('code')
    v.add_argument('--product', required=True)
    v.add_argument('--device')
    v.add_argument('--home')
    a = p.parse_args(argv)
    if a.cmd == 'mcp':
        from . import mcp
        mcp.main()
        return 0
    if a.cmd == 'doctor':
        from . import mcp
        print(json.dumps(mcp.doctor(), indent=1, ensure_ascii=False))
        return 0
    from .service import Studio
    studio = Studio(home_dir(getattr(a, 'home', None)))
    if a.cmd == 'verify':
        print(json.dumps(studio.verify(a.code, a.product, a.device), indent=1, ensure_ascii=False))
        return 0
    from .server import serve
    httpd, _ = serve(studio, a.port)
    url = f'http://127.0.0.1:{a.port}/'
    print(f'Licence Studio: {url}  (data: {studio.home})')
    if not a.no_browser:
        threading.Timer(0.8, lambda: webbrowser.open(url)).start()
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == '__main__':
    sys.exit(main())
