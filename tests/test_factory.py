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
        self.assertEqual(d["properties"]["schema_version"]["enum"], ["1.0", "1.1"])
        self.assertEqual(set(d["properties"]["connectivity"]["properties"]["tier"]["enum"]), factory.TIERS)

    def test_all_sample_manifests(self):
        for name in ("hessa-product.json", "trip-orders-product.json", "multi-branch-reference.json",
                     "vendor-control-center.json"):
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
                     ["check", str(ROOT / "examples/trip-orders-product.json")],
                     ["check", str(ROOT / "examples/multi-branch-reference.json")],
                     ["check", str(ROOT / "examples/vendor-control-center.json")]]:
            p = subprocess.run(cmd + tail, capture_output=True, text=True, check=False)
            self.assertEqual(p.returncode, 0, p.stderr + p.stdout)

    def test_cli_release_fails_closed(self):
        cmd = [sys.executable, str(ROOT / "scripts/factory.py"), "check",
               str(ROOT / "examples/hessa-product.json"), "--release"]
        p = subprocess.run(cmd, capture_output=True, text=True, check=False)
        self.assertEqual(p.returncode, 2)
        self.assertIn("NO-GO", p.stdout)


    def reference(self):
        return factory.load(ROOT / "examples/multi-branch-reference.json")

    def test_legacy_schema_10_still_valid(self):
        p = factory.load(ROOT / "examples/trip-orders-product.json")
        p["schema_version"] = "1.0"
        del p["connectivity"]
        errors, selected = factory.valid_product(p)
        self.assertEqual(errors, [])
        self.assertEqual(factory.connectivity(p)["tier"], "office_server")

    def test_schema_11_requires_connectivity(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        del p["connectivity"]
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("connectivity" in e for e in errors))

    def test_cloud_sync_activates_sync_and_tenant_controls(self):
        ids = {c["id"] for c in factory.valid_product(self.reference())[1]}
        for cid in ("SYNC-05", "SYNC-12", "TEN-01", "MOB-03", "SITE-02", "OWN-01", "BIZ-06"):
            self.assertIn(cid, ids)
        office = {c["id"] for c in factory.valid_product(factory.load(ROOT / "examples/trip-orders-product.json"))[1]}
        self.assertFalse(any(c.startswith(("SYNC-", "MOB-", "OWN-", "SITE-", "MESH-")) for c in office))
        self.assertTrue({"ARCH-02", "ARCH-03", "OPS-06"}.issubset(office))

    def test_tier_must_fit_deployment(self):
        p = self.reference()
        p["connectivity"]["tier"] = "standalone"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("does not fit" in e for e in errors))

    def test_mobile_and_branches_need_cloud(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        p["connectivity"]["clients"].append("mobile_pwa")
        p["connectivity"]["sites"] = "multi"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("HTTPS" in e for e in errors))
        self.assertTrue(any("Multiple sites" in e for e in errors))

    def test_cloud_sync_needs_bounded_offline_grace_and_region(self):
        p = self.reference()
        del p["connectivity"]["offline_grace_days"]
        del p["data"]["residency"]
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("offline_grace_days" in e for e in errors))
        self.assertTrue(any("residency" in e for e in errors))
        p = self.reference()
        p["connectivity"]["offline_grace_days"] = True
        self.assertTrue(any("offline_grace_days" in e for e in factory.valid_product(p)[0]))

    def test_offline_mobile_actions_only_on_cloud_sync(self):
        p = self.reference()
        p["deployment"] = "saas"
        p["connectivity"]["tier"] = "cloud_only"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("Offline mobile actions" in e for e in errors))

    def test_cloud_entitlement_needs_cloud_tier(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        p["monetization"]["entitlement_method"] = "cloud_entitlement"
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("cloud_sync tier" in e for e in errors))

    def test_bad_clients_fail_cleanly(self):
        p = self.reference()
        p["connectivity"]["clients"] = [{"x": 1}]
        errors, _ = factory.valid_product(p)
        self.assertTrue(any("clients" in e for e in errors))

    def test_release_blocks_undecided_hosting_region(self):
        errors, _ = factory.valid_product(self.reference(), release=True)
        self.assertTrue(any("hosting region" in e for e in errors))

    def test_advisories_are_honest(self):
        notes = " ".join(factory.advisories(self.reference()))
        self.assertIn("leaves the premises", notes)
        self.assertIn("iOS", notes)
        office = " ".join(factory.advisories(factory.load(ROOT / "examples/trip-orders-product.json")))
        self.assertIn("cannot write", office)

    def test_scaffold_cloud_sync_tier(self):
        with tempfile.TemporaryDirectory() as d:
            out = Path(d) / "premium.json"
            args = type("Args", (), {"id": "premium-app", "name": "Premium", "mode": "lan", "market": "EG",
                                     "output": str(out), "tier": "cloud_sync", "sites": "multi",
                                     "clients": "windows_desktop,mobile_pwa", "multi_owner": True})
            factory.new_product(args)
            p = factory.load(out)
            self.assertEqual(p["schema_version"], "1.1")
            self.assertEqual(factory.valid_product(p)[0], [])
            self.assertIn("sync", factory.profiles(p))
            bad = type("Args", (), {"id": "bad-app", "name": "Bad", "mode": "desktop", "market": "EG",
                                    "output": str(Path(d) / "bad.json"), "tier": None, "sites": "single",
                                    "clients": "mobile_pwa", "multi_owner": False})
            with self.assertRaises(ValueError):
                factory.new_product(bad)

    def test_sync_envelope_contract(self):
        schema = factory.load(ROOT / "factory/contracts/sync-envelope.schema.json")
        example = factory.load(ROOT / "factory/contracts/examples/receipt-issued.json")
        self.assertTrue(set(schema["required"]).issubset(example))
        self.assertTrue(set(example).issubset(schema["properties"]))
        self.assertIn(example["class"], schema["properties"]["class"]["enum"])
        self.assertNotIn("D_derived", schema["properties"]["class"]["enum"])

    def test_windows_builds_get_protection_and_safe_updates(self):
        ids = {c["id"] for c in factory.valid_product(factory.load(ROOT / "examples/hessa-product.json"))[1]}
        for cid in ("PROT-01", "PROT-04", "REL-01", "REL-02", "REL-03", "SUP-03", "AI-04"):
            self.assertIn(cid, ids)
        web = {c["id"] for c in factory.valid_product(factory.load(ROOT / "examples/vendor-control-center.json"))[1]}
        self.assertFalse({"PROT-01", "REL-01", "REL-03"} & web)
        self.assertTrue({"AI-01", "AI-04", "SUP-01", "MOB-01"}.issubset(web))

    def test_control_center_is_not_releasable_yet(self):
        errors, _ = factory.valid_product(factory.load(ROOT / "examples/vendor-control-center.json"), release=True)
        self.assertTrue(any("hosting region" in e for e in errors))

    def test_office_mesh_tier(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        errors, selected = factory.valid_product(p)
        self.assertEqual(errors, [])
        ids = {c["id"] for c in selected}
        self.assertTrue({"MESH-01", "SYNC-03", "SYNC-12"}.issubset(ids))
        self.assertFalse({"SYNC-01", "SYNC-13", "TEN-01"} & ids)          # no cloud hub in a mesh
        p["deployment"] = "desktop"
        self.assertTrue(any("does not fit" in e for e in factory.valid_product(p)[0]))

    def test_every_control_profile_is_known(self):
        for c in factory.catalog():
            self.assertTrue(set(c["profiles"]).issubset(factory.PROFILES), c["id"])

if __name__ == "__main__":
    unittest.main()


class GuideControls(unittest.TestCase):
    """HELP-04 register, HELP-07..12 and the `guide` subcommand (packages/af-guide)."""
    SHOP = ROOT / "packages/af-guide/examples/shop"

    def test_help_controls(self):
        by_id = {c["id"]: c for c in factory.catalog()}
        self.assertIn("العربية الميسّرة", by_id["HELP-04"]["requirement"])
        self.assertNotIn("Egyptian Arabic a", by_id["HELP-04"]["requirement"])
        for n in range(7, 13):
            c = by_id[f"HELP-{n:02d}"]
            self.assertEqual(c["implementation_status"], "implemented")
            self.assertTrue({"desktop", "lan", "saas"}.issubset(c["profiles"]))
        ids = {c["id"] for c in factory.valid_product(factory.load(ROOT / "examples/hessa-product.json"))[1]}
        self.assertTrue({"HELP-07", "HELP-12"}.issubset(ids))

    def guide(self, folder, *extra):
        cmd = [sys.executable, str(ROOT / "scripts/factory.py"), "guide", str(folder),
               "--ui", str(self.SHOP / "ui-ar.json"), "--ui", str(self.SHOP / "ui-en.json"),
               "--access", str(self.SHOP / "access.json"), "--errors", str(self.SHOP / "errors.json"), *extra]
        return subprocess.run(cmd, capture_output=True, text=True, check=False)

    def test_guide_command(self):
        p = self.guide(self.SHOP, "--release")
        self.assertEqual(p.returncode, 0, p.stdout + p.stderr)
        self.assertIn("GUIDE OK", p.stdout)
        with tempfile.TemporaryDirectory() as d:
            for f in self.SHOP.iterdir():
                (Path(d) / f.name).write_bytes(f.read_bytes())
            ar = json.loads((Path(d) / "ar.json").read_text(encoding="utf-8"))
            ar["guide.open-shift.why"] = "لازم تفتح الوردية عشان تبيع."
            (Path(d) / "ar.json").write_text(json.dumps(ar, ensure_ascii=False), encoding="utf-8")
            self.assertEqual(self.guide(d).returncode, 0)
            p = self.guide(d, "--release")
            self.assertEqual(p.returncode, 1)
            self.assertIn("banned-word", p.stdout)


class PrivacyTelemetryControls(unittest.TestCase):
    """PRIV-01..06, TEL-01..03, FB-01, ROLL-01 (packages/af-consent, packages/af-telemetry)."""

    def test_controls_present(self):
        by_id = {c["id"]: c for c in factory.catalog()}
        for cid in ["PRIV-0%d" % n for n in range(1, 7)] + ["TEL-01", "TEL-02", "TEL-03", "FB-01", "ROLL-01"]:
            self.assertIn(cid, by_id)
        self.assertFalse(by_id["PRIV-05"]["required_if_applies"], "the «ماذا أُرسل؟» viewer is optional")
        text = json.dumps([by_id[c] for c in by_id if c.startswith(("PRIV", "TEL", "FB", "ROLL"))]).lower()
        for word in ("law", "lawyer", "legal", "151/2020", "gdpr"):
            self.assertNotIn(word, text)

    def test_roll_01_practice_first(self):
        p = factory.load(ROOT / "examples/hessa-product.json")
        p["telemetry"] = {"rollout": "practice"}
        self.assertEqual(factory.valid_product(p)[0], [])
        p["telemetry"] = {"rollout": "installations"}
        self.assertTrue(any("ROLL-01" in e for e in factory.valid_product(p)[0]))
        p["telemetry"] = {"rollout": "installations", "practice_evidence": "PENDING"}
        self.assertTrue(any("ROLL-01" in e for e in factory.valid_product(p)[0]))
        p["telemetry"] = {"rollout": "installations", "practice_evidence": "2026-10-20 demo shop, 3 days, 0 leaks"}
        self.assertEqual(factory.valid_product(p)[0], [])
        p["telemetry"] = {"rollout": "everyone"}
        self.assertTrue(factory.valid_product(p)[0])
        schema = factory.load(ROOT / "factory/product.schema.json")
        self.assertEqual(schema["properties"]["telemetry"]["properties"]["rollout"]["enum"], ["off", "practice", "installations"])
