"""Optional fresh-install licence check on the shared Windows smoke template.

The check is generic: the product names its own route and fresh state.
"""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]


def load_smoke():
    path = ROOT / 'templates' / 'windows-installer' / 'smoke_exe.py'
    spec = importlib.util.spec_from_file_location('af_windows_smoke_exe', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SmokeLicenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.smoke = load_smoke()

    def test_required_true_passes_and_a_switch_off_does_not(self):
        self.smoke.licence_status_required({'required': True, 'state': 'trial'}, state='trial')
        for payload in (
            {'required': False, 'state': 'trial'},
            {'state': 'trial'},
            {'required': 'true'},
            None,
            [],
        ):
            with self.subTest(payload=payload):
                with self.assertRaises(AssertionError):
                    self.smoke.licence_status_required(payload)

    def test_state_is_checked_only_when_named(self):
        self.smoke.licence_status_required({'required': True, 'state': 'active'})
        with self.assertRaises(AssertionError):
            self.smoke.licence_status_required({'required': True, 'state': 'active'}, state='trial')

    def test_flags_stay_off_the_program_command(self):
        env = os.environ.copy()
        env.pop('AF_SMOKE_LICENSE_PATH', None)
        env.pop('AF_SMOKE_LICENSE_STATE', None)
        with patch.dict(os.environ, env, clear=True):
            path, state, cmd = self.smoke.parse_smoke_args(
                ['--license-path', '/status/licence', '--license-state', 'trial', 'App.exe', '--port', '1']
            )
        self.assertEqual(path, '/status/licence')
        self.assertEqual(state, 'trial')
        self.assertEqual(cmd, ['App.exe', '--port', '1'])

    def test_flags_override_environment(self):
        with patch.dict(os.environ, {'AF_SMOKE_LICENSE_PATH': '/from-env', 'AF_SMOKE_LICENSE_STATE': 'from-env'}):
            path, state, cmd = self.smoke.parse_smoke_args(['--license-path', '/from-cli', 'App.exe'])
        self.assertEqual(path, '/from-cli')
        self.assertEqual(state, 'from-env')
        self.assertEqual(cmd, ['App.exe'])

    def test_environment_alone_selects_the_check(self):
        with patch.dict(os.environ, {'AF_SMOKE_LICENSE_PATH': '/from-env'}, clear=False):
            os.environ.pop('AF_SMOKE_LICENSE_STATE', None)
            path, state, cmd = self.smoke.parse_smoke_args(['App.exe'])
        self.assertEqual(path, '/from-env')
        self.assertIsNone(state)
        self.assertEqual(cmd, ['App.exe'])

    def test_workflow_run_lines_do_not_hardcode_a_licence_route(self):
        text = (ROOT / 'templates' / 'windows-installer' / 'windows.yml').read_text(encoding='utf-8')
        invocations = [
            line.strip()
            for line in text.splitlines()
            if 'smoke_exe.py' in line and not line.strip().startswith('#')
        ]
        self.assertEqual(
            invocations,
            [
                'run: python tools/smoke_exe.py build/app.dist/Al-Store.exe',
                'python tools/smoke_exe.py $exe',
            ],
        )


if __name__ == '__main__':
    unittest.main()
