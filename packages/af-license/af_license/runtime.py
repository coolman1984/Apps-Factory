"""Optional helpers for commercial (distributed) builds: release-policy fail-closed and contract-upgrade grace.

Products wire these into their own licence module; af-license code signing and licence-code formats are unchanged.
"""
from __future__ import annotations

import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Iterable, Optional, Sequence

UPGRADE_GRACE_DAYS = 30
UPGRADE_PRIOR_DATA_MIN_AGE_HOURS = 24
UPGRADE_GRACE_FILE = 'commercial_upgrade_grace.json'
UPGRADE_GRACE_META_KEY = 'commercial_upgrade_grace_at'
UPGRADE_GRACE_CONSUMED_META = 'commercial_upgrade_grace_consumed'
UPGRADE_GRACE_EVER_META = 'commercial_upgrade_grace_ever'


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def iso(dt: Optional[datetime] = None) -> str:
    return (dt or utcnow()).strftime('%Y-%m-%dT%H:%M:%SZ')


def parse_iso(text) -> Optional[datetime]:
    try:
        return datetime.strptime(str(text), '%Y-%m-%dT%H:%M:%SZ')
    except (TypeError, ValueError):
        return None


def distributed_runtime(
    frozen: Optional[bool] = None,
    executable: Optional[str] = None,
    compiled: Optional[bool] = None,
) -> bool:
    """True when this process is a shipped binary, not a plain ``python`` source run.

    Nuitka marks a compiled module with ``__compiled__`` and a bytecode module
    shipped inside the same binary with ``__uncompiled__`` (Nuitka 4.3). Either
    marker means Nuitka provided this module. PyInstaller sets ``sys.frozen``
    and does not set those markers. An explicit ``frozen`` or ``compiled``
    argument overrides the automatic check.
    """
    if frozen is None:
        frozen = getattr(sys, 'frozen', False)
    if compiled is None:
        # Presence, not truthiness: Nuitka's own check is ``"__compiled__" in globals()``,
        # and 4.3's bytecode modules carry ``__uncompiled__`` instead.
        compiled = '__compiled__' in globals() or '__uncompiled__' in globals()
    if frozen or compiled:
        return True
    exe = os.path.basename(executable if executable is not None else (sys.executable or '')).lower()
    return bool(exe) and not exe.startswith('python')


@dataclass(frozen=True)
class ReleasePolicy:
    commercial_build: bool
    trusted_keys: Sequence[str]
    build_channel: str


def release_policy_without_module(distributed: bool) -> ReleasePolicy:
    """Fail-closed when ``_release_policy`` is missing: commercial distributed builds get no keys."""
    return ReleasePolicy(
        commercial_build=distributed,
        trusted_keys=(),
        build_channel='commercial' if distributed else 'source',
    )


def load_release_policy(
    module_name: str = '_release_policy',
    *,
    frozen: Optional[bool] = None,
    executable: Optional[str] = None,
) -> ReleasePolicy:
    """Import the generated release policy module, or fail-closed defaults when it is missing."""
    distributed = distributed_runtime(frozen=frozen, executable=executable)
    try:
        mod = __import__(module_name)
    except ImportError:
        return release_policy_without_module(distributed)
    commercial = bool(getattr(mod, 'COMMERCIAL_BUILD', distributed))
    keys = tuple(getattr(mod, 'TRUSTED_KEYS', ()) or ())
    channel = str(getattr(mod, 'BUILD_CHANNEL', 'commercial' if commercial else 'source'))
    return ReleasePolicy(commercial_build=commercial, trusted_keys=keys, build_channel=channel)


def _flag(value) -> bool:
    return bool(value() if callable(value) else value)


@dataclass
class UpgradeGraceResult:
    active: bool
    days_left: int
    reason: str


