"""The owner's side of the licence mailbox (templates/telemetry-relay, src/licence.js) and the owner's phone (Telegram).

- The studio PULLS requests and PUSHES decisions. Nothing reaches this PC from the internet, and the signing key never leaves it:
  the relay only ever sees finished codes (public, bound to one device code).
- The relay address and its admin token live in `relay.json` inside the studio's own folder (owner-only permissions), or in the
  environment (`LS_RELAY_URL`, `LS_RELAY_TOKEN`). Never in a repository, never in a log, never in the audit.
- Telegram is the owner's notification channel (owner decision 2026-10-09). `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` come
  from the environment only (the same names the Control Center uses). The text carries the kind, the request number and the device
  code, never what a shop typed. A Telegram problem never stops a decision.
"""
from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

DEVICE = re.compile(r'^[0-9A-HJKMNP-TV-Z]{5}-[0-9A-HJKMNP-TV-Z]{5}$')
MACHINE = re.compile(r'^[0-9a-f]{64}$')
UUID = re.compile(r'^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$')
KIND_EDITION = {'trial': 'trial', 'monthly': 'standard', 'permanent': 'perpetual'}
KIND_AR = {'trial': 'تجربة 14 يوم', 'monthly': 'اشتراك شهري', 'permanent': 'تفعيل دائم'}
REASON_AR = {
    'already_used': 'الجهاز ده أو الكمبيوتر ده خد تجربة قبل كده',
    'bad_device': 'رقم الجهاز مش مظبوط',
    'bad_machine': 'بصمة الكمبيوتر مش مظبوطة',
    'unknown_product': 'البرنامج مش معروف',
    'owner_refused': 'صاحب الشركة رفض الطلب',
    'daily_cap': 'عدد التجارب النهاردة وصل الحد',
    'payment_needed': 'محتاج تأكيد الدفع وموافقتك',
    'locked': 'برنامج التراخيص مقفول (اكتب كلمة السر)',
    'review_src': 'طلبات كتير من نفس المكان: راجعها بنفسك',
    'relay_down': 'مفيش اتصال بالوسيط',
}


class RelayError(Exception):
    def __init__(self, key, text, status=0):
        super().__init__(text)
        self.key, self.status = key, status


def check_url(url: str) -> str:
    url = (url or '').strip().rstrip('/')
    parts = urlparse(url)
    local = parts.hostname in ('127.0.0.1', 'localhost', '::1')
    if parts.scheme not in ('https', 'http') or not parts.hostname or parts.username or parts.password or (parts.scheme == 'http' and not local):
        raise RelayError('relay.url', 'The relay address must start with https://')
    return url


class Relay:
    """Owner-side client. One instance per studio; the address and token are read when needed (a change takes effect at once)."""

    def __init__(self, home: Path):
        self.file = Path(home) / 'relay.json'

    # ------------------------------------------------------------ settings
    def config(self) -> dict:
        cfg = {}
        try:
            cfg = json.loads(self.file.read_text(encoding='utf-8'))
        except (OSError, ValueError):
            pass
        url = os.environ.get('LS_RELAY_URL') or cfg.get('url') or ''
        token = os.environ.get('LS_RELAY_TOKEN') or cfg.get('token') or ''
        return {'url': url, 'token': token}

    def configured(self) -> bool:
        c = self.config()
        return bool(c['url'] and c['token'])

    def save(self, url: str, token: str | None = None):
        cfg = self.config() if self.file.exists() else {}
        cfg = {'url': check_url(url), 'token': cfg.get('token', '')}
        if token:
            if not isinstance(token, str) or len(token) < 16 or len(token) > 200 or any(ch.isspace() for ch in token):
                raise RelayError('relay.token', 'The relay token is not valid.')
            cfg['token'] = token
        tmp = self.file.with_suffix('.tmp')
        fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(cfg, f)
        os.replace(tmp, self.file)

    def public(self) -> dict:
        c = self.config()
        parts = urlparse(c['url']) if c['url'] else None
        return {'configured': bool(c['url'] and c['token']), 'host': parts.netloc if parts else '', 'url': f'{parts.scheme}://{parts.netloc}' if parts else '',
                'has_token': bool(c['token'])}

    # ------------------------------------------------------------ calls
    def _call(self, method: str, path: str, body: dict | None = None, timeout: float = 15):
        c = self.config()
        if not (c['url'] and c['token']):
            raise RelayError('relay.off', 'The relay is not set up.')
        url = check_url(c['url']) + path
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(url, data=data, method=method, headers={
            'Authorization': 'Bearer ' + c['token'], 'Content-Type': 'application/json', 'User-Agent': 'LicenceStudio/1.1'})
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return json.loads(r.read().decode('utf-8') or '{}')
        except urllib.error.HTTPError as e:
            raise RelayError('relay.http', f'The relay answered {e.code}.', e.code) from None
        except (urllib.error.URLError, OSError, ValueError, TimeoutError) as e:
            raise RelayError('relay.down', f'The relay cannot be reached ({e.__class__.__name__}).') from None

    def pending(self, limit: int = 50) -> list[dict]:
        return self._call('GET', f'/licence/pending?limit={int(limit)}').get('requests') or []

    def issue(self, relay_id: str, code: str):
        return self._call('POST', '/licence/decide', {'id': relay_id, 'action': 'issue', 'code': code})

    def refuse(self, relay_id: str, reason: str = 'owner_refused'):
        return self._call('POST', '/licence/decide', {'id': relay_id, 'action': 'refuse', 'reason': reason})

    def events(self, limit: int = 100) -> list[dict]:
        return self._call('GET', f'/licence/events?limit={int(limit)}').get('events') or []


def telegram(text: str) -> bool:
    """Tell the owner's phone. Returns False (never raises) when Telegram is not set up or not reachable."""
    token = os.environ.get('TELEGRAM_BOT_TOKEN') or os.environ.get('CC_TG_BOT_TOKEN')
    chat = os.environ.get('TELEGRAM_OWNER_CHAT_ID') or os.environ.get('CC_TG_CHAT_ID')
    if not token or not chat:
        return False
    api = 'https://api.telegram.org'
    override = os.environ.get('LS_TELEGRAM_API', '')  # for tests only, and only ever a program on this PC: a bot token never goes to another host
    if override and urlparse(override).hostname in ('127.0.0.1', 'localhost', '::1'):
        api = override.rstrip('/')
    req = urllib.request.Request(f'{api}/bot{token}/sendMessage', method='POST', headers={'Content-Type': 'application/json'},
                                 data=json.dumps({'chat_id': chat, 'text': text, 'disable_web_page_preview': True}).encode())
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return 200 <= r.status < 300
    except (urllib.error.URLError, OSError, ValueError, TimeoutError):
        return False
