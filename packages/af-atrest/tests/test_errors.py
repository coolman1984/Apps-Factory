import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
from af_errors import CATALOGUE, AtRestError  # noqa: E402


class ErrorCatalogue(unittest.TestCase):
    def test_every_code_has_ar_and_en(self):
        for code, row in CATALOGUE.items():
            self.assertIn('en', row)
            self.assertIn('ar', row)
            self.assertTrue(row['en'].strip())
            self.assertTrue(row['ar'].strip())

    def test_message_bilingual(self):
        e = AtRestError('ATREST_RECOVERED_PACKAGE_BAD_FORMAT')
        self.assertIn('package', e.message('en').lower())
        self.assertTrue(e.message('ar'))


if __name__ == '__main__':
    unittest.main()
