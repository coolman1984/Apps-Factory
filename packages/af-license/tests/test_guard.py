"""Clock protection with synthetic clocks and files; no customer data or network."""
import copy
import json
import sys
import tempfile
import unittest
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from af_license import ClockGuard, codes, generate_keypair
from af_license.codes import CodeResult
from af_license.guard import should_check_server


class GuardTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.path = Path(self.directory.name) / 'guard.json'
        self.wall = datetime(2026, 10, 13, 12, tzinfo=timezone.utc)
        self.local = date(2026, 10, 13)
        self.guard = self.new_guard()

    def new_guard(self):
        return ClockGuard(self.path, now=lambda: self.wall, today=lambda: self.local)

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

    def test_unsigned_server_day_can_only_move_effective_day_forward(self):
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

    def test_all_three_dates_contribute_to_effective_day(self):
        self.local = date(2026, 10, 14)
        self.guard.note_seen()
        self.assertEqual(self.guard.effective_day(), self.local)
        self.guard.note_seen(at=datetime(2026, 10, 15))
        self.assertEqual(self.guard.effective_day(), date(2026, 10, 15))
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

    def test_deleted_state_loses_marks_but_signed_data_can_restore_time(self):
        code = self.paid()
        self.guard.note_seen(at=datetime(2026, 10, 15))
        self.guard.note_server_day('2026-10-16')
        self.path.unlink()
        self.guard = self.new_guard()
        self.assertIsNone(self.guard.max_seen)
        self.assertIsNone(self.guard.server_day_max)
        self.assert_access(code, 'active', True)
        self.guard.note_seen(at=datetime(2026, 10, 15))
        self.assert_access(code, 'clock_back', False)
        self.assert_access(code, 'expired', False, tolerance_hours=72)
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
        self.guard.note_seen()
        self.assertEqual(self.new_guard().server_day_max, date(2026, 10, 17))

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


if __name__ == '__main__':
    unittest.main()
