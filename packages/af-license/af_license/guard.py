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


def _parse_anchor_value(value: str) -> tuple[date | None, datetime | None, int]:
    """Plain YYYY-MM-DD or JSON with optional rollback ``max_seen`` and ``repair_gen``."""
    if value.startswith('{'):
        data = json.loads(value)
        if not isinstance(data, dict):
            raise ValueError('bad_anchor')
        day_raw = data.get('day')
        day = _day(day_raw) if day_raw is not None else None
        seen = data.get('max_seen')
        max_seen = _utc(datetime.fromisoformat(seen)) if seen is not None else None
        gen = data.get('repair_gen', 0)
        if not isinstance(gen, int) or isinstance(gen, bool) or gen < 0:
            raise ValueError('bad_anchor')
        return day, max_seen, gen
    return _day(value), None, 0


def _encode_anchor_record(day: date | None, max_seen: datetime | None,
                          repair_gen: int = 0) -> str:
    if day is None and max_seen is None:
        raise ValueError('empty_anchor')
    if day is None:
        payload = {'max_seen': max_seen.isoformat()}
    elif max_seen is None:
        return day.isoformat()
    else:
        payload = {'day': day.isoformat(), 'max_seen': max_seen.isoformat()}
    if repair_gen:
        payload['repair_gen'] = repair_gen
    if day is None:
        return json.dumps(payload, separators=(',', ':'))
    if max_seen is None:
        return day.isoformat()
    return json.dumps(payload, separators=(',', ':'))


# Licence hub business calendar; products must match ``LICENCE_CALENDAR_TZ``.
HUB_DEFAULT_CALENDAR_TZ = 'Africa/Cairo'


