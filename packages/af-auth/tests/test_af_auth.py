"""Unit and regression tests for af-auth (Trip Orders v1.1.5 auth rules)."""
import concurrent.futures
import os
import sqlite3
import sys
import tempfile
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_auth as A  # noqa: E402

PASS = 'Office-pass88'
PASS2 = 'Office-pass12'
VIEW = ['overview.view']


def store():
    return A.AuthStore(':memory:')


def seed_admin(s: A.AuthStore, username='boss', password='Secure-pass9'):
    s.setup(username, 'System Owner', password, ip='127.0.0.1')
    return s.get_by_username(username)


def add_user(s: A.AuthStore, username, password=PASS2, perms=None, status='approved'):
    if not s.has_users():
        seed_admin(s)
    uid = __import__('uuid').uuid4().hex
    perms = perms or VIEW
    row = {
        'username': username, 'full_name': username.title(), 'pw_hash': A.hash_password(password),
        'perms': __import__('json').dumps(perms), 'active': 1 if status == 'approved' else 0,
        'status': status, 'deleted': 0, 'must_change': 0, 'created_at': A.now(), 'created_by': 'test',
        'updated_at': A.now(), 'updated_by': 'test',
    }
    s._commit([{'e': 'users', 'id': uid, 'op': 'insert', 's': row, 'r': {'id': uid, **row}}])
    return s.get(uid)


class Policy(unittest.TestCase):
    def test_sole_admin_never_locked(self):
        failed, locked = A.login_failure_update(4, True, 5, 15)
        self.assertEqual(failed, 5)
        self.assertIsNone(locked)

    def test_reset_guess_sole_admin_no_lock(self):
        failed, locked, burn, _ = A.reset_guess_update(7, True, 5, 15, 3, False)
        self.assertIsNone(locked)
        self.assertTrue(burn)


class SignupFlow(unittest.TestCase):
    def test_pending_until_approved(self):
        s = store()
        seed_admin(s)
        r = s.register('newhire', 'New Hire', PASS)
        self.assertEqual(len(r['request_code']), 6)
        with self.assertRaises(A.AuthError) as e:
            s.login('newhire', 'wrong')
        self.assertNotIn('waiting', str(e.exception).lower())
        with self.assertRaises(A.AuthError) as e2:
            s.login('newhire', PASS)
        self.assertIn('waiting', str(e2.exception).lower())
        u = s.get_by_username('newhire')
        s.review(u['id'], 'approve', perms=VIEW)
        s.login('newhire', PASS)

    def test_refused_shows_reason(self):
        s = store()
        seed_admin(s)
        s.register('refused1', 'Refused One', PASS)
        u = s.get_by_username('refused1')
        s.review(u['id'], 'reject', reason='Not on the staff list')
        with self.assertRaises(A.AuthError) as e:
            s.login('refused1', PASS)
        self.assertEqual(e.exception.key, 'autherr.signupRejectedReason')
        self.assertEqual(e.exception.vars.get('reason'), 'Not on the staff list')

    def test_rejected_user_may_reregister(self):
        s = store()
        seed_admin(s)
        s.register('retry', 'Retry User', PASS)
        u = s.get_by_username('retry')
        s.review(u['id'], 'reject', reason='Try again later')
        r = s.register('retry', 'Retry User', PASS2)
        self.assertTrue(r['ok'])
        u2 = s.get_by_username('retry')
        self.assertEqual(u2['status'], 'pending')
        self.assertTrue(A.verify_password(PASS2, u2['pw_hash']))

    def test_suspend_blocks_login(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'suspendme')
        s.review(u['id'], 'suspend', reason='Policy test')
        with self.assertRaises(A.AuthError) as e:
            s.login('suspendme', PASS2)
        self.assertEqual(e.exception.key, 'autherr.suspended')
        self.assertIn('suspended', str(e.exception).lower())

    def test_suspended_username_cannot_reregister(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'wasactive')
        s.review(u['id'], 'suspend', reason='Policy test')
        with self.assertRaises(A.AuthError) as e:
            s.register('wasactive', 'New Try', PASS)
        self.assertIn('taken', str(e.exception).lower())

    def test_cannot_suspend_sole_admin(self):
        s = store()
        boss = seed_admin(s)
        with self.assertRaises(A.AuthError) as e:
            s.review(boss['id'], 'suspend', reason='Test')
        self.assertEqual(e.exception.key, 'autherr.lastAdmin')


