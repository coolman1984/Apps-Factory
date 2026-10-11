"""Licence Studio command line.

  python -m licence_studio serve [--port 8770] [--home DIR] [--no-browser]   the owner's page (127.0.0.1 only)
  python -m licence_studio mcp                                                MCP bridge for an AI agent (stdio)
  python -m licence_studio doctor                                             check this machine
  python -m licence_studio verify CODE --product al-store [--device XXXXX-XXXXX]
  python -m licence_studio telegram-webhook [--url https://relay]    point the bot's «✅ موافق / ❌ رفض» buttons at the relay
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


def telegram_webhook(studio, a):
    """Tell Telegram to send the owner's button presses to the relay, with the secret the relay checks. The bot token (TELEGRAM_BOT_TOKEN) and
    the secret (TELEGRAM_WEBHOOK_SECRET, the same value the relay holds) come from the environment. This command never prints, stores or logs
    a secret. To make one: python -c "import secrets; print(secrets.token_urlsafe(32))" and put it in both places."""
    from .relay import RelayError, bot_token, set_webhook
    secret = os.environ.get('TELEGRAM_WEBHOOK_SECRET', '')
    if not bot_token():
        print('TELEGRAM_BOT_TOKEN is not set on this PC (the bot token from BotFather).')
        return 2
    if not secret:
        print('TELEGRAM_WEBHOOK_SECRET is not set. Make a long random value, set it here AND in the relay (wrangler secret put TELEGRAM_WEBHOOK_SECRET):')
        print('  python -c "import secrets; print(secrets.token_urlsafe(32))"')
        return 2
    url = a.url or studio.relay.config()['url']
    try:
        out = set_webhook(url, secret)
    except RelayError as e:
        print(str(e))
        return 2
    if not out or not out.get('ok'):
        print('Telegram did not accept the webhook. Check the bot token and that the relay address is a public https one.')
        return 1
    print(f'Done: the buttons now go to {url.rstrip("/")}/telegram')
    return 0


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
    w = sub.add_parser('telegram-webhook')
    w.add_argument('--url', help='the relay address; defaults to the one saved in the studio')
    w.add_argument('--home')
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
    if a.cmd == 'telegram-webhook':
        return telegram_webhook(studio, a)
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