class ClockGuard:
    """One guard per product state file; injected clocks make checks repeatable.

    Naive observed datetimes mean UTC. Licence dates use ``calendar_tz`` (the
    system local zone by default), including vendor dates. I/O failures preserve
    memory. Use one writer. Both anchor callbacks are required for protection
    against removal/corruption/restoration of this file alone; the reader must
    return a verified YYYY-MM-DD (or JSON with optional rollback ``max_seen``)
    or None for a confirmed fresh installation.
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
        self._anchor_max_seen: datetime | None = None
        self._anchor_repair_gen = 0
        self._anchor_out_of_sync = False
        self._repair_gen = 0
        self._persist_clock_before_anchor = False
        self._pending_server_day: date | None = None
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
            if value is None:
                day, anchor_seen, anchor_gen = None, None, 0
            else:
                day, anchor_seen, anchor_gen = _parse_anchor_value(value)
        except (OSError, ValueError, TypeError, json.JSONDecodeError, OverflowError):
            return False
        self._anchor_ready = True
        self._anchor_day = day
        self._anchor_max_seen = anchor_seen
        self._anchor_repair_gen = anchor_gen
        if day is not None:
            if self.server_day_max is not None and self.server_day_max > day:
                self.server_day_max = day
                self._pending = True
            elif self.server_day_max is None or day > self.server_day_max:
                self.server_day_max = day
                self._pending = True
        if anchor_gen > self._repair_gen:
            self._repair_gen = anchor_gen
            if anchor_seen is not None:
                self.max_seen = anchor_seen
                self._pending = True
        elif self._repair_gen > anchor_gen:
            pass
        elif anchor_seen is not None:
            if self.max_seen is None or anchor_seen > self.max_seen:
                self.max_seen = anchor_seen
                self._pending = True
            elif (anchor_seen < self.max_seen and anchor_gen > 0
                  and anchor_gen == self._repair_gen):
                self.max_seen = anchor_seen
                self._pending = True
        return True

    def _sync_anchor(self) -> bool:
        if self._save_anchor is None or not self._anchor_ready:
            return True
        if self.server_day_max is None and self.max_seen is None:
            return True
        if (self._anchor_day == self.server_day_max
                and self._anchor_max_seen == self.max_seen
                and self._anchor_repair_gen == self._repair_gen):
            return True
        if (self.max_seen is not None and self._anchor_max_seen is not None
                and self.max_seen < self._anchor_max_seen
                and self._repair_gen <= self._anchor_repair_gen):
            return True
        try:
            self._save_anchor(_encode_anchor_record(self.server_day_max, self.max_seen,
                                                    self._repair_gen))
            self._anchor_day = self.server_day_max
            self._anchor_max_seen = self.max_seen
            self._anchor_repair_gen = self._repair_gen
            self._anchor_out_of_sync = False
            return True
        except (OSError, ValueError, TypeError):
            self._anchor_out_of_sync = True
            return False

    def _commit_server_day(self, day: date) -> bool:
        if self.server_day_max == day:
            return True
        if self._save_anchor is None:
            self.server_day_max = day
            self._pending = True
            return True
        if not self._anchor_ready:
            return False
        previous = self.server_day_max
        self.server_day_max = day
        if self._sync_anchor():
            self._pending_server_day = None
            self._pending = True
            return True
        self.server_day_max = previous
        self._pending_server_day = day
        self._retry_after = self._monotonic() + 5
        return False

    @property
    def deletion_protected(self) -> bool:
        """Independent anchor is available and mirrors the latest guard watermark."""
        if self._load_anchor is None or not self._anchor_ready:
            return False
        if self._anchor_out_of_sync:
            return False
        if self._anchor_day is None and self._anchor_max_seen is None:
            return False
        return (self.server_day_max == self._anchor_day
                and self.max_seen == self._anchor_max_seen
                and self._repair_gen == self._anchor_repair_gen)

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
        if self._pending_server_day is not None:
            self._commit_server_day(self._pending_server_day)
        if self._persist_clock_before_anchor:
            if self._pending:
                success = self._save() and success
            if self._save_anchor is not None and self._anchor_ready:
                success = self._sync_anchor() and success
        else:
            if self._save_anchor is not None and self._anchor_ready:
                success = self._sync_anchor() and success
            if self._pending:
                success = self._save() and success
        if success:
            self._persist_clock_before_anchor = False
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
            gen = state.get('repair_gen', 0)
            repair_gen = int(gen) if isinstance(gen, int) and not isinstance(gen, bool) else 0
            if repair_gen < 0:
                repair_gen = 0
        except (OSError, ValueError, TypeError, OverflowError, RecursionError):
            return
        self.max_seen = self._written_max = max_seen
        self.server_day_max = server_day
        self._repair_gen = repair_gen

    def _save(self) -> bool:
        temporary = None
        try:
            # A unique sibling avoids overwriting an unrelated pre-existing .tmp.
            with tempfile.NamedTemporaryFile(mode='w', encoding='utf-8',
                                             dir=self.state_path.parent,
                                             prefix=self.state_path.name + '.',
                                             suffix='.tmp', delete=False) as stream:
                temporary = stream.name
                payload = {'max_seen': self.max_seen.isoformat() if self.max_seen else None,
                           'server_day_max': (self.server_day_max.isoformat()
                                              if self.server_day_max else None)}
                if self._repair_gen:
                    payload['repair_gen'] = self._repair_gen
                json.dump(payload, stream)
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
        """Rollback is a current state, cleared when the clock is corrected.

        Default tolerance is 2 hours for licence paid-action gating. This differs
        from ``af_license.clock_rolled_back`` (24 hours), which is a separate
        document-store helper for coarse tamper hints, not the guard contract.
        """
        return (self.max_seen is not None
                and self.max_seen - _utc(self._now()) > timedelta(hours=tolerance_hours))

    def _vendor_day_floor(self, day: date, tolerance_hours: float) -> datetime | None:
        try:
            end = datetime.combine(day, time.max, self._calendar_tz).astimezone(timezone.utc)
        except (OverflowError, ValueError):
            return None
        return _utc(end + timedelta(hours=tolerance_hours))

    def _record_signed_repair_lower(self, previous: datetime | None) -> None:
        if (previous is not None and self.max_seen is not None
                and self.max_seen < previous):
            self._repair_gen += 1
            self._persist_clock_before_anchor = True

    def _signed_repair_floor(self, day: date, tolerance_hours: float,
                             pinned: datetime) -> datetime | None:
        vendor_floor = self._vendor_day_floor(day, tolerance_hours)
        if vendor_floor is None:
            return None
        return max(vendor_floor, _utc(pinned))

    def _apply_pinned_instant(self, day: date, pinned: datetime,
                              tolerance_hours: float,
                              repair_floor: datetime | None = None) -> None:
        vendor_floor = self._vendor_day_floor(day, tolerance_hours)
        if vendor_floor is None:
            return
        floor = repair_floor if repair_floor is not None else vendor_floor
        trusted = _utc(pinned)
        previous = self.max_seen
        if previous is None:
            self.max_seen = max(floor, trusted)
            self._pending = True
            return
        if previous <= floor:
            return
        repaired = max(floor, trusted)
        if previous - trusted > timedelta(hours=tolerance_hours):
            self.max_seen = repaired
            self._pending = True
            self._record_signed_repair_lower(previous)
        elif (self._calendar_day(previous) > self._calendar_day(trusted)
              and previous - trusted <= timedelta(hours=tolerance_hours)):
            self.max_seen = repaired
            self._pending = True
            self._record_signed_repair_lower(previous)

    def _repair_max_seen(self, day: date, tolerance_hours: float,
                          repair_floor: datetime | None = None) -> None:
        if self.max_seen is None:
            return
        vendor_floor = self._vendor_day_floor(day, tolerance_hours)
        if vendor_floor is None:
            return
        floor = repair_floor if repair_floor is not None else vendor_floor
        if repair_floor is not None:
            if self.max_seen <= floor:
                return
            previous = self.max_seen
            self.max_seen = floor
            self._pending = True
            self._record_signed_repair_lower(previous)
            return
        try:
            end = datetime.combine(day, time.max, self._calendar_tz).astimezone(timezone.utc)
        except (OverflowError, ValueError):
            return
        if self.max_seen <= vendor_floor:
            return
        if self.max_seen - end > timedelta(hours=tolerance_hours):
            previous = self.max_seen
            self.max_seen = vendor_floor
            self._pending = True
            self._record_signed_repair_lower(previous)

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
        self._note_authenticated_calendar_day(day, tolerance_hours, pinned_instant=None)

    def note_server_time(self, moment: datetime, tolerance_hours: float = 2) -> None:
        """Convert a fresh authenticated aware server instant to our calendar.

        Prefer this API when the endpoint reports UTC; never pass a bare UTC
        day to ``note_server_day`` for licences in another timezone. For signed
        licence-hub responses use ``note_hub_time`` instead.
        """
        if not isinstance(moment, datetime) or moment.utcoffset() is None:
            raise ValueError('aware_server_time_required')
        day = self._calendar_day(moment)
        self._note_authenticated_calendar_day(day, tolerance_hours, pinned_instant=moment)

    def note_hub_time(self, result: 'HubTimeVerifyResult',
                      tolerance_hours: float = 2) -> None:
        """Apply a verified licence-hub time result to the guard.

        Uses the clamped business ``calendar_day`` from the result (never a day
        derived from ``server_time``). ``server_time`` updates rollback evidence
        only. Non-sealing v1 results are ignored. Configure ``calendar_tz`` on
        the guard to match the hub ``LICENCE_CALENDAR_TZ`` (often
        ``ZoneInfo('Africa/Cairo')``).
        """
        from .hub_time import HubTimeVerifyResult as HubResult
        if not isinstance(result, HubResult) or not result.sealable:
            return
        try:
            day = _day(result.calendar_day)
        except (ValueError, TypeError):
            return
        pinned = None
        if result.server_time is not None:
            pinned = datetime.fromtimestamp(result.server_time, tz=timezone.utc)
        repair_floor = None
        if result.day_jump_capped and pinned is not None:
            repair_floor = self._signed_repair_floor(day, tolerance_hours, pinned)
        self._note_authenticated_calendar_day(day, tolerance_hours,
                                                pinned_instant=pinned,
                                                repair_floor=repair_floor)

    def _note_authenticated_calendar_day(self, day: date, tolerance_hours: float,
                                         pinned_instant: datetime | None,
                                         repair_floor: datetime | None = None) -> None:
        if self.server_day_max is not None and day < self.server_day_max:
            self._persist()
            return
        if self.server_day_max is None or day > self.server_day_max:
            if not self._commit_server_day(day):
                self._persist()
                return
        if pinned_instant is not None:
            self._apply_pinned_instant(day, pinned_instant, tolerance_hours,
                                         repair_floor=repair_floor)
        if repair_floor is None:
            self._repair_max_seen(day, tolerance_hours)
        else:
            self._repair_max_seen(day, tolerance_hours, repair_floor=repair_floor)
        self._persist()

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