class ResetCode(unittest.TestCase):
    def test_reset_flow(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'resetme')
        code = s.issue_reset_code(u['id'])['code']
        spaced = code[:4] + '-' + code[4:]
        s.reset_with_code('resetme', spaced, 'Fresh-pass42')
        s.login('resetme', 'Fresh-pass42')

    def test_reset_clears_login_lockout(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'resetlock')
        for _ in range(6):
            try:
                s.login('resetlock', 'wrong')
            except A.AuthError:
                pass
        self.assertTrue(s.is_locked(u['id']))
        code = s.issue_reset_code(u['id'])['code']
        s.reset_with_code('resetlock', code, 'Fresh-pass99')
        s.login('resetlock', 'Fresh-pass99')

    def test_clear_reset_replicates_on_success(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'clr_ok')
        code = s.issue_reset_code(u['id'])['code']
        s.reset_with_code('clr_ok', code, 'Fresh-pass42')
        bindings = A.journal_clear_reset_hashes(s.journal_ops())
        self.assertTrue(bindings and all(bindings))
        s.rebuild_from_journal()
        row = s.conn.execute('SELECT reset_hash FROM users WHERE username=?', ('clr_ok',)).fetchone()
        self.assertFalse(row['reset_hash'])
        with self.assertRaises(A.AuthError):
            s.reset_with_code('clr_ok', code, 'Another-pass99')

    def test_three_wrong_guesses_burn_code(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'clr_bad')
        burned = s.issue_reset_code(u['id'])['code']
        for _ in range(3):
            try:
                s.reset_with_code('clr_bad', 'BADCODE1', 'Fresh-pass42')
            except A.AuthError:
                pass
        bindings = A.journal_clear_reset_hashes(s.journal_ops())
        self.assertEqual(len(bindings), 1)
        self.assertTrue(all(bindings))
        s.rebuild_from_journal()
        with self.assertRaises(A.AuthError):
            s.reset_with_code('clr_bad', burned, 'Fresh-pass42')

    def test_reject_journals_clear_reset(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'rejclr')
        burned = s.issue_reset_code(u['id'])['code']
        s.conn.execute('UPDATE users SET status=? WHERE id=?', ('pending', u['id']))
        s.review(u['id'], 'reject', reason='Not on the staff list')
        self.assertTrue(A.journal_clear_reset_hashes(s.journal_ops()))
        s.rebuild_from_journal()
        with self.assertRaises(A.AuthError):
            s.reset_with_code('rejclr', burned, 'Fresh-pass42')

    def test_suspend_journals_clear_reset(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'susclr')
        burned = s.issue_reset_code(u['id'])['code']
        s.review(u['id'], 'suspend', reason='Policy test')
        bindings = A.journal_clear_reset_hashes(s.journal_ops())
        self.assertTrue(bindings and all(bindings))
        s.rebuild_from_journal()
        row = s.conn.execute('SELECT reset_hash FROM users WHERE username=?', ('susclr',)).fetchone()
        self.assertFalse(row['reset_hash'])
        with self.assertRaises(A.AuthError):
            s.reset_with_code('susclr', burned, 'Fresh-pass42')

    def test_rejected_reregister_journals_clear_reset_code(self):
        s = store()
        seed_admin(s)
        s.register('rejagain', 'Rej Again', PASS)
        u = s.get_by_username('rejagain')
        s.review(u['id'], 'reject', reason='Not on the staff list')
        stale = A.hash_password('STALE-CODE1')
        s.conn.execute('UPDATE users SET reset_hash=?, reset_expires=? WHERE id=?',
                       (stale, '2099-01-01T00:00:00', u['id']))
        s.register('rejagain', 'Rej Again', PASS2)
        bindings = A.journal_clear_reset_hashes(s.journal_ops())
        self.assertIn(stale, bindings)
        s.rebuild_from_journal()
        row = s.conn.execute('SELECT reset_hash FROM users WHERE username=?', ('rejagain',)).fetchone()
        self.assertFalse(row['reset_hash'])

    def test_failed_commit_still_clears_reset_hash_after_wrong_guesses(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'commitburn')
        burned = s.issue_reset_code(u['id'])['code']
        for _ in range(2):
            try:
                s.reset_with_code('commitburn', 'BADCODE1', 'Fresh-pass42')
            except A.AuthError:
                pass
        inner = s.conn

        class _FlakyConn:
            def execute(self, sql, *args):
                if str(sql).strip().upper() == 'COMMIT':
                    raise sqlite3.OperationalError('simulated commit failure')
                return inner.execute(sql, *args)

            def __getattr__(self, name):
                return getattr(inner, name)

        s.conn = _FlakyConn()
        try:
            try:
                s.reset_with_code('commitburn', 'BADCODE1', 'Fresh-pass42')
            except (A.AuthError, sqlite3.OperationalError):
                pass
        finally:
            s.conn = inner
        s.rebuild_from_journal()
        row = s.conn.execute('SELECT reset_hash FROM users WHERE username=?', ('commitburn',)).fetchone()
        self.assertFalse(row['reset_hash'])
        with self.assertRaises(A.AuthError):
            s.reset_with_code('commitburn', burned, 'Fresh-pass42')

    def test_reset_code_single_use(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'once')
        code = s.issue_reset_code(u['id'])['code']
        s.reset_with_code('once', code, 'Fresh-pass42')
        with self.assertRaises(A.AuthError):
            s.reset_with_code('once', code, 'Another-pass99')

    def test_stale_clear_does_not_wipe_reissued_code(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'reissue')
        s.issue_reset_code(u['id'])
        stale = s.conn.execute('SELECT reset_hash FROM users WHERE id=?', (u['id'],)).fetchone()['reset_hash']
        for _ in range(3):
            try:
                s.reset_with_code('reissue', 'BADCODE1', 'Fresh-pass42')
            except A.AuthError:
                pass
        code2 = s.issue_reset_code(u['id'])['code']
        s._commit([A.clear_reset_code_op(u['id'], stale)])
        s.rebuild_from_journal()
        row = s.conn.execute('SELECT reset_hash FROM users WHERE username=?', ('reissue',)).fetchone()
        self.assertTrue(row['reset_hash'])
        s.reset_with_code('reissue', code2, 'Fresh-pass55')


