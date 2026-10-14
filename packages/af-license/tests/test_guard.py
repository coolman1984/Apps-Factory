"""Clock protection with synthetic clocks and files; no customer data or network."""
import base64
import copy
import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date, datetime, time, timedelta, timezone
from pathlib import Path
from unittest.mock import Mock, patch

from cryptography.hazmat.primitives import serialization

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from af_license import ClockGuard, codes, generate_keypair
from af_license.codes import CodeResult
from af_license.guard import should_check_server
from af_license.hub_time import HubTimeVerifyResult, hub_time_message_v2, verify_hub_time


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'guard.json'
        self.wall = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
        self.local = date(2026, 10, 13)
        self.mono = 0
        self.guard = self.new_guard()

    def new_guard(self):
        return ClockGuard(self.path, now=lambda: self.wall, today=lambda: self.local,
                          calendar_tz=timezone.utc, monotonic_now=lambda: self.mono)

    def vendor_floor(self, day, tolerance_hours=2):
        end = datetime.combine(day, time.max, timezone.utc).astimezone(timezone.utc)
        return end + timedelta(hours=tolerance_hours)

    def paid(self, last='2026-10-13', grace=0, **kwargs):
        terms = {'first_day': '2026-10-01', 'last_day': last, 'grace_days': grace}
        terms.update(kwargs)
        return CodeResult(True, 'active', terms=terms)

    def assert_access(self, code, state, full, **kwargs):
        result = self.guard.evaluate(code, **kwargs)
        self.assertEqual((result['state'], result['full']), (state, full))
        self.assertEqual(set(result), {'state', 'full', 'reason', 'effective_day'})
        self.assertEqual(result['effective_day'], self.guard.effective_day().isoformat())
        return result

    def test_rollback_locks_and_forward_correction_unlocks_after_restart(self):
        code = self.paid()
        self.assert_access(code, 'active', True)
        self.wall -= timedelta(hours=3)
        self.guard = self.new_guard()
        self.assert_access(code, 'clock_back', False)
        self.wall += timedelta(hours=3)
        self.assert_access(code, 'active', True)
        self.wall += timedelta(minutes=5)
        self.assert_access(code, 'active', True)

    def test_tolerance_boundary_and_larger_paid_tolerance(self):
        self.guard.note_seen()
        self.wall -= timedelta(hours=2)
        self.assertFalse(self.guard.clock_back())
        self.wall -= timedelta(microseconds=1)
        self.assertTrue(self.guard.clock_back())
        self.assertFalse(self.guard.clock_back(72))
        self.assert_access(self.paid(), 'active', True, tolerance_hours=72)
        self.wall -= timedelta(hours=71)
        self.assert_access(self.paid(), 'clock_back', False, tolerance_hours=72)

    def test_note_seen_throttles_disk_but_keeps_latest_in_memory(self):
        with patch('af_license.guard.os.replace', wraps=__import__('os').replace) as replace:
            self.guard.note_seen()
            self.assertEqual(replace.call_count, 1)
            initial = self.path.read_bytes()
            self.wall += timedelta(minutes=4, seconds=59)
            self.guard.note_seen()
            self.assertEqual(self.guard.max_seen, self.wall)
            self.assertEqual(self.path.read_bytes(), initial)
            self.wall += timedelta(seconds=1)
            self.guard.note_seen()
            self.assertEqual(replace.call_count, 2)
            self.assertEqual(self.new_guard().max_seen, self.wall)
            self.wall -= timedelta(hours=1)
            self.guard.note_seen()
            self.assertEqual(replace.call_count, 2)
            self.assertEqual(self.guard.max_seen, self.wall + timedelta(hours=1))

    def test_vendor_day_can_only_move_trusted_expiry_forward(self):
        self.guard.note_seen()
        self.guard.note_server_day('2026-10-20')
        saved = self.path.read_bytes()
        for value in ('2026-10-19', '2026-10-20', '', 'garbage', None, 12,
                      '2026-02-30', '20261021', '2026-W43-1', '2026-1-20',
                      ' 2026-10-21', '2026-10-21T00:00:00Z', {}, []):
            with self.subTest(value=value):
                self.guard.note_server_day(value)
                self.assertEqual(self.path.read_bytes(), saved)
                self.assertEqual(self.guard.effective_day(), date(2026, 10, 20))
        self.guard.note_server_day('2026-10-21')
        self.assertEqual(self.new_guard().server_day_max, date(2026, 10, 21))
        self.assert_access(self.paid(), 'expired', False)

    def test_frozen_date_server_expiry_cannot_be_undone_by_old_server_date(self):
        code = self.paid()
        self.assert_access(code, 'active', True)
        self.guard.note_server_day('2026-10-14')
        self.assert_access(code, 'expired', False)
        self.guard.note_server_day('2026-10-01')
        self.guard = self.new_guard()
        self.assert_access(code, 'expired', False)

    def test_grace_is_inclusive_and_fixed_by_signed_terms(self):
        code = self.paid(grace=3, days_left=999999)
        original = copy.deepcopy(code)
        for day, state, full in (('2026-10-13', 'active', True),
                                 ('2026-10-14', 'grace', True),
                                 ('2026-10-16', 'grace', True),
                                 ('2026-10-17', 'expired', False)):
            self.guard.note_server_day(day)
            self.assert_access(code, state, full)
        self.assertEqual(code, original)

    def test_perpetual_never_expires_by_date_but_still_checks_rollback(self):
        code = self.paid(last=None, edition='perpetual')
        self.guard.note_server_day('9999-12-31')
        self.assert_access(code, 'active', True)
        self.wall -= timedelta(hours=3)
        self.assert_access(code, 'clock_back', False)

    def test_future_start_is_checked_against_effective_day(self):
        code = self.paid(last=None, first_day='2026-10-15')
        self.assert_access(code, 'not_yet_valid', False)
        self.guard.note_server_day('2026-10-15')
        self.assert_access(code, 'active', True)

    def test_missing_invalid_and_malformed_results_never_grant_access(self):
        self.assert_access(None, 'invalid', False)
        code = CodeResult(False, 'active', 'bad_signature', self.paid().terms)
        self.assertEqual(self.assert_access(code, 'invalid', False)['reason'], 'bad_signature')
        for terms in ({}, {'last_day': 'bad'}, {'last_day': False},
                      {'last_day': None, 'grace_days': -1},
                      {'last_day': None, 'grace_days': '3'},
                      {'last_day': None, 'grace_days': True}):
            with self.subTest(terms=terms):
                self.assert_access(CodeResult(True, 'active', terms=terms), 'invalid', False)

    def test_local_maximum_is_rollback_evidence_not_an_expiry_date(self):
        self.local = date(2026, 10, 14)
        self.guard.note_seen()
        self.assertEqual(self.guard.effective_day(), self.local)
        self.guard.note_seen(at=datetime(2026, 10, 15))
        self.assertEqual(self.guard.effective_day(), self.local)
        self.guard.note_server_day('2026-10-16')
        self.assertEqual(self.guard.effective_day(), date(2026, 10, 16))

    def test_naive_utc_and_aware_offsets_are_normalized(self):
        self.wall = self.wall.replace(tzinfo=None)
        self.guard.note_seen()
        utc = self.wall.replace(tzinfo=timezone.utc)
        self.guard.note_seen(at=utc.astimezone(timezone(timedelta(hours=3))))
        self.assertEqual(self.guard.max_seen, utc)
        self.assertEqual(self.new_guard().max_seen, utc)
        self.assertFalse(self.guard.clock_back())
        state = json.loads(self.path.read_text())
        self.assertEqual(state, {'max_seen': utc.isoformat(), 'server_day_max': None})

    def test_corrupt_state_starts_fresh_and_leaves_other_files_alone(self):
        other = self.path.with_suffix('.tmp')
        other.write_bytes(b'unrelated data')
        for value in (b'{', b'[]', b'null', b'42', b'\xff',
                      b'{"max_seen": "bad"}', b'{"max_seen": []}',
                      b'{"server_day_max": "2026-02-30"}'):
            with self.subTest(value=value):
                self.path.write_bytes(value)
                guard = self.new_guard()
                self.assertIsNone(guard.max_seen)
                self.assertIsNone(guard.server_day_max)
                self.assertEqual(self.path.read_bytes(), value)
                guard.note_seen()
                self.assertEqual(self.new_guard().max_seen, self.wall)
                self.assertEqual(other.read_bytes(), b'unrelated data')
        self.assertEqual(set(Path(self.directory.name).iterdir()), {self.path, other})

    def test_unprotected_deleted_state_loses_marks_and_makes_no_protection_claim(self):
        code = self.paid()
        self.guard.note_seen(at=datetime(2026, 10, 15))
        self.guard.note_server_day('2026-10-16')
        self.path.unlink()
        self.guard = self.new_guard()
        self.assertIsNone(self.guard.max_seen)
        self.assertIsNone(self.guard.server_day_max)
        self.assertFalse(self.guard.deletion_protected)
        self.assert_access(code, 'active', True)
        self.guard.note_seen(at=datetime(2026, 10, 15))
        self.assert_access(code, 'clock_back', False)
        self.assert_access(code, 'active', True, tolerance_hours=72)
        self.assertEqual(code.terms['last_day'], '2026-10-13')

    def test_failed_atomic_replace_keeps_old_state_and_cleans_only_own_tmp(self):
        self.guard.note_seen()
        original = self.path.read_bytes()
        other = self.path.with_suffix('.tmp')
        other.write_bytes(b'keep')
        self.wall += timedelta(minutes=5)
        with patch('af_license.guard.os.replace', side_effect=OSError('disk unavailable')):
            self.guard.note_seen()
            self.guard.note_server_day('2026-10-17')
        self.assertEqual(self.path.read_bytes(), original)
        self.assertEqual(self.guard.max_seen, self.wall)
        self.assertEqual(self.guard.effective_day(), date(2026, 10, 17))
        self.assertEqual(set(Path(self.directory.name).iterdir()), {self.path, other})
        self.mono += 5
        self.guard.note_seen()
        self.assertEqual(self.new_guard().server_day_max, date(2026, 10, 17))

    def test_mistaken_future_jump_recovers_with_fresh_server_day_and_restart(self):
        private, public, _ = generate_keypair()
        device = codes.device_code('future-clock-pc')
        signed = codes.issue_code(private, 'guard-test', 'standard', self.local,
                                  days=19, device=device)
        code = codes.read_code(signed['code'], [public], 'guard-test', device, today=self.local)
        self.assert_access(code, 'active', True)
        self.wall = self.wall.replace(year=2036)
        self.local = self.wall.date()
        self.assert_access(code, 'expired', False)
        self.wall = self.wall.replace(year=2026)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assert_access(code, 'clock_back', False)
        self.guard.note_server_day('2026-10-13')
        floor = self.vendor_floor(date(2026, 10, 13))
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assert_access(code, 'clock_back', False)
        self.guard.note_server_day('2026-10-13')
        self.assert_access(code, 'active', True)
        self.assertEqual(code.terms['last_day'], '2026-10-31')

    def test_one_hour_correction_across_midnight_does_not_poison_expiry(self):
        self.wall = datetime(2026, 10, 14, 0, 30, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.assert_access(self.paid(), 'expired', False)
        self.wall -= timedelta(hours=1)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assert_access(self.paid(), 'active', True)
        self.assertEqual(self.guard.max_seen.date(), date(2026, 10, 14))

    def test_old_server_day_cannot_repair_rollback_or_reopen_trusted_expiry(self):
        self.guard.note_server_day('2026-11-01')
        self.wall = self.wall.replace(year=2036)
        self.guard.note_seen()
        future = self.guard.max_seen
        self.wall = self.wall.replace(year=2026)
        self.guard.note_server_day('2026-10-13')
        self.assertEqual(self.guard.max_seen, future)
        self.assert_access(self.paid(), 'clock_back', False)
        self.wall = datetime(2026, 11, 1, 12, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard.note_server_day('2026-11-01')
        self.guard = self.new_guard()
        self.wall = self.vendor_floor(date(2026, 11, 1)) - timedelta(hours=1)
        self.local = self.wall.date()
        self.guard.note_server_day('2026-11-01')
        # A repaired local clock never erases a vendor-observed expiry.
        self.assert_access(self.paid(), 'expired', False)

    def test_bare_server_day_does_not_repair_midnight_only_overshoot(self):
        """REV70-2: day-only proof cannot snap max_seen before end-of-day + tolerance."""
        self.wall = datetime(2026, 10, 14, 22, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard.note_seen(at=datetime(2026, 10, 15, 0, 30, tzinfo=timezone.utc))
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_day('2026-10-14')
        self.assertEqual(self.guard.max_seen, datetime(2026, 10, 15, 0, 30, tzinfo=timezone.utc))
        self.assertTrue(self.guard.clock_back())
        self.assert_access(self.paid(last='2026-10-31'), 'clock_back', False)
        self.wall = datetime(2026, 10, 13, 23, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assertTrue(self.guard.clock_back())
        self.assert_access(self.paid(last='2026-10-31'), 'clock_back', False)

    def test_rev70_server_time_and_hub_repair_within_tolerance_past_midnight(self):
        """REV70-2 probes (UTC, 2 h tolerance): pinned instant, not bare-day snap."""
        self.wall = datetime(2026, 10, 14, 21, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard.note_seen(at=datetime(2026, 10, 15, 1, 0, tzinfo=timezone.utc))
        self.assertTrue(self.guard.clock_back())
        overshoot = datetime(2026, 10, 15, 1, 0, tzinfo=timezone.utc)
        server_instant = datetime(2026, 10, 14, 23, 0, tzinfo=timezone.utc)
        self.guard.note_server_time(server_instant)
        self.assertEqual(self.guard.max_seen, overshoot)
        self.assertTrue(self.guard.clock_back())
        self.guard = self.new_guard()
        self.assertEqual(self.guard.max_seen, overshoot)
        self.assertTrue(self.guard.clock_back())

        self.guard.note_seen(at=overshoot)
        self.assertTrue(self.guard.clock_back())
        hub_ts = int(server_instant.timestamp())
        hub = HubTimeVerifyResult('2026-10-14', hub_ts, True, 2, True)
        self.guard.note_hub_time(hub)
        self.assertEqual(self.guard.max_seen, overshoot)
        self.assertTrue(self.guard.clock_back())

    def test_rev70_paid_tolerance_does_not_unlock_via_bare_day_snap(self):
        """REV70-2: 72 h tolerance must not bare-day snap a modest multi-day overshoot."""
        tol = 72
        self.wall = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        future = self.wall + timedelta(hours=73)
        self.guard.note_seen(at=future)
        self.assertTrue(self.guard.clock_back(tol))
        self.guard.note_server_day('2026-10-14', tolerance_hours=tol)
        self.assertEqual(self.guard.max_seen, future)
        self.assertTrue(self.guard.clock_back(tol))
        self.assert_access(self.paid(last='2026-10-31'), 'clock_back', False, tolerance_hours=tol)

    def test_rollback_beyond_tolerance_survives_restart_until_clock_catches_up(self):
        self.guard.note_seen(at=datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc))
        self.wall = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assertTrue(self.guard.clock_back())
        self.assert_access(self.paid(), 'clock_back', False)
        repair_day = date(2026, 10, 13)
        self.guard.note_server_day('2026-10-13')
        floor = self.vendor_floor(repair_day)
        self.assertEqual(self.guard.max_seen, floor)
        self.assertTrue(self.guard.clock_back())
        self.guard = self.new_guard()
        self.assertEqual(self.guard.max_seen, datetime(2026, 10, 16, 12, tzinfo=timezone.utc))
        self.assertTrue(self.guard.clock_back())
        self.assert_access(self.paid(), 'clock_back', False)

    def test_one_day_forward_mistake_repaired_by_server_day_and_time(self):
        private, public, _ = generate_keypair()
        device = codes.device_code('one-day-mistake-pc')
        signed = codes.issue_code(private, 'guard-test', 'standard', self.local,
                                  days=19, device=device)
        code = codes.read_code(signed['code'], [public], 'guard-test', device, today=self.local)
        self.wall = datetime(2026, 10, 13, 0, 10, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.assert_access(code, 'active', True)
        self.wall = datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc)
        self.assert_access(code, 'active', True)
        self.wall = datetime(2026, 10, 13, 0, 10, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assert_access(code, 'clock_back', False)
        repair_instant = datetime(2026, 10, 13, 0, 10, tzinfo=timezone.utc)
        forward_seen = datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc)
        self.guard.note_server_time(repair_instant)
        self.assertEqual(self.guard.max_seen, forward_seen)
        self.wall = forward_seen - timedelta(hours=2)
        self.guard = self.new_guard()
        self.assert_access(code, 'active', True)
        self.wall = datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc)
        self.guard.note_seen()
        self.wall = datetime(2026, 10, 13, 0, 10, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assert_access(code, 'clock_back', False)
        self.guard.note_server_time(repair_instant)
        self.assertEqual(self.guard.max_seen, forward_seen)
        self.wall = forward_seen - timedelta(hours=2)
        self.guard = self.new_guard()
        self.assert_access(code, 'active', True)

    def test_failed_server_only_save_retries_with_frozen_wall_time(self):
        self.guard.note_seen()
        original = self.path.read_bytes()
        with patch('af_license.guard.os.replace', side_effect=OSError('temporary failure')) as replace:
            self.guard.note_server_day('2026-11-01')
            for _ in range(10):
                self.guard.note_seen()
                self.guard.note_server_day('2026-11-01')
            self.assertEqual(replace.call_count, 1)
        self.assertEqual(self.path.read_bytes(), original)
        self.assert_access(self.paid(), 'expired', False)
        self.mono += 5
        self.guard.note_server_day('2026-11-01')
        self.guard = self.new_guard()
        self.assert_access(self.paid(), 'expired', False)

    def test_calendar_boundaries_with_real_signed_codes_and_server_instants(self):
        private, public, _ = generate_keypair()
        device = codes.device_code('calendar-test-pc')
        for hours, instant, local_day in (
                (-4, datetime(2026, 10, 14, 1, tzinfo=timezone.utc), date(2026, 10, 13)),
                (3, datetime(2026, 10, 12, 21, tzinfo=timezone.utc), date(2026, 10, 13))):
            with self.subTest(offset=hours):
                zone = timezone(timedelta(hours=hours))
                self.wall = instant
                self.path = Path(self.directory.name) / f'zone{hours}.json'
                self.guard = ClockGuard(self.path, now=lambda: self.wall, calendar_tz=zone)
                signed = codes.issue_code(private, 'calendar-test', 'standard', local_day,
                                          days=1, grace_days=1, device=device)
                code = codes.read_code(signed['code'], [public], 'calendar-test', device, today=local_day)
                self.assert_access(code, 'active', True)
                self.guard.note_server_time(self.wall)
                self.assert_access(code, 'active', True)
                self.assertEqual(self.guard.effective_day(), local_day)
                future_signed = codes.issue_code(private, 'calendar-test', 'perpetual',
                                                 date(2026, 10, 14), days=1, device=device)
                future = codes.read_code(future_signed['code'], [public], 'calendar-test',
                                         device, today=local_day)
                self.assert_access(future, 'not_yet_valid', False)
                self.wall = datetime(2026, 10, 14, tzinfo=zone).astimezone(timezone.utc)
                self.assert_access(code, 'grace', True)
                self.assert_access(future, 'active', True)
                self.wall = datetime(2026, 10, 14, 23, 59, 59, tzinfo=zone).astimezone(timezone.utc)
                self.guard.note_server_time(self.wall)
                self.assert_access(code, 'grace', True)
                self.wall += timedelta(seconds=1)
                self.guard.note_server_time(self.wall)
                self.assert_access(code, 'expired', False)

    def test_server_instant_requires_timezone(self):
        for value in (datetime(2026, 10, 13), '2026-10-13', None):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.guard.note_server_time(value)

    def test_fresh_server_instant_repairs_same_day_future_time(self):
        day = self.wall.date()
        floor = self.vendor_floor(day)
        repair_instant = self.wall
        self.guard.note_seen(at=floor + timedelta(hours=3))
        self.assert_access(self.paid(), 'clock_back', False)
        self.guard.note_server_time(repair_instant)
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.local = self.wall.date()
        self.guard = self.new_guard()
        overshoot = floor + timedelta(hours=3)
        self.assertEqual(self.guard.max_seen, overshoot)
        self.guard.note_server_time(repair_instant)
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.local = self.wall.date()
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)

    def anchor_guard(self):
        """Synthetic vendor signs an independent device-bound time anchor.

        Real adapters retain the authenticated response; they hold no private key.
        No customer database is used by this fixture.
        """
        if not hasattr(self, 'anchor_path'):
            self.anchor_path = Path(self.directory.name) / 'verified-licence-time.json'
            self.anchor_private, self.anchor_public, _ = generate_keypair()
            self.anchor_device = codes.device_code('independent-anchor-pc')

        def load():
            if not self.anchor_path.exists():
                return None  # fixture's confirmed fresh installation
            record = json.loads(self.anchor_path.read_text())
            max_seen = record.get('max_seen') if isinstance(record, dict) else None
            if isinstance(record, dict) and 'signed' not in record and max_seen:
                return json.dumps({'max_seen': max_seen})
            signed = record['signed'] if isinstance(record, dict) and 'signed' in record else record
            result = codes.read_code(signed['code'], [self.anchor_public], 'anchor-test',
                                     self.anchor_device, today=self.local)
            if not result.valid:
                raise ValueError('unverified_anchor')
            day = result.terms['issued']
            if max_seen:
                return json.dumps({'day': day, 'max_seen': max_seen})
            return day

        def save(payload):
            # Simulates receiving and retaining a genuinely signed server proof.
            if payload.startswith('{'):
                data = json.loads(payload)
                day = data.get('day')
                max_seen = data.get('max_seen')
            else:
                day, max_seen = payload, None
            if day is None:
                self.anchor_path.write_text(json.dumps({'max_seen': max_seen}))
                return
            signed = codes.issue_code(self.anchor_private, 'anchor-test', 'standard',
                                      date(2026, 10, 1), days=1, device=self.anchor_device,
                                      issued=date.fromisoformat(day))
            self.anchor_path.write_text(json.dumps({'signed': signed, 'max_seen': max_seen}))

        return ClockGuard(self.path, now=lambda: self.wall, today=lambda: self.local,
                          calendar_tz=timezone.utc, monotonic_now=lambda: self.mono,
                          load_anchor=load, save_anchor=save)

    def test_authenticated_instant_never_lowers_max_seen_below_pin_same_day(self):
        self.wall = datetime(2026, 10, 14, 10, tzinfo=timezone.utc)
        self.local = self.wall.date()
        future = datetime(2026, 10, 14, 20, tzinfo=timezone.utc)
        self.guard.note_seen(at=future)
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_time(datetime(2026, 10, 14, 18, tzinfo=timezone.utc))
        self.assertEqual(self.guard.max_seen, future)
        self.assertTrue(self.guard.clock_back())
        self.wall = datetime(2026, 10, 13, 23, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.assertTrue(self.guard.clock_back())

    def test_anchor_mirrors_max_seen_before_vendor_day(self):
        self.guard = self.anchor_guard()
        self.assertFalse(self.guard.deletion_protected)
        seen = datetime(2026, 10, 15, 8, tzinfo=timezone.utc)
        self.guard.note_seen(at=seen)
        self.assertTrue(self.guard.deletion_protected)
        self.assertIsNone(self.guard.server_day_max)
        record = json.loads(self.anchor_path.read_text())
        self.assertEqual(record['max_seen'], seen.isoformat())
        self.path.unlink()
        self.wall = seen
        self.local = self.wall.date()
        self.guard = self.anchor_guard()
        self.assertEqual(self.guard.max_seen, seen)
        self.assertFalse(self.guard.clock_back())

    def test_note_hub_time_uses_clamped_day_and_ignores_v1(self):
        private, pub_b64, kid = generate_keypair()
        trusted = {kid: pub_b64}
        private_key = serialization.load_pem_private_key(private, password=None)

        def b64url(raw):
            return base64.urlsafe_b64encode(raw).decode().rstrip('=')
        server_time = 1_700_000_500
        far_day = '2026-10-30'
        nonce = 'hub-guard01'
        msg = hub_time_message_v2(far_day, server_time, kid, nonce)
        data = {
            'calendar_day': far_day,
            'kid': kid,
            'server_time': server_time,
            'sig2': b64url(private_key.sign(msg)),
            'signed': True,
            'nonce': nonce,
        }
        sealed = '2026-10-14'
        result = verify_hub_time(
            data, trusted, sealed_day=sealed, max_jump_days=7, nonce=nonce,
            last_server_time=1_700_000_100,
        )
        self.assertEqual(result, HubTimeVerifyResult('2026-10-21', server_time, True, 2, True))
        self.guard.note_hub_time(result)
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 21))
        self.assertNotEqual(self.guard.server_day_max, date(2026, 10, 30))
        wrong = HubTimeVerifyResult(sealed, None, False, 1, False)
        self.guard.note_hub_time(wrong)
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 21))

    def _hub_day_jump_capped_result(self, far_day, sealed_day, server_dt):
        private, pub_b64, kid = generate_keypair()
        trusted = {kid: pub_b64}
        private_key = serialization.load_pem_private_key(private, password=None)

        def b64url(raw):
            return base64.urlsafe_b64encode(raw).decode().rstrip('=')

        server_time = int(server_dt.timestamp())
        nonce = 'hub-cap01'
        msg = hub_time_message_v2(far_day, server_time, kid, nonce)
        data = {
            'calendar_day': far_day,
            'kid': kid,
            'server_time': server_time,
            'sig2': b64url(private_key.sign(msg)),
            'signed': True,
            'nonce': nonce,
        }
        result = verify_hub_time(
            data, trusted, sealed_day=sealed_day, max_jump_days=7, nonce=nonce,
        )
        self.assertTrue(result.day_jump_capped)
        return result

    def test_note_hub_time_day_jump_capped_never_lowers_below_server_time(self):
        """Reviewer example: clamped hub day must not snap max_seen below server_time."""
        server_dt = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)
        self.wall = server_dt
        self.local = self.wall.date()
        self.guard.note_seen(at=server_dt)
        result = self._hub_day_jump_capped_result('2026-12-01', '2026-09-14', server_dt)
        self.assertEqual(result.calendar_day, '2026-09-21')
        self.guard.note_hub_time(result)
        self.assertEqual(self.guard.server_day_max, date(2026, 9, 21))
        self.assertGreaterEqual(self.guard.max_seen, server_dt)
        self.wall = datetime(2026, 9, 22, 15, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.assertTrue(self.guard.clock_back())

        server_dt_oct = datetime(2026, 12, 1, 12, 0, tzinfo=timezone.utc)
        self.wall = server_dt_oct
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.guard.note_seen(at=server_dt_oct)
        result_oct = self._hub_day_jump_capped_result('2026-12-01', '2026-10-14', server_dt_oct)
        self.assertEqual(result_oct.calendar_day, '2026-10-21')
        self.guard.note_hub_time(result_oct)
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 21))
        self.assertGreaterEqual(self.guard.max_seen, server_dt_oct)
        self.wall = datetime(2026, 10, 22, 15, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.assertTrue(self.guard.clock_back())

    def test_restart_after_in_run_signed_repair_restores_disk_watermark(self):
        self.guard = self.anchor_guard()
        future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=future)
        floor = self.vendor_floor(date(2026, 10, 14))
        self.guard.note_server_time(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.assertFalse(self.guard.clock_back())
        clock_before = json.loads(self.path.read_text())
        anchor_before = json.loads(self.anchor_path.read_text())
        self.assertEqual(clock_before['max_seen'], future.isoformat())
        self.guard = self.anchor_guard()
        self.assertEqual(self.guard.max_seen, future)
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_time(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.assertFalse(self.guard.clock_back())
        self.assertEqual(json.loads(self.path.read_text())['max_seen'], clock_before['max_seen'])
        self.assertEqual(json.loads(self.anchor_path.read_text())['max_seen'],
                         anchor_before['max_seen'])

    def test_in_run_signed_repair_clears_clock_back_without_lowering_files(self):
        self.guard = self.anchor_guard()
        future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=future)
        clock_before = json.loads(self.path.read_text())
        anchor_before = json.loads(self.anchor_path.read_text())
        floor = self.vendor_floor(date(2026, 10, 14))
        self.guard.note_server_time(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.local = self.wall.date()
        self.assertFalse(self.guard.clock_back())
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        self.assertEqual(json.loads(self.path.read_text())['max_seen'], clock_before['max_seen'])
        self.assertEqual(json.loads(self.anchor_path.read_text())['max_seen'],
                         anchor_before['max_seen'])
        self.guard.note_seen()
        self.assertEqual(self.guard.max_seen, floor)
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)

    def test_reviewer_clock_file_tamper_cannot_lower_below_anchor(self):
        self.guard = self.anchor_guard()
        future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=future)
        tampered = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
        self.path.write_text(json.dumps({
            'max_seen': tampered.isoformat(),
            'server_day_max': None,
            'extra': 'tamper',
        }))
        anchor_before = json.loads(self.anchor_path.read_text())
        self.wall = tampered
        self.local = self.wall.date()
        self.guard = self.anchor_guard()
        self.assertEqual(self.guard.max_seen, future)
        self.assert_access(self.paid(), 'clock_back', False)
        anchor_after = json.loads(self.anchor_path.read_text())
        self.assertEqual(anchor_after['max_seen'], anchor_before['max_seen'])

    def test_reviewer_null_clock_max_seen_restores_anchor_before_evaluate(self):
        self.guard = self.anchor_guard()
        future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=future)
        tampered = datetime(2026, 10, 11, 12, 0, tzinfo=timezone.utc)
        self.path.write_text(json.dumps({
            'max_seen': None,
            'server_day_max': None,
            'extra': 'tamper',
        }))
        anchor_before = json.loads(self.anchor_path.read_text())
        self.wall = tampered
        self.local = self.wall.date()
        self.guard = self.anchor_guard()
        self.assertEqual(self.guard.max_seen, future)
        self.assert_access(self.paid(), 'clock_back', False)
        anchor_after = json.loads(self.anchor_path.read_text())
        self.assertEqual(anchor_after['max_seen'], anchor_before['max_seen'])

    def test_fresh_signed_instant_seeds_max_seen_not_vendor_floor(self):
        instant = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.wall = instant
        self.local = instant.date()
        guard = self.new_guard()
        guard.note_server_time(instant)
        self.assertEqual(guard.max_seen, instant)
        self.assertFalse(guard.clock_back())

    def test_fresh_hub_time_seeds_max_seen_not_vendor_floor(self):
        instant = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.wall = instant
        self.local = instant.date()
        private, pub_b64, kid = generate_keypair()
        trusted = {kid: pub_b64}
        private_key = serialization.load_pem_private_key(private, password=None)

        def b64url(raw):
            return base64.urlsafe_b64encode(raw).decode().rstrip('=')

        server_time = int(instant.timestamp())
        day = '2026-10-14'
        nonce = 'hub-seed01'
        msg = hub_time_message_v2(day, server_time, kid, nonce)
        data = {
            'calendar_day': day,
            'kid': kid,
            'server_time': server_time,
            'sig2': b64url(private_key.sign(msg)),
            'signed': True,
            'nonce': nonce,
        }
        result = verify_hub_time(
            data, trusted, sealed_day=day, max_jump_days=7, nonce=nonce,
        )
        guard = self.new_guard()
        guard.note_hub_time(result)
        self.assertEqual(guard.max_seen, instant)
        self.assertFalse(guard.clock_back())

    def test_signed_time_clears_stuck_clock_back(self):
        forward_seen = datetime(2026, 10, 14, 1, 0, tzinfo=timezone.utc)
        repair_instant = datetime(2026, 10, 13, 0, 10, tzinfo=timezone.utc)
        self.guard.note_seen(at=forward_seen)
        self.wall = repair_instant
        self.local = self.wall.date()
        self.guard = self.new_guard()
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_time(repair_instant)
        self.assertEqual(self.guard.max_seen, forward_seen)
        self.wall = forward_seen - timedelta(hours=2)
        self.assertFalse(self.guard.clock_back())
        self.assert_access(self.paid(), 'active', True)

    def test_independent_verified_anchor_recovers_deleted_corrupt_and_old_state(self):
        self.guard = self.anchor_guard()
        self.assertFalse(self.guard.deletion_protected)
        self.assert_access(self.paid(), 'active', True)
        self.assertTrue(self.guard.deletion_protected)
        old = self.path.read_bytes()
        self.guard.note_server_day('2026-11-01')
        self.assertTrue(self.guard.deletion_protected)
        for replacement in (None, b'{broken', old):
            with self.subTest(replacement=replacement):
                if replacement is None:
                    self.path.unlink()
                else:
                    self.path.write_bytes(replacement)
                self.guard = self.anchor_guard()
                self.assert_access(self.paid(), 'expired', False)
                self.assertTrue(self.guard.deletion_protected)
                self.assertEqual(self.new_guard().server_day_max, date(2026, 11, 1))

    def test_anchor_is_saved_even_if_clock_file_replace_fails(self):
        self.guard = self.anchor_guard()
        self.guard.note_seen()
        with patch('af_license.guard.os.replace', side_effect=OSError('clock write failed')):
            self.guard.note_server_day('2026-11-01')
        self.path.unlink()
        self.guard = self.anchor_guard()
        self.assert_access(self.paid(), 'expired', False)

    def test_anchor_read_failure_keeps_paid_actions_safe_and_recovers(self):
        self.guard = self.anchor_guard()
        self.anchor_path.write_text('{broken')
        self.guard = self.anchor_guard()
        self.assert_access(self.paid(), 'anchor_unavailable', False)
        self.assertFalse(self.guard.deletion_protected)
        # Valid metadata becomes readable again; no usage/lockout counter.
        self.anchor_path.write_text(json.dumps(codes.issue_code(
            self.anchor_private, 'anchor-test', 'standard', self.local, days=1,
            device=self.anchor_device, issued=self.local)))
        self.mono += 5
        self.assert_access(self.paid(), 'active', True)
        self.assertTrue(self.guard.deletion_protected)

    def test_unverified_anchor_is_not_accepted(self):
        self.guard = self.anchor_guard()
        self.guard.note_server_day('2026-10-13')
        record = json.loads(self.anchor_path.read_text())
        signed = record['signed'] if 'signed' in record else record
        signed['code'] = signed['code'][:-1] + ('0' if signed['code'][-1] != '0' else '1')
        record['signed'] = signed
        self.anchor_path.write_text(json.dumps(record))
        self.guard = self.anchor_guard()
        self.assert_access(self.paid(), 'anchor_unavailable', False)

    def test_failed_anchor_save_retries_same_day_with_frozen_wall_time(self):
        self.guard = self.anchor_guard()
        save = self.guard._save_anchor
        self.guard._save_anchor = Mock(side_effect=OSError('temporary failure'))
        self.guard.note_server_day('2026-10-13')
        self.assert_access(self.paid(), 'anchor_unavailable', False)
        self.assertFalse(self.guard.deletion_protected)
        self.assertEqual(self.guard._save_anchor.call_count, 1)
        for _ in range(5):
            self.guard.note_seen()
            self.assert_access(self.paid(), 'anchor_unavailable', False)
        self.assertEqual(self.guard._save_anchor.call_count, 1)
        self.guard._save_anchor = save
        self.mono += 5
        self.guard.note_seen()
        self.assert_access(self.paid(), 'active', True)
        self.assertTrue(self.guard.deletion_protected)

    def test_evaluate_active_when_clock_save_fails_but_anchor_matches_disk(self):
        anchor_seen = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
        self.guard = self.anchor_guard()
        self.guard.note_seen(at=anchor_seen)
        self.wall += timedelta(minutes=6)
        with patch('af_license.guard.os.replace', side_effect=OSError('disk busy')):
            self.assert_access(self.paid(), 'active', True)
        self.mono += 5
        self.guard.note_seen()
        self.assertEqual(json.loads(self.path.read_text())['max_seen'],
                         datetime(2026, 10, 13, 12, 6, tzinfo=timezone.utc).isoformat())

    def test_anchor_restores_rollback_after_clock_file_removed_post_expiry(self):
        private, public, _ = generate_keypair()
        device = codes.device_code('rollback-anchor-pc')
        signed = codes.issue_code(private, 'guard-test', 'standard', date(2026, 10, 1),
                                  days=31, device=device)
        code = codes.read_code(signed['code'], [public], 'guard-test', device,
                               today=date(2026, 10, 13))
        self.guard = self.anchor_guard()
        self.guard.note_server_day('2026-10-13')
        self.wall = datetime(2026, 11, 5, 12, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard.note_seen()
        self.assert_access(code, 'expired', False)
        self.path.unlink()
        self.wall = datetime(2026, 10, 31, 12, tzinfo=timezone.utc)
        self.local = self.wall.date()
        self.guard = self.anchor_guard()
        self.assertTrue(self.guard.deletion_protected)
        result = self.guard.evaluate(code)
        self.assertNotEqual((result['state'], result['full']), ('active', True))

    def test_max_seen_only_anchor_discards_untrusted_clock_server_day(self):
        _ = self.anchor_guard()
        seen = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
        self.anchor_path.write_text(json.dumps({'max_seen': seen.isoformat()}))
        self.path.write_text(json.dumps({
            'max_seen': seen.isoformat(),
            'server_day_max': '9999-12-31',
        }))
        self.guard = self.anchor_guard()
        self.assertIsNone(self.guard.server_day_max)
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        self.assertNotEqual(self.guard.effective_day(), date(9999, 12, 31))
        self.guard.note_server_time(datetime(2026, 10, 14, 12, tzinfo=timezone.utc))
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 14))

    def test_fresh_install_load_anchor_none_discards_clock_server_day(self):
        seen = datetime(2026, 10, 13, 12, 0, tzinfo=timezone.utc)
        self.path.write_text(json.dumps({
            'max_seen': seen.isoformat(),
            'server_day_max': '9999-12-31',
        }))
        self.guard = ClockGuard(self.path, now=lambda: self.wall, today=lambda: self.local,
                                calendar_tz=timezone.utc, monotonic_now=lambda: self.mono,
                                load_anchor=lambda: None, save_anchor=lambda _: None)
        self.assertIsNone(self.guard.server_day_max)
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        self.assertNotEqual(self.guard.effective_day(), date(9999, 12, 31))

    def test_reviewer_probe_repair_without_clock_file_never_lowers_anchor(self):
        future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard = self.anchor_guard()
        self.guard.note_seen(at=future)
        anchor_before = json.loads(self.anchor_path.read_text())
        self.path.unlink()
        floor = self.vendor_floor(date(2026, 10, 14))
        self.wall = floor - timedelta(hours=1)
        self.local = self.wall.date()
        self.guard = self.anchor_guard()
        self.guard.note_server_time(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))
        self.assertFalse(self.guard.clock_back())
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        anchor_after = json.loads(self.anchor_path.read_text())
        self.assertEqual(anchor_after['max_seen'], anchor_before['max_seen'])
        if self.path.exists():
            self.assertEqual(json.loads(self.path.read_text())['max_seen'],
                             anchor_before['max_seen'])

    def test_failed_note_seen_save_then_repair_does_not_lower_disk(self):
        self.guard = self.anchor_guard()
        future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=future)
        clock_before = json.loads(self.path.read_text())
        anchor_before = json.loads(self.anchor_path.read_text())
        self.guard.max_seen = future + timedelta(hours=1)
        self.guard._pending = True
        with patch('af_license.guard.os.replace', side_effect=OSError('disk busy')):
            self.guard.note_seen()
        self.assertEqual(json.loads(self.path.read_text())['max_seen'], clock_before['max_seen'])
        floor = self.vendor_floor(date(2026, 10, 14))
        self.wall = floor - timedelta(hours=1)
        self.local = self.wall.date()
        self.mono += 5
        self.guard.note_server_time(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(json.loads(self.path.read_text())['max_seen'], clock_before['max_seen'])
        self.assertEqual(json.loads(self.anchor_path.read_text())['max_seen'],
                         anchor_before['max_seen'])

    def test_fresh_hub_far_server_time_seeds_max_seen_without_floor_snap(self):
        server_dt = datetime(2026, 11, 13, 12, 0, tzinfo=timezone.utc)
        self.wall = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        result = HubTimeVerifyResult('2026-10-14', int(server_dt.timestamp()),
                                     False, 2, True)
        guard = self.new_guard()
        guard.note_hub_time(result)
        self.assertEqual(guard.max_seen, server_dt)

    def test_unconfirmed_clock_file_day_cannot_exceed_verified_anchor(self):
        self.guard = self.anchor_guard()
        self.guard.note_server_day('2026-10-13')
        state = json.loads(self.path.read_text())
        state['server_day_max'] = '9999-12-31'
        self.path.write_text(json.dumps(state))
        self.guard = self.anchor_guard()
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 13))
        self.guard.note_server_time(datetime(2026, 10, 14, 12, tzinfo=timezone.utc))
        self.guard = self.anchor_guard()
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 14))
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)

    def test_strict_anchor_rejects_unconfirmed_future_day_in_clock_file(self):
        self.guard = self.anchor_guard()
        self.guard.note_server_day('2026-10-13')
        state = json.loads(self.path.read_text())
        state['server_day_max'] = '9999-12-31'
        self.path.write_text(json.dumps(state))
        save = self.guard._save_anchor

        def strict(payload):
            if payload.startswith('{'):
                day = json.loads(payload)['day']
            else:
                day = payload
            if day == '9999-12-31':
                raise ValueError('unconfirmed_day')
            save(payload)

        self.guard = ClockGuard(self.path, now=lambda: self.wall, today=lambda: self.local,
                                calendar_tz=timezone.utc, monotonic_now=lambda: self.mono,
                                load_anchor=self.guard._load_anchor, save_anchor=strict)
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 13))
        self.mono += 5
        self.guard.note_server_time(datetime(2026, 10, 14, 12, tzinfo=timezone.utc))
        self.guard = ClockGuard(self.path, now=lambda: self.wall, today=lambda: self.local,
                                calendar_tz=timezone.utc, monotonic_now=lambda: self.mono,
                                load_anchor=self.guard._load_anchor, save_anchor=strict)
        self.assertEqual(self.guard.server_day_max, date(2026, 10, 14))
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)

    def test_historical_anchor_does_not_repair_a_future_local_maximum(self):
        self.guard = self.anchor_guard()
        self.guard.note_server_day('2026-10-13')
        self.wall = self.wall.replace(year=2036)
        self.guard.note_seen()
        self.wall = self.wall.replace(year=2026)
        self.guard = self.anchor_guard()
        self.assert_access(self.paid(), 'clock_back', False)
        self.guard.note_server_day('2026-10-13')
        floor = self.vendor_floor(date(2026, 10, 13))
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.assert_access(self.paid(), 'active', True)

    def test_signed_instant_lowers_only_to_vendor_day_floor(self):
        """REV70-4: pinned repair never drops max_seen below end-of-day + tolerance."""
        self.wall = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        floor = self.vendor_floor(date(2026, 10, 14))
        modest = datetime(2026, 10, 15, 1, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=modest)
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_time(datetime(2026, 10, 14, 23, 0, tzinfo=timezone.utc))
        self.assertEqual(self.guard.max_seen, modest)
        self.assertTrue(self.guard.clock_back())

        far_future = datetime(2026, 10, 18, 12, 0, tzinfo=timezone.utc)
        self.guard.note_seen(at=far_future)
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_time(datetime(2026, 10, 14, 20, 0, tzinfo=timezone.utc))
        self.assertEqual(self.guard.max_seen, floor)
        self.wall = floor - timedelta(hours=1)
        self.assertFalse(self.guard.clock_back())
        self.guard = self.new_guard()
        self.assertEqual(self.guard.max_seen, far_future)
        self.assertTrue(self.guard.clock_back())

    def test_bare_signed_day_repairs_same_year_future_to_floor(self):
        """REV70-4: day-only proof repairs beyond tolerance down to the vendor floor."""
        self.wall = datetime(2026, 10, 14, 12, 0, tzinfo=timezone.utc)
        self.local = self.wall.date()
        floor = self.vendor_floor(date(2026, 10, 14))
        self.guard.note_seen(at=datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc))
        self.assertTrue(self.guard.clock_back())
        self.guard.note_server_day('2026-10-14')
        self.assertEqual(self.guard.max_seen, floor)
        self.assertTrue(self.guard.clock_back())
        self.wall = floor - timedelta(hours=1)
        self.assertFalse(self.guard.clock_back())
        self.assert_access(self.paid(last='2026-10-31'), 'active', True)
        self.guard = self.new_guard()
        persisted = datetime(2026, 10, 16, 12, 0, tzinfo=timezone.utc)
        self.assertEqual(self.guard.max_seen, persisted)
        self.assertTrue(self.guard.clock_back())

    def test_anchor_callbacks_must_be_supplied_together(self):
        for kwargs in ({'load_anchor': lambda: None}, {'save_anchor': lambda day: None}):
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                ClockGuard(self.path, **kwargs)

    def test_missing_parent_never_creates_directories_or_raises(self):
        self.path = Path(self.directory.name) / 'missing' / 'guard.json'
        self.guard = self.new_guard()
        self.guard.note_server_day('2026-10-17')
        self.assert_access(self.paid(), 'expired', False)
        self.assertFalse(self.path.parent.exists())

    def test_never_online_frozen_date_has_no_usage_limit(self):
        code = self.paid()
        for _ in range(100):
            self.assert_access(code, 'active', True)
        self.assertEqual(set(json.loads(self.path.read_text())), {'max_seen', 'server_day_max'})

    def test_real_signed_code_is_rechecked_without_changing_it(self):
        private, public, _ = generate_keypair()
        device = codes.device_code('synthetic-guard-pc')
        for edition in ('standard', 'perpetual'):
            with self.subTest(edition=edition):
                signed = codes.issue_code(private, 'guard-test', edition, self.local,
                                          days=1, grace_days=3, device=device)
                verified = codes.read_code(signed['code'], [public], 'guard-test', device,
                                           today=self.local)
                self.assertTrue(verified.full_access)
                snapshot = copy.deepcopy(verified)
                self.guard.note_server_day('2026-10-17')
                self.assert_access(verified, 'active' if edition == 'perpetual' else 'expired',
                                   edition == 'perpetual')
                self.assertEqual(verified, snapshot)


