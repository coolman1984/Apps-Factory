"""Re-use af-atrest vault error codes (standalone copy for tool imports)."""

import sys
from pathlib import Path

PKG = Path(__file__).resolve().parents[2] / 'packages' / 'af-atrest'
sys.path.insert(0, str(PKG))
from af_errors import AtRestError, CATALOGUE  # noqa: E402

__all__ = ['AtRestError', 'CATALOGUE']
