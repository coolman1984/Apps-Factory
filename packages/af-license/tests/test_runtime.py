"""Commercial runtime fail-closed and contract-upgrade grace (generic af_license.runtime)."""
import importlib
import json
import os
import sqlite3
import sys
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

from af_license import runtime as R


class KV:
    def __init__(self):
        self.values = {}

    def __call__(self, key, value=None, delete=False):
        if delete:
            self.values.pop(key, None)
            return None
        if value is not None:
            self.values[key] = value
        return self.values.get(key)


def _seed_primary_db(path):
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);
        INSERT INTO meta VALUES ('initialized', '2020-01-01T00:00:00Z');
        CREATE TABLE office_rows (id TEXT PRIMARY KEY);
        INSERT INTO office_rows VALUES ('r1');
        """
    )
    conn.commit()
    conn.close()


def _meta_rw(db_path):
    def read(key):
        if not os.path.exists(db_path):
            return None
        conn = sqlite3.connect(db_path)
        try:
            row = conn.execute('SELECT value FROM meta WHERE key=?', (key,)).fetchone()
            return row[0] if row else None
        finally:
            conn.close()

    def write(key, value):
        if not os.path.exists(db_path):
            return
        conn = sqlite3.connect(db_path, isolation_level=None)
        try:
            conn.execute(
                'INSERT INTO meta(key, value) VALUES (?, ?) ON CONFLICT(key) DO NOTHING',
                (key, value),
            )
        finally:
            conn.close()

    return read, write


def _prior_checker(db_path):
    def has_prior():
        if not os.path.exists(db_path):
            return False
        try:
            conn = sqlite3.connect(db_path)
            try:
                if not conn.execute('SELECT 1 FROM office_rows LIMIT 1').fetchone():
                    return False
                row = conn.execute("SELECT value FROM meta WHERE key='initialized'").fetchone()
                if not row:
                    return False
                initialised = __import__('datetime').datetime.fromisoformat(str(row[0]).rstrip('Z'))
                return initialised < R.utcnow() - timedelta(hours=R.UPGRADE_PRIOR_DATA_MIN_AGE_HOURS)
            finally:
                conn.close()
        except Exception:
            return None

    return has_prior


def _evaluator(data_dir, build_channel='commercial', licence_code=None, clock_back=False):
    policy = R.ReleasePolicy(commercial_build=True, trusted_keys=('k',), build_channel=build_channel)
    kv = KV()
    if licence_code:
        kv('licence_code', licence_code)
    db_path = os.path.join(data_dir, 'primary.db')
    read_meta, write_meta = _meta_rw(db_path)
    return R.UpgradeGraceEvaluator(
        policy=policy,
        kv=kv,
        data_dir=data_dir,
        has_trusted_keys=True,
        has_licence_code=bool(licence_code),
        clock_rolled_back=lambda: clock_back,
        has_prior_office_data=_prior_checker(db_path),
        read_primary_meta=read_meta,
        write_primary_meta=write_meta,
    )


class DistributedRuntimeTest(unittest.TestCase):
    def test_plain_python_is_not_distributed(self):
        self.assertFalse(R.distributed_runtime(frozen=False, executable=sys.executable))

    def test_plain_source_run_has_no_shipped_markers(self):
        self.assertNotIn('__compiled__', vars(R))
        self.assertNotIn('__uncompiled__', vars(R))
        self.assertFalse(getattr(sys, 'frozen', False))
        self.assertTrue(os.path.basename(sys.executable).lower().startswith('python'))
        self.assertFalse(R.distributed_runtime())

    def test_frozen_is_distributed(self):
        self.assertTrue(R.distributed_runtime(frozen=True, executable=sys.executable))

    def test_sys_frozen_without_an_explicit_argument(self):
        old = getattr(sys, 'frozen', False)
        sys.frozen = True
        try:
            self.assertTrue(R.distributed_runtime(executable=sys.executable))
        finally:
            if old:
                sys.frozen = old
            else:
                del sys.frozen

    def test_nuitka_compiled_and_uncompiled_markers(self):
        for name in ('__compiled__', '__uncompiled__'):
            setattr(R, name, {'version': '4.3'})
            try:
                self.assertTrue(R.distributed_runtime(frozen=False, executable=sys.executable))
            finally:
                delattr(R, name)

    def test_explicit_compiled_argument_overrides_markers(self):
        R.__uncompiled__ = {'version': '4.3'}
        try:
            self.assertFalse(
                R.distributed_runtime(frozen=False, executable=sys.executable, compiled=False)
            )
            self.assertTrue(
                R.distributed_runtime(frozen=False, executable=sys.executable, compiled=True)
            )
        finally:
            del R.__uncompiled__

    def test_uncompiled_marker_fail_closed_without_policy_module(self):
        R.__uncompiled__ = {'version': '4.3'}
        try:
            pol = R.load_release_policy('_release_policy_missing', frozen=False, executable=sys.executable)
            self.assertTrue(pol.commercial_build)
            self.assertEqual(pol.trusted_keys, ())
            self.assertEqual(pol.build_channel, 'commercial')
        finally:
            del R.__uncompiled__

    def test_non_python_executable(self):
        self.assertTrue(R.distributed_runtime(frozen=False, executable='/opt/MyApp/MyApp.exe'))


class ReleasePolicyTest(unittest.TestCase):
    def test_missing_module_fail_closed_when_distributed(self):
        pol = R.release_policy_without_module(True)
        self.assertTrue(pol.commercial_build)
        self.assertEqual(pol.trusted_keys, ())
        self.assertEqual(pol.build_channel, 'commercial')

    def test_missing_module_source_mode(self):
        pol = R.release_policy_without_module(False)
        self.assertFalse(pol.commercial_build)
        self.assertEqual(pol.build_channel, 'source')

    def test_import_missing_policy_subprocess(self):
        code = """