class SecurityHelpers(unittest.TestCase):
    def test_verify_password_rejects_extreme_iterations(self):
        salt = '00' * 16
        dk = 'aa' * 32
        bad_low = f'pbkdf2_sha256$9999${salt}${dk}'
        bad_high = f'pbkdf2_sha256$2000000${salt}${dk}'
        self.assertFalse(A.verify_password('x', bad_low))
        self.assertFalse(A.verify_password('x', bad_high))

    def test_clear_reset_empty_binding_noop(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'bound')
        h = s.issue_reset_code(u['id'])
        live = s.conn.execute('SELECT reset_hash FROM users WHERE id=?', (u['id'],)).fetchone()['reset_hash']
        A.apply_user_command(s.conn, {'s': {'cmd': 'clear-reset-code', 'user': u['id'], 'reset_hash': ''}})
        row = s.conn.execute('SELECT reset_hash FROM users WHERE id=?', (u['id'],)).fetchone()
        self.assertEqual(row['reset_hash'], live)

    def test_sole_admin_login_delay(self):
        self.assertEqual(A.sole_admin_login_delay(4, 5, True), 0.0)
        self.assertGreater(A.sole_admin_login_delay(5, 5, True), 0.0)
        s = store()
        seed_admin(s, password='Secure-pass9')
        for _ in range(6):
            try:
                s.login('boss', 'wrong')
            except A.AuthError:
                pass
        self.assertGreater(s.sole_admin_login_delay('boss'), 0.0)
        self.assertGreaterEqual(A.http_auth_delay_seconds(s, 'boss'), 0.6)


class Sessions(unittest.TestCase):
    def test_session_idle_expiry(self):
        s = A.AuthStore(':memory:')
        s.idle = __import__('datetime').timedelta(seconds=1)
        s.setup('boss', 'Boss', 'Secure-pass9', ip='127.0.0.1')
        token, _ = s.login('boss', 'Secure-pass9')
        import time
        time.sleep(1.5)
        self.assertIsNone(s.session(token))

    def test_session_max_age_expiry(self):
        s = A.AuthStore(':memory:')
        s.max_age = __import__('datetime').timedelta(seconds=1)
        s.setup('boss', 'Boss', 'Secure-pass9', ip='127.0.0.1')
        token, _ = s.login('boss', 'Secure-pass9')
        import time
        time.sleep(1.5)
        self.assertIsNone(s.session(token))


