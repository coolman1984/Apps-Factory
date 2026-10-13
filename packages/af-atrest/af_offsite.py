"""Daily encrypted off-site backup (on by default; injectable transport)."""

from __future__ import annotations

import json
import os
from datetime import datetime
from typing import Protocol
from zoneinfo import ZoneInfo

import af_atrest as core
from af_errors import AtRestError


class Transport(Protocol):
    def post(self, url: str, headers: dict, body: bytes) -> tuple[int, bytes]: ...


DEFAULT_SETTINGS = {
    'enabled': True,
    'timezone': 'Africa/Cairo',
    'last_upload_date': None,
}


def load_settings(path: str) -> dict:
    if not os.path.isfile(path):
        return dict(DEFAULT_SETTINGS)
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    out = dict(DEFAULT_SETTINGS)
    if isinstance(data, dict):
        out.update({k: data.get(k, out[k]) for k in out})
    return out


def save_settings(path: str, settings: dict) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)) or '.', exist_ok=True)
    with open(path, 'w', encoding='utf-8') as f:
        json.dump(settings, f, sort_keys=True, indent=2)
        f.write('\n')


def business_date_today(timezone: str) -> str:
    tz = ZoneInfo(timezone)
    return datetime.now(tz).date().isoformat()


def offsite_due_today(settings: dict, timezone: str | None = None) -> bool:
    if not settings.get('enabled'):
        return False
    tz = timezone or settings.get('timezone') or DEFAULT_SETTINGS['timezone']
    today = business_date_today(tz)
    return settings.get('last_upload_date') != today


def upload_offsite_backup(
    worker_url: str,
    company_token: str,
    company_id: str,
    device_code: str,
    backup_path: str,
    transport: Transport,
) -> None:
    if not os.path.isfile(backup_path):
        raise AtRestError('ATREST_BACKUP_NOT_ENCRYPTED', backup_path)
    if not core.is_aead(backup_path):
        raise AtRestError('ATREST_BACKUP_NOT_ENCRYPTED', backup_path)
    with open(backup_path, 'rb') as f:
        body = f.read()
    url = worker_url.rstrip('/') + '/backup'
    headers = {
        'content-type': 'application/octet-stream',
        'x-af-company-token': company_token,
        'x-af-company-id': str(company_id),
        'x-af-device-code': str(device_code),
    }
    status, _ = transport.post(url, headers, body)
    if status == 401 or status == 403:
        raise AtRestError('ATREST_ESCROW_UPLOAD_REJECTED', str(status))
    if status < 200 or status >= 300:
        raise AtRestError('ATREST_ESCROW_UPLOAD_FAILED', str(status))


def run_offsite_if_due(
    settings_path: str,
    worker_url: str,
    company_token: str,
    company_id: str,
    device_code: str,
    backup_path: str,
    transport: Transport,
) -> bool:
    """Upload when due; mark settings on success. Returns True if uploaded."""
    settings = load_settings(settings_path)
    if not settings.get('enabled'):
        raise AtRestError('ATREST_OFFSITE_DISABLED')
    if not offsite_due_today(settings):
        raise AtRestError('ATREST_OFFSITE_NOT_DUE')
    upload_offsite_backup(worker_url, company_token, company_id, device_code, backup_path, transport)
    settings['last_upload_date'] = business_date_today(settings.get('timezone') or DEFAULT_SETTINGS['timezone'])
    save_settings(settings_path, settings)
    return True