import importlib, sys, tempfile
sys.path.insert(0, sys.argv[1])
runtime = importlib.import_module('af_license.runtime')
pol = runtime.load_release_policy('_release_policy_missing', frozen=True)
assert pol.commercial_build and pol.trusted_keys == () and pol.build_channel == 'commercial'
st = runtime.fail_closed_status_when_no_keys(pol, 'DEV1')
assert st['enforced'] and not st['full'] and st['state'] == 'none'
"""
        pkg = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with tempfile.TemporaryDirectory() as d:
            p = __import__('subprocess').run(
                [sys.executable, '-c', code, pkg],
                capture_output=True,
                text=True,
                env={**os.environ, 'PYTHONPATH': pkg},
            )
            self.assertEqual(p.returncode, 0, p.stderr)


class UpgradeGraceTest(unittest.TestCase):
    def test_fresh_install_no_grace(self):
        with tempfile.TemporaryDirectory() as d:
            ev = _evaluator(d)
            self.assertIsNone(ev.evaluate())
            self.assertFalse(ev.edits_allowed())

    def test_fresh_with_young_data_never_gets_grace(self):
        with tempfile.TemporaryDirectory() as d:
            db = os.path.join(d, 'primary.db')
            conn = sqlite3.connect(db)
            conn.executescript(
                "CREATE TABLE meta (key TEXT PRIMARY KEY, value TEXT);"
                "INSERT INTO meta VALUES ('initialized', ?);"
                "CREATE TABLE office_rows (id TEXT PRIMARY KEY); INSERT INTO office_rows VALUES ('x');"
            )
            conn.execute("UPDATE meta SET value=?", (R.utcnow().isoformat(timespec='seconds'),))
            conn.commit()
            conn.close()
            ev = _evaluator(d)
            self.assertIsNone(ev.evaluate())
            conn = sqlite3.connect(db)
            conn.execute("UPDATE meta SET value='2020-01-01T00:00:00Z' WHERE key='initialized'")
            conn.commit()
            conn.close()
            ev2 = _evaluator(d)
            g = ev2.evaluate()
            self.assertIsNotNone(g)
            self.assertFalse(ev2.edits_allowed())

    def test_prior_data_gets_grace_then_expires(self):
        with tempfile.TemporaryDirectory() as d:
            _seed_primary_db(os.path.join(d, 'primary.db'))
            ev = _evaluator(d)
            g = ev.evaluate()
            self.assertIsNotNone(g)
            self.assertGreater(g.days_left, 0)
            self.assertTrue(ev.edits_allowed())
            future = R.utcnow() + timedelta(days=R.UPGRADE_GRACE_DAYS + 1)
            ev2 = _evaluator(d)
            ev2.now = lambda: future
            g2 = ev2.evaluate()
            self.assertEqual(g2.reason, 'upgrade_grace_expired')
            self.assertFalse(ev2.edits_allowed())

    def test_licence_code_flag_is_reread(self):
        with tempfile.TemporaryDirectory() as d:
            ev = _evaluator(d)
            saved = {'code': True}
            ev.has_licence_code = lambda: saved['code']
            self.assertIsNone(ev.evaluate())
            ev.has_trusted_keys = lambda: False
            saved['code'] = False
            self.assertIsNone(ev.evaluate())

    def test_ci_test_never_gets_grace(self):
        with tempfile.TemporaryDirectory() as d:
            _seed_primary_db(os.path.join(d, 'primary.db'))
            ev = _evaluator(d, build_channel='ci-test')
            self.assertIsNone(ev.evaluate())

    def test_clock_back_locks_without_consuming_grace(self):
        with tempfile.TemporaryDirectory() as d:
            _seed_primary_db(os.path.join(d, 'primary.db'))
            ev = _evaluator(d)
            ev.evaluate()
            ev_clock = _evaluator(d, clock_back=True)
            g = ev_clock.evaluate()
            self.assertEqual(g.reason, 'clock_back')
            self.assertFalse(ev_clock.edits_allowed())
            ev_ok = _evaluator(d, clock_back=False)
            self.assertTrue(ev_ok.edits_allowed())

    def test_unreadable_db_does_not_consume_grace(self):
        with tempfile.TemporaryDirectory() as d:
            _seed_primary_db(os.path.join(d, 'primary.db'))
            ev = _evaluator(d)
            with patch.object(ev, 'has_prior_office_data', return_value=None):
                self.assertIsNone(ev.evaluate())
            self.assertFalse(ev._upgrade_grace_consumed())
            self.assertTrue(_evaluator(d).edits_allowed())


if __name__ == '__main__':
    unittest.main()