class UpgradeGraceEvaluator:
    """One-time edit grace after upgrading a contract office to a commercial build (not CI-test, not fresh installs)."""

    def __init__(
        self,
        *,
        policy: ReleasePolicy,
        kv: Callable[..., Optional[str]],
        data_dir: str,
        has_trusted_keys,  # bool or zero-arg callable, re-read on every evaluate()
        has_licence_code,  # bool or zero-arg callable, re-read on every evaluate()
        clock_rolled_back: Callable[[], bool],
        has_prior_office_data: Callable[[], Optional[bool]],
        read_primary_meta: Callable[[str], Optional[str]],
        write_primary_meta: Callable[[str, str], None],
        now: Callable[[], datetime] = utcnow,
        grace_days: int = UPGRADE_GRACE_DAYS,
    ):
        self.policy = policy
        self.kv = kv
        self.data_dir = data_dir
        self.has_trusted_keys = has_trusted_keys
        self.has_licence_code = has_licence_code
        self.clock_rolled_back = clock_rolled_back
        self.has_prior_office_data = has_prior_office_data
        self.read_primary_meta = read_primary_meta
        self.write_primary_meta = write_primary_meta
        self.now = now
        self.grace_days = grace_days

    def _upgrade_grace_consumed(self) -> bool:
        if self.kv('upgrade_grace_consumed'):
            return True
        return self.read_primary_meta(UPGRADE_GRACE_CONSUMED_META) == '1'

    def _mark_upgrade_grace_consumed(self) -> None:
        self.kv('upgrade_grace_consumed', '1')
        self.write_primary_meta(UPGRADE_GRACE_CONSUMED_META, '1')

    def _read_grace_started(self) -> Optional[datetime]:
        started = parse_iso(self.kv('upgrade_grace_started_at'))
        path = os.path.join(self.data_dir, UPGRADE_GRACE_FILE)
        if os.path.exists(path):
            try:
                with open(path, encoding='utf-8') as f:
                    file_started = parse_iso((json.load(f) or {}).get('started_at'))
                    if file_started and (not started or file_started < started):
                        started = file_started
            except (OSError, ValueError, TypeError):
                pass
        meta_started = parse_iso(self.read_primary_meta(UPGRADE_GRACE_META_KEY))
        if meta_started and (not started or meta_started < started):
            started = meta_started
        return started

    def _write_grace_started(self, when: datetime) -> datetime:
        existing = parse_iso(self.kv('upgrade_grace_started_at'))
        if existing:
            return existing
        payload = {'started_at': iso(when)}
        self.kv('upgrade_grace_started_at', payload['started_at'])
        path = os.path.join(self.data_dir, UPGRADE_GRACE_FILE)
        os.makedirs(self.data_dir, exist_ok=True)
        tmp = path + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(payload, f)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, path)
        self.write_primary_meta(UPGRADE_GRACE_META_KEY, payload['started_at'])
        self.write_primary_meta(UPGRADE_GRACE_EVER_META, '1')
        return when

    def evaluate(self) -> Optional[UpgradeGraceResult]:
        if (
            not self.policy.commercial_build
            or self.policy.build_channel == 'ci-test'
            or not _flag(self.has_trusted_keys)
        ):
            return None
        if _flag(self.has_licence_code):
            return None
        if self.clock_rolled_back():
            return UpgradeGraceResult(active=True, days_left=0, reason='clock_back')
        if self._upgrade_grace_consumed():
            return UpgradeGraceResult(active=True, days_left=0, reason='upgrade_grace_expired')
        started = self._read_grace_started()
        if started is None:
            if self.read_primary_meta(UPGRADE_GRACE_EVER_META) == '1' or self.kv('upgrade_grace_started_at'):
                self._mark_upgrade_grace_consumed()
                return UpgradeGraceResult(active=True, days_left=0, reason='upgrade_grace_expired')
            prior = self.has_prior_office_data()
            if prior is None:
                return None
            if not prior:
                self._mark_upgrade_grace_consumed()
                return None
            started = self._write_grace_started(self.now())
        end = started + timedelta(days=self.grace_days)
        now = self.now()
        if now < started:
            return UpgradeGraceResult(active=True, days_left=0, reason='clock_back')
        if now >= end:
            self._mark_upgrade_grace_consumed()
            return UpgradeGraceResult(active=True, days_left=0, reason='upgrade_grace_expired')
        days_left = max(0, (end.date() - now.date()).days)
        if end.date() == now.date():
            days_left = 0
        return UpgradeGraceResult(active=True, days_left=days_left, reason='upgrade_grace')

    def edits_allowed(self) -> bool:
        """True when grace gives temporary full edits (positive days left)."""
        grace = self.evaluate()
        return grace is not None and grace.days_left > 0 and grace.reason == 'upgrade_grace'


def fail_closed_status_when_no_keys(policy: ReleasePolicy, device: str) -> dict:
    """Status fragment when commercial enforcement has no trusted keys (edits blocked)."""
    return {
        'state': 'none' if policy.commercial_build else 'contract',
        'full': not policy.commercial_build,
        'enforced': bool(policy.commercial_build),
        'device': device,
        'reason': 'no_keys',
        'build_channel': policy.build_channel,
        'upgrade_grace': False,
        'upgrade_grace_days_left': None,
    }
