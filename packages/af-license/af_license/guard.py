"""Gentle clock and server-date protection; no runtime or lockout counters.

A PC that never goes online and keeps its date frozen is an accepted edge case.
Deleting this state file loses its persisted high-water marks, not the signed
licence terms. Products should also restore trusted time from their own signed
data with ``note_seen(at=...)``. This module only writes its state file and its
own temporary file; it never changes customer data. ``full=False`` means that
read, export and backup must remain available.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import TYPE_CHECKING, Callable

if TYPE_CHECKING:
    from .codes import CodeResult


def _utc(value: datetime) -> datetime:
    return (value.replace(tzinfo=timezone.utc) if value.tzinfo is None
            else value.astimezone(timezone.utc))


def _day(value: str) -> date:
    """Accept only YYYY-MM-DD, not compact or week dates."""
    if not isinstance(value, str) or len(value) != 10:
        raise ValueError('bad_day')
    result = date.fromisoformat(value)
    if result.isoformat() != value:
        raise ValueError('bad_day')
    return result


class ClockGuard:
    """One guard per product state file; injected clocks make checks repeatable.

    Naive datetimes mean UTC. I/O failures leave the in-memory marks intact and
    never raise or prevent reading customer data. Use one writer per state file.
    """

    def __init__(self, state_path: str | os.PathLike,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 today: Callable[[], date] = date.today):
        self.state_path = Path(state_path)
        self._now = now
        self._today = today
        self.max_seen: datetime | None = None
        self.server_day_max: date | None = None
        self._written_max: datetime | None = None
        self._load()

    def _load(self) -> None:
        try:
            with self.state_path.open(encoding='utf-8') as stream:
                state = json.load(stream)
            if not isinstance(state, dict):
                return
            seen = state.get('max_seen')
            server = state.get('server_day_max')
            max_seen = _utc(datetime.fromisoformat(seen)) if seen is not None else None
            server_day = _day(server) if server is not None else None
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            return
        self.max_seen = self._written_max = max_seen
        self.server_day_max = server_day

    def _save(self) -> None:
        temporary = None
        try:
            # A unique sibling avoids overwriting an unrelated pre-existing .tmp.
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.state_path.parent,
                                             prefix=self.state_path.name + '.',
                                             suffix='.tmp', delete=False) as stream:
                temporary = stream.name
                json.dump({'max_seen': self.max_seen.isoformat() if self.max_seen else None,
                           'server_day_max': (self.server_day_max.isoformat()
                                              if self.server_day_max else None)}, stream)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.state_path)
            temporary = None
            self._written_max = self.max_seen
        except OSError:
            pass
        finally:
            if temporary is not None:
                try:
                    os.unlink(temporary)
                except OSError:
                    pass

    def note_seen(self, at: datetime | None = None) -> None:
        """Advance memory every time; persist at first sight or 5 minutes forward.

        ``at`` may seed the mark from the product's own verified signed data.
        Up to five minutes of observations can be lost on restart between writes.
        """
        seen = _utc(self._now() if at is None else at)
        if self.max_seen is None or seen > self.max_seen:
            self.max_seen = seen
        if (self._written_max is None
                or self.max_seen - self._written_max >= timedelta(minutes=5)):
            self._save()

    def clock_back(self, tolerance_hours: float = 2) -> bool:
        """Rollback is a current state, cleared when the clock is corrected."""
        return (self.max_seen is not None
                and self.max_seen - _utc(self._now()) > timedelta(hours=tolerance_hours))

    def note_server_day(self, day_str: str) -> None:
        """A vendor date can advance expiry checks, never extend signed terms."""
        try:
            day = _day(day_str)
        except (ValueError, TypeError):
            return
        if self.server_day_max is None or day > self.server_day_max:
            self.server_day_max = day
            self._save()

    def effective_day(self) -> date:
        """Latest local, observed UTC or vendor calendar date."""
        days = [self._today()]
        if self.max_seen is not None:
            days.append(self.max_seen.date())
        if self.server_day_max is not None:
            days.append(self.server_day_max)
        return max(days)

    def evaluate(self, code_result: CodeResult | None, tolerance_hours: float = 2) -> dict:
        """Re-check verified terms; a paid product may choose e.g. 72 hours.

        Pass only ``codes.read_code`` results: this guard does not verify signatures.
        ``effective_day`` in the returned dictionary is an ISO date string.
        """
        self.note_seen()
        day = self.effective_day()

        def result(state: str, full: bool, reason: str = '') -> dict:
            return {'state': state, 'full': full, 'reason': reason,
                    'effective_day': day.isoformat()}

        if self.clock_back(tolerance_hours):
            return result('clock_back', False, 'clock_rolled_back')
        if code_result is None:
            return result('invalid', False, 'missing_code')
        if not code_result.valid:
            return result('invalid', False, code_result.reason)
        try:
            terms = code_result.terms
            last = terms['last_day']
            last_day = _day(last) if last is not None else None
            grace = terms.get('grace_days', 0)
            if not isinstance(grace, int) or isinstance(grace, bool) or grace < 0:
                raise ValueError('bad_grace')
            first = terms.get('first_day')
            first_day = _day(first) if first is not None else None
        except (KeyError, TypeError, ValueError):
            return result('invalid', False, 'bad_terms')
        # Compare elapsed days to avoid overflow near date.max.
        if last_day is not None and (day - last_day).days > grace:
            return result('expired', False, 'renew_to_unlock_paid_actions')
        if first_day is not None and day < first_day:
            return result('not_yet_valid', False, 'starts_later')
        if last_day is not None and day > last_day:
            return result('grace', True, 'renew_soon')
        return result('active', True)


def should_check_server(last_check_mono: float | None, now_mono: float,
                        every_hours: float = 6) -> bool:
    """Poll online on first use, after the interval, or after a clock reset.

    Inputs are monotonic seconds, not wall times. Keep the last-check value in
    process memory and reset it to None on restart. This helper makes no requests.
    """
    return (last_check_mono is None or now_mono < last_check_mono
            or now_mono - last_check_mono >= every_hours * 3600)