class ServerScheduleTests(unittest.TestCase):
    def test_first_check_default_interval_and_monotonic_reset(self):
        self.assertTrue(should_check_server(None, 0))
        self.assertFalse(should_check_server(0, 0))
        self.assertFalse(should_check_server(100, 100 + 6 * 3600 - 0.001))
        self.assertTrue(should_check_server(100, 100 + 6 * 3600))
        self.assertTrue(should_check_server(100, 99))
        self.assertFalse(should_check_server(0, 3600, every_hours=2))
        self.assertTrue(should_check_server(0, 7200, every_hours=2))


class StdlibImportTests(unittest.TestCase):
    def test_documented_imports_without_site_packages_or_crypto(self):
        package = str(Path(__file__).resolve().parents[1])
        private, public, _ = generate_keypair()
        device = codes.device_code('stdlib-consumer-pc')
        signed = codes.issue_code(private, 'stdlib-test', 'standard', date(2026, 10, 13),
                                  days=1, device=device)
        script = f'''
import sys
from datetime import date
sys.path.insert(0, {package!r})
from af_license import ClockGuard
assert 'af_license.core' not in sys.modules
assert 'af_license.codes' not in sys.modules
from af_license import codes
from af_license.guard import ClockGuard as DirectGuard, should_check_server
assert DirectGuard is ClockGuard
assert codes.device_code('synthetic-pc')
assert not codes.read_code('bad', [], 'test').valid
assert codes.read_code({signed['code']!r}, [{public!r}], 'stdlib-test',
                       {device!r}, today=date(2026, 10, 13)).full_access
assert 'af_license.core' not in sys.modules
assert not any(name.startswith('cryptography') for name in sys.modules)
import af_license
try:
    af_license.nonexistent
except AttributeError:
    pass
else:
    raise AssertionError('unknown package attribute')
'''
        result = subprocess.run([sys.executable, '-I', '-S', '-c', script],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)


if __name__ == '__main__':
    unittest.main()
