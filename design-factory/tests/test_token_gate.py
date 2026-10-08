"""The token gate is the enforceable part of DESIGN.md v2: contrast and minimum sizes fail the build, not a review."""
from pathlib import Path
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[2]
GATE = ROOT / "design-factory" / "qa" / "token_gate.py"
sys.path.insert(0, str(GATE.parent))
import token_gate  # noqa: E402


class TokenGate(unittest.TestCase):
    def test_factory_core_tokens_pass(self):
        result = subprocess.run([sys.executable, str(GATE), str(ROOT / "design-factory" / "core" / "tokens.css")], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stdout)

    def test_a_weak_grey_fails_in_the_theme_where_it_is_weak(self):
        css = ':root{--ink:#111111;--bg:#ffffff;--tap:40px}[data-theme="dark"]{--ink:#444444;--bg:#222222}'
        problems = token_gate.check(css, ["ink/bg"], {"tap": 44})
        self.assertEqual(len(problems), 2, problems)
        self.assertTrue(any(p.startswith("dark") for p in problems))
        self.assertTrue(any("--tap" in p for p in problems))

    def test_missing_token_is_a_failure_not_a_pass(self):
        self.assertTrue(token_gate.check(":root{--ink:#000000}", ["ink/bg"], {}))

    def test_known_ratios(self):
        self.assertAlmostEqual(token_gate.contrast("#000000", "#ffffff"), 21, places=1)
        self.assertAlmostEqual(token_gate.contrast("#767676", "#ffffff"), 4.54, places=2)


if __name__ == "__main__":
    unittest.main()
