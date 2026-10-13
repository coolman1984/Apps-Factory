"""Gentle clock and server-date protection; no runtime or lockout counters.

A PC that never goes online and keeps its date frozen is an accepted edge case.
Protected products supply independent, verified licence-time anchor callbacks.
Without them, deletion resistance is unimplemented. This module only writes its
state file and its own temporary file; anchor callbacks must only retain licence
metadata, never change customer records. ``full=False`` means that read, export
and backup must remain available.
"""
from __future__ import annotations

import json
import os
import tempfile
from datetime import date, datetime, time, timedelta, timezone, tzinfo
from pathlib import Path
from time import monotonic
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

    Naive observed datetimes mean UTC. Licence dates use ``calendar_tz`` (the
    system local zone by default), including vendor dates. I/O failures preserve
    memory. Use one writer. Both anchor callbacks are required for protection
    against removal/corruption/restoration of this file alone; the reader must
    return a verified YYYY-MM-DD or None for a confirmed fresh installation.
    """

    def __init__(self, state_path: str | os.PathLike,
                 now: Callable[[], datetime] = lambda: datetime.now(timezone.utc),
                 today: Callable[[], date] | None = None, *,
                 calendar_tz: tzinfo | None = None,
                 monotonic_now: Callable[[], float] = monotonic,
                 load_anchor: Callable[[], str | None] | None = None,
                 save_anchor: Callable[[str], None] | None = None):
        if (load_anchor is None) != (save_anchor is None):
            raise ValueError('both_anchor_callbacks_required')
        self.state_path = Path(state_path)
        self._now = now
        self._calendar_tz = calendar_tz
        self._today = today or (lambda: self._calendar_day(_utc(self._now())))
        self._monotonic = monotonic_now
        self._load_anchor = load_anchor
        self._save_anchor = save_anchor
        self._anchor_ready = load_anchor is None
        self._anchor_day: date | None = None
        self.max_seen: datetime | None = None
        self.server_day_max: date | None = None
        self._written_max: datetime | None = None
        self._pending = False
        self._retry_after: float | None = None
        self._load()
        if load_anchor is not None:
            if not self._restore_anchor():
                self._retry_after = self._monotonic() + 5

    def _calendar_day(self, moment: datetime) -> date:
        return moment.astimezone(self._calendar_tz).date()

    def _restore_anchor(self) -> bool:
        try:
            value = self._load_anchor()
            day = _day(value) if value is not None else None
        except (OSError, ValueError, TypeError):
            return False
        self._anchor_ready = True
        self._anchor_day = day
        if day is not None and (self.server_day_max is None or day > self.server_day_max):
            self.server_day_max = day
            self._pending = True
        # Historical anchors restore expiry, but cannot prove today's date and
        # must never lower a local maximum. Only a fresh server response can.
        return True

    @property
    def deletion_protected(self) -> bool:
        """Independent anchor is available and contains the latest vendor day."""
        return (self._load_anchor is not None and self._anchor_ready
                and self._anchor_day == self.server_day_max)

    def _persist(self) -> None:
        """Retry I/O after five monotonic seconds, independent of wall time.

        These are transient I/O scheduling timestamps, never usage counters.
        """
        tick = self._monotonic()
        if self._retry_after is not None and tick < self._retry_after:
            return
        success = True
        if not self._anchor_ready:
            success = self._restore_anchor()
        if (self._save_anchor is not None and self._anchor_ready
                and self.server_day_max is not None
                and self.server_day_max != self._anchor_day):
            try:
                self._save_anchor(self.server_day_max.isoformat())
                self._anchor_day = self.server_day_max
            except (OSError, ValueError, TypeError):
                success = False
        if self._pending:
            success = self._save() and success
        self._retry_after = None if success else tick + 5

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

    def _save(self) -> bool:
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
            self._pending = False
            return True
        except OSError:
            return False
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
            self._pending = True
        self._persist()

    def clock_back(self, tolerance_hours: float = 2) -> bool:
        """Rollback is a current state, cleared when the clock is corrected."""
        return (self.max_seen is not None
                and self.max_seen - _utc(self._now()) > timedelta(hours=tolerance_hours))

    def note_server_day(self, day_str: str, tolerance_hours: float = 2) -> None:
        """Accept a *fresh authenticated* vendor day in the licence calendar.

        The adapter must reject stale/replayed responses and UTC-day mismatches.
        A day older than the retained vendor day is ignored. A fresh day can
        repair an erroneous local future maximum beyond its latest possible
        instant plus tolerance. Only a server can prove this correction; it
        never lowers retained vendor expiry evidence or changes signed terms.
        """
        try:
            day = _day(day_str)
        except (ValueError, TypeError):
            return
        if self.server_day_max is not None and day < self.server_day_max:
            self._persist()
            return
        if self.server_day_max is None or day > self.server_day_max:
            self.server_day_max = day
            self._pending = True
        if self.max_seen is not None:
            try:
                end = datetime.combine(day, time.max, self._calendar_tz).astimezone(timezone.utc)
                start = datetime.combine(day, time.min, self._calendar_tz).astimezone(timezone.utc)
                if self.max_seen - end > timedelta(hours=tolerance_hours):
                    # A whole day proves only its lower bound, not an exact time.
                    self.max_seen = start
                    self._pending = True
            except (OverflowError, ValueError):
                # Extreme representable dates may overflow zone conversion.
                pass
        self._persist()

    def note_server_time(self, moment: datetime, tolerance_hours: float = 2) -> None:
        """Convert a fresh authenticated aware server instant to our calendar.

        Prefer this API when the endpoint reports UTC; never pass a bare UTC
        day to ``note_server_day`` for licences in another timezone.
        """
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise ValueError('aware_server_time_required')
        day = self._calendar_day(moment)
        if self.server_day_max is not None and day < self.server_day_max:
            self._persist()
            return
        # A timestamp also proves the time within a day, unlike a bare day.
        trusted = _utc(moment)
        if (self.max_seen is not None
                and self.max_seen - trusted > timedelta(hours=tolerance_hours)):
            self.max_seen = trusted
            self._pending = True
        self.note_server_day(day.isoformat(), tolerance_hours)

    def effective_day(self) -> date:
        """Latest local or trusted vendor day, in one licence calendar.

        Untrusted max_seen is only rollback evidence, never expiry evidence.
        A small clock correction within tolerance must not poison a paid day.
        """
        days = [self._today()]
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
        if self._load_anchor is not None and not self.deletion_protected:
            return result('anchor_unavailable', False, 'retry_licence_time_storage')
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