class Lockout(unittest.TestCase):
    def test_parallel_wrong_logins_lock(self):
        s = store()
        seed_admin(s)
        add_user(s, 'victim', password='Secure-pass9')

        def wrong():
            try:
                s.login('victim', 'wrong-password')
            except A.AuthError:
                pass

        with concurrent.futures.ThreadPoolExecutor(max_workers=10) as ex:
            list(ex.map(lambda _: wrong(), range(10)))
        u = s.get_by_username('victim')
        self.assertTrue(s.is_locked(u['id']) or int(s.conn.execute(
            'SELECT failed FROM users WHERE id=?', (u['id'],)).fetchone()[0]) >= 5)
        with self.assertRaises(A.AuthError):
            s.login('victim', 'Secure-pass9')

    def test_replicated_save_cannot_clear_lockout_or_reset(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'localsafe')
        code = s.issue_reset_code(u['id'])['code']
        for _ in range(6):
            try:
                s.login('localsafe', 'wrong')
            except A.AuthError:
                pass
        self.assertTrue(s.is_locked(u['id']))
        live_reset = s.conn.execute('SELECT reset_hash FROM users WHERE id=?', (u['id'],)).fetchone()['reset_hash']
        s.save_user_replicated(u['id'], {'failed': 0, 'locked_until': None, 'reset_hash': '', 'full_name': 'Localsafe'})
        self.assertTrue(s.is_locked(u['id']))
        self.assertEqual(
            s.conn.execute('SELECT reset_hash FROM users WHERE id=?', (u['id'],)).fetchone()['reset_hash'],
            live_reset,
        )
        s.reset_with_code('localsafe', code, 'Fresh-pass42')

    def test_lock_survives_replicated_save(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'locksave')
        code = s.issue_reset_code(u['id'])['code']
        s.reset_with_code('locksave', code, 'Fresh-pass42')
        for _ in range(6):
            try:
                s.login('locksave', 'wrong')
            except A.AuthError:
                pass
        self.assertTrue(s.is_locked(u['id']))
        s.save_user_replicated(u['id'], {'full_name': 'Lock Save Renamed'})
        self.assertTrue(s.is_locked(u['id']))

    def test_sole_admin_reset_guesses_not_locked(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        s.issue_reset_code(boss['id'])
        for _ in range(8):
            try:
                s.reset_with_code('boss', 'BADCODE1', 'Fresh-pass42')
            except A.AuthError:
                pass
        self.assertFalse(s.is_locked(boss['id']))

    def test_sole_admin_login_not_locked(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        for _ in range(8):
            try:
                s.login('boss', 'wrong-only')
            except A.AuthError:
                pass
        self.assertFalse(s.is_locked(boss['id']))
        s.login('boss', 'Secure-pass9')


class SetupLocal(unittest.TestCase):
    def test_setup_rejects_remote_ip(self):
        s = store()
        with self.assertRaises(A.AuthError) as e:
            s.setup('boss', 'System Owner', 'Secure-pass9', ip='203.0.113.50')
        self.assertEqual(e.exception.key, 'autherr.setupRemote')
        self.assertFalse(s.has_users())


class LastManagerSave(unittest.TestCase):
    def test_sole_manager_save_deleted_refused(self):
        s = store()
        boss = seed_admin(s)
        with self.assertRaises(A.AuthError) as e:
            s.save_user_replicated(boss['id'], {'deleted': 1})
        self.assertEqual(e.exception.key, 'autherr.lastAdmin')

    def test_sole_manager_save_suspended_refused(self):
        s = store()
        boss = seed_admin(s)
        with self.assertRaises(A.AuthError) as e:
            s.save_user_replicated(boss['id'], {'status': 'suspended'})
        self.assertEqual(e.exception.key, 'autherr.lastAdmin')

    def test_sole_manager_save_active_string_zero_refused(self):
        s = store()
        boss = seed_admin(s)
        with self.assertRaises(A.AuthError) as e:
            s.save_user_replicated(boss['id'], {'active': '0'})
        self.assertEqual(e.exception.key, 'autherr.lastAdmin')

    def test_sole_manager_save_active_affinity_zero_spellings_refused(self):
        s = store()
        boss = seed_admin(s)
        for val in ('00', '0.0', '+0', '-0', '0e0'):
            with self.assertRaises(A.AuthError) as e:
                s.save_user_replicated(boss['id'], {'active': val})
            self.assertEqual(e.exception.key, 'autherr.lastAdmin')
            self.assertEqual(s.conn.execute('SELECT active FROM users WHERE id=?', (boss['id'],)).fetchone()[0], 1)

    def test_sole_manager_save_deleted_false_string_stored_as_integer_zero(self):
        s = store()
        boss = seed_admin(s)
        s.save_user_replicated(boss['id'], {'deleted': 'false'})
        self.assertEqual(s.conn.execute('SELECT deleted FROM users WHERE id=?', (boss['id'],)).fetchone()[0], 0)
        self.assertIsNotNone(s.get_by_username('boss'))
        s.login('boss', 'Secure-pass9')

    def test_sole_manager_save_invalid_pw_hash_refused(self):
        s = store()
        boss = seed_admin(s)
        for bad in ('', 'x'):
            with self.assertRaises(A.AuthError) as e:
                s.save_user_replicated(boss['id'], {'pw_hash': bad})
            self.assertEqual(e.exception.key, 'autherr.badField')
            self.assertEqual(e.exception.vars.get('field'), 'pw_hash')
        s.login('boss', 'Secure-pass9')

    def test_two_managers_save_invalid_pw_hash_on_helper_refused(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        helper = add_user(s, 'helper', perms=[*VIEW, A.DEFAULT_MANAGE])
        with self.assertRaises(A.AuthError) as e:
            s.save_user_replicated(helper['id'], {'pw_hash': ''})
        self.assertEqual(e.exception.key, 'autherr.badField')
        rows = [dict(r) for r in s.conn.execute('SELECT * FROM users WHERE deleted=0').fetchall()]
        self.assertIsNone(A.sole_admin_id(rows))
        self.assertTrue(A.is_managing_user(s.get(helper['id'])))
        s.login('boss', 'Secure-pass9')
        s.login('helper', PASS2)

    def test_two_managers_save_invalid_pw_hash_on_boss_refused(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        helper = add_user(s, 'helper', perms=[*VIEW, A.DEFAULT_MANAGE])
        with self.assertRaises(A.AuthError) as e:
            s.save_user_replicated(boss['id'], {'pw_hash': 'x'})
        self.assertEqual(e.exception.key, 'autherr.badField')
        s.login('boss', 'Secure-pass9')
        s.login('helper', PASS2)

    def test_sole_manager_save_uppercase_digest_pw_hash_refused(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        good = boss['pw_hash']
        algo, n, salt, dk = good.split('$')
        bad = f'{algo}${n}${salt}${dk.upper()}'
        self.assertTrue(A.is_valid_stored_password_hash(good))
        self.assertFalse(A.is_valid_stored_password_hash(bad))
        with self.assertRaises(A.AuthError) as e:
            s.save_user_replicated(boss['id'], {'pw_hash': bad})
        self.assertEqual(e.exception.key, 'autherr.badField')
        s.login('boss', 'Secure-pass9')


class SoleManagerPredicate(unittest.TestCase):
    def test_status_only_suspend_second_manager_keeps_sole_boss_unlocked(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        helper = add_user(s, 'helper', perms=[*VIEW, A.DEFAULT_MANAGE])
        s.save_user_replicated(helper['id'], {'status': 'suspended'})
        rows = s.conn.execute('SELECT * FROM users WHERE deleted=0').fetchall()
        rows = [dict(r) for r in rows]
        self.assertEqual(A.sole_admin_id(rows), boss['id'])
        for _ in range(8):
            try:
                s.login('boss', 'wrong-only')
            except A.AuthError:
                pass
        self.assertFalse(s.is_locked(boss['id']))
        s.login('boss', 'Secure-pass9')
        with self.assertRaises(A.AuthError) as e:
            s.login('helper', PASS2)
        self.assertEqual(e.exception.key, 'autherr.suspended')


class SignupLimits(unittest.TestCase):
    def test_pending_signup_cap(self):
        s = store()
        seed_admin(s)
        cap = A.MAX_PENDING_SIGNUPS
        for i in range(cap):
            s.register(f'pending{i}', f'Pending {i}', PASS)
        with self.assertRaises(A.AuthError) as e:
            s.register('one_too_many', 'One Too Many', PASS)
        self.assertEqual(e.exception.key, 'autherr.signupQueue')


class Integrity(unittest.TestCase):
    def test_duplicate_username_maps_to_auth_error(self):
        s = store()
        seed_admin(s)
        uid = __import__('uuid').uuid4().hex
        row = {
            'username': 'boss', 'full_name': 'Duplicate', 'pw_hash': A.hash_password(PASS),
            'perms': '[]', 'active': 1, 'status': 'approved', 'deleted': 0,
            'created_at': A.now(), 'created_by': 'test', 'updated_at': A.now(), 'updated_by': 'test',
        }
        with self.assertRaises(A.AuthError) as e:
            s._commit([{'e': 'users', 'id': uid, 'op': 'insert', 's': row, 'r': {'id': uid, **row}}])
        self.assertEqual(e.exception.key, 'autherr.usernameTaken')


class LoginAndResetRaces(unittest.TestCase):
    def test_login_password_swap_during_verify_fails(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        gate = threading.Event()
        done = threading.Event()
        real_verify = A.verify_password

        def slow_verify(pw, stored):
            ok = real_verify(pw, stored)
            if ok and pw == 'Secure-pass9':
                gate.set()
                done.wait(timeout=5)
            return ok

        def swap_password():
            gate.wait(timeout=5)
            s.save_user_replicated(boss['id'], {'pw_hash': A.hash_password('Other-pass99')})
            done.set()

        with patch.object(A, 'verify_password', side_effect=slow_verify):
            t = threading.Thread(target=swap_password)
            t.start()
            with self.assertRaises(A.AuthError) as e:
                s.login('boss', 'Secure-pass9')
            self.assertEqual(e.exception.key, 'autherr.wrong')
            t.join(timeout=5)
        with self.assertRaises(A.AuthError):
            s.login('boss', 'Secure-pass9')

    def test_suspend_during_login_verify_denies_session(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'raceuser')
        gate = threading.Event()
        done = threading.Event()
        real_verify = A.verify_password

        def slow_verify(pw, stored):
            ok = real_verify(pw, stored)
            if ok and pw == PASS2:
                gate.set()
                done.wait(timeout=5)
            return ok

        def suspend():
            gate.wait(timeout=5)
            s.review(u['id'], 'suspend', reason='Race')
            done.set()

        with patch.object(A, 'verify_password', side_effect=slow_verify):
            t = threading.Thread(target=suspend)
            t.start()
            with self.assertRaises(A.AuthError) as e:
                s.login('raceuser', PASS2)
            self.assertEqual(e.exception.key, 'autherr.suspended')
            t.join(timeout=5)
        self.assertIsNone(s.conn.execute(
            'SELECT 1 FROM sessions WHERE user_id=?', (u['id'],),
        ).fetchone())

    def test_approve_during_reregister_from_hash_fails(self):
        s = store()
        seed_admin(s)
        s.register('retryrace', 'Retry Race', PASS)
        u = s.get_by_username('retryrace')
        s.review(u['id'], 'reject', reason='Try again later')
        gate = threading.Event()
        done = threading.Event()
        real_hash = A.hash_password

        def slow_hash(pw):
            gate.set()
            done.wait(timeout=5)
            return real_hash(pw)

        def approve():
            gate.wait(timeout=5)
            s.review(u['id'], 'approve', perms=VIEW)
            done.set()

        with patch.object(A, 'hash_password', side_effect=slow_hash):
            t = threading.Thread(target=approve)
            t.start()
            with self.assertRaises(A.AuthError) as e:
                s.register('retryrace', 'Retry Race', PASS2)
            self.assertEqual(e.exception.key, 'autherr.signupState')
            t.join(timeout=5)
        u2 = s.get_by_username('retryrace')
        self.assertEqual(u2['status'], 'approved')
        self.assertTrue(A.verify_password(PASS, u2['pw_hash']))

    def test_concurrent_reset_code_single_winner(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'resetrace')
        code = s.issue_reset_code(u['id'])['code']
        results = []
        barrier = threading.Barrier(2)

        def attempt():
            barrier.wait(timeout=5)
            try:
                s.reset_with_code('resetrace', code, 'Fresh-pass42')
                results.append('ok')
            except A.AuthError:
                results.append('fail')

        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as ex:
            list(ex.map(lambda _: attempt(), range(2)))
        self.assertEqual(results.count('ok'), 1)
        self.assertEqual(results.count('fail'), 1)


class PasswordSave(unittest.TestCase):
    def test_pw_hash_save_logs_out_sessions(self):
        s = store()
        seed_admin(s, password='Secure-pass9')
        token, _ = s.login('boss', 'Secure-pass9')
        boss = s.get_by_username('boss')
        s.save_user_replicated(boss['id'], {'pw_hash': A.hash_password('Fresh-pass42')})
        self.assertIsNone(s.session(token))
        s.login('boss', 'Fresh-pass42')


class ResetBurnCallback(unittest.TestCase):
    def test_burn_after_commit_invokes_on_commit_with_binding(self):
        seen = []

        def on_commit(batch):
            seen.append(batch)

        s = A.AuthStore(':memory:', {'on_commit': on_commit})
        seed_admin(s)
        u = add_user(s, 'burncb')
        s.issue_reset_code(u['id'])
        for _ in range(3):
            try:
                s.reset_with_code('burncb', 'BADCODE1', 'Fresh-pass42')
            except A.AuthError:
                pass
        burn_batches = [b for b in seen if A.journal_clear_reset_hashes(b)]
        self.assertEqual(len(burn_batches), 1)
        bindings = A.journal_clear_reset_hashes(burn_batches[0])
        self.assertEqual(len(bindings), 1)
        self.assertTrue(bindings[0])


class SoleAdminResetLock(unittest.TestCase):
    def test_sole_admin_wrong_reset_clears_existing_lock(self):
        s = store()
        boss = seed_admin(s, password='Secure-pass9')
        future = (A.now()[:10] + 'T23:59:59')
        s.conn.execute('UPDATE users SET locked_until=? WHERE id=?', (future, boss['id']))
        s.issue_reset_code(boss['id'])
        try:
            s.reset_with_code('boss', 'BADCODE1', 'Fresh-pass42')
        except A.AuthError:
            pass
        row = s.conn.execute('SELECT locked_until FROM users WHERE id=?', (boss['id'],)).fetchone()
        self.assertFalse(row['locked_until'])


class ResetAccountState(unittest.TestCase):
    def test_reset_blocked_if_account_suspended_in_transaction(self):
        s = store()
        seed_admin(s)
        u = add_user(s, 'resetsus')
        code = s.issue_reset_code(u['id'])['code']
        gate = threading.Event()
        done = threading.Event()
        real_verify = A.verify_password

        def slow_verify(pw, stored):
            ok = real_verify(pw, stored)
            if ok and pw == code:
                gate.set()
                done.wait(timeout=5)
            return ok

        def suspend():
            gate.wait(timeout=5)
            s.save_user_replicated(u['id'], {'status': 'suspended', 'active': 0})
            done.set()

        with patch.object(A, 'verify_password', side_effect=slow_verify):
            t = threading.Thread(target=suspend)
            t.start()
            with self.assertRaises(A.AuthError):
                s.reset_with_code('resetsus', code, 'Fresh-pass42')
            t.join(timeout=5)


class ExampleConsumer(unittest.TestCase):
    """Products import afauth and wire catalogue manage permission."""

    def test_consumer_wires_manage_permission(self):
        import importlib.util
        ex = PKG / 'examples' / 'minimal' / 'consumer.py'
        spec = importlib.util.spec_from_file_location('consumer', ex)
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        self.assertTrue(mod.run_checks())


class VendoredCopies(unittest.TestCase):
    def test_known_products_hold_a_fresh_copy(self):
        import hashlib
        src = (PKG / 'af_auth.py').read_bytes()
        root = PKG.parents[2]
        for name in ('Store', 'Teachers', 'Yousef-Transportation'):
            copy_ = Path(os.environ.get(f'AF_{name.upper().replace("-", "_")}_REPO', root / name)) / 'server' / 'afauth.py'
            if not copy_.exists():
                continue
            body = copy_.read_bytes().split(b'\n', 2)[2]
            self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(src).hexdigest(),
                             f'{copy_} is stale: run python scripts/vendor_auth.py <product repo>')


if __name__ == '__main__':
    unittest.main()
