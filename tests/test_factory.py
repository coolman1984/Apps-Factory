import copy
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory


class FactoryTests(unittest.TestCase):
    def test_catalog_unique_and_substantial(self):
        ids = [c["id"] for c in factory.catalog()]
        self.assertGreaterEqual(len(ids), 40)
        self.assertEqual(len(ids), len(set(ids)))

    def test_schema_parses(self):
        d = factory.load(ROOT / "factory/product.schema.json")
        self.assertEqual(d["properties"]["schema_version"]["const"], "1.0")

    def test_all_sample_manifests(self):
        for name in ("hessa-product.json", "trip-orders-product.json"):
            with self.subTest(name=name):
                p = factory.load(ROOT / "examples" / name)
                errors, selected = factory.valid_product(p)
                self.assertEqual(errors, [])
                self.assertGreaterEqual(len(selected), 30)

    def test_no_release_claim_without_field_evidence(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        errors, _ = factory.valid_product(p, release=True)
        self.assertTrue(any("field acceptance" in e for e in errors))
        self.assertTrue(any("Missing verified proof" in e for e in errors))

    def test_expiration_never_locks_customer_data(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        p["monetization"]["expiry_data_access"] = "delete_customer_data"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("read/export/backup" in e for e in errors))

    def test_saas_requires_cloud_entitlement(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        p["deployment"] = "saas"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("cloud_entitlement" in e for e in errors))

    def test_regulated_overlay_required(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        p["data"]["sensitivity"] = "regulated"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("regulated_overlay" in e for e in errors))

    def test_no_overwrite_when_scaffolding(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "sample.json"
            args = type("Args", (), {"id": "sample-app", "name": "Sample", "mode": "desktop",
                                     "market": "EG", "output": str(out)})
            factory.new_product(args)
            self.assertTrue(out.exists())
            with self.assertRaises(FileExistsError):
                factory.new_product(args)

    def test_cli_doctor_and_samples(self):
        cmd = [sys.executable, str(ROOT / "scripts/factory.py")]
        for tail in [["doctor"], ["check", str(ROOT / "examples/hessa-product.json")],
                     ["check", str(ROOT / "examples/trip-orders-product.json")]]:
            p = subprocess.run(cmd + tail, capture_output=True, text=True, check=False)
            self.assertEqual(p.returncode, 0, p.stderr + p.stdout)

    def test_cli_release_fails_closed(self):
        cmd = [sys.executable, str(ROOT / "scripts/factory.py"), "check",
               str(ROOT / "examples/hessa-product.json"), "--release"]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("NO-GO", p.stdout)


if __name__ == "__main__":
    unittest.main()
