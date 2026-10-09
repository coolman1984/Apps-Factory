import copy
import json
import re
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory

LEGAL_WORDS = re.compile(r"\b(law|legal|lawyer|jurisdiction|compliance|regulator)", re.I)


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
        self.assertNotRegex(notes, LEGAL_WORDS)
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
        for cid in ("PROT-01", "BIZ-03", "REL-01", "REL-02", "REL-03", "SUP-03", "AI-04"):
            self.assertIn(cid, ids)
        web = {c["id"] for c in factory.valid_product(factory.load(ROOT / "examples/vendor-control-center.json"))[1]}
        self.assertFalse({"PROT-01", "REL-01", "REL-03"} & web)
        self.assertTrue({"AI-01", "AI-04", "FB-01", "MOB-01"}.issubset(web))

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

class CoreGateTests(unittest.TestCase):
    """Core/reference tiers, merged and retired ids, and the two-item release evidence."""

    @staticmethod
    def proven(product=None):
        """A product that passes --release: both evidence items verified, proof for every applicable core control."""
        p = copy.deepcopy(product or factory.load(ROOT / "examples/hessa-product.json"))
        p["stage"] = "field_accepted"
        p["competitors"] = []  # competitor rows are advice only
        p["evidence"] = {"clean_device_restore": "2026-10-09 restored on a second PC, run log 41",
                         "core_user_acceptance": "2026-10-09 first customer did the journey alone"}
        if p.get("commercial_plan") == "solo":
            p["evidence"]["off_device_cloud_restore"] = "Synthetic test: off-PC encrypted backup restored on a second clean PC"
        p["control_evidence"] = {c["id"]: {"status": "verified", "proof": "test run 41"}
                                 for c in factory.core_controls(factory.applicable(factory.catalog(), p))}
        return p

    def test_every_control_has_a_valid_tier(self):
        for c in factory.catalog():
            self.assertIn(c.get("tier"), {"core", "reference"}, c["id"])

    def test_core_count_is_small(self):
        core = factory.core_controls(factory.catalog())
        self.assertTrue(25 <= len(core) <= 35, len(core))
        for c in core:  # each core control says how it is checked
            self.assertTrue(c["acceptance_evidence"].strip(), c["id"])

    def test_merged_ids_resolve_to_survivor(self):
        data = factory.catalog_data()
        live = {c["id"] for c in data["controls"]}
        merged = factory.merged_map(data)
        self.assertGreaterEqual(len(merged), 10)
        for old, new in merged.items():
            self.assertNotIn(old, live, old)
            self.assertIn(new, live, old)
            self.assertEqual(factory.lookup(old), ("merged", new))
        self.assertEqual(factory.lookup("HELP-03"), ("merged", "HELP-09"))
        self.assertEqual(factory.lookup("HELP-12"), ("merged", "HELP-07"))
        self.assertEqual(factory.lookup("HELP-07")[0], "control")

    def test_retired_ids_have_a_reason_and_are_not_controls(self):
        data = factory.catalog_data()
        live = {c["id"] for c in data["controls"]}
        self.assertTrue(data["retired"])
        for r in data["retired"]:
            self.assertTrue(r["reason"].strip(), r["id"])
            self.assertNotIn(r["id"], live)
            self.assertNotIn(r["id"], factory.merged_map(data))
            kind, reason = factory.lookup(r["id"])
            self.assertEqual((kind, reason), ("retired", r["reason"]))
        self.assertEqual(factory.lookup("NOPE-99"), (None, None))
        for cid in ("REG-01", "REG-02"):
            self.assertEqual(factory.lookup(cid)[0], "retired")

    def test_cli_lookup_of_merged_and_retired_ids(self):
        cmd = [sys.executable, str(ROOT / "scripts/factory.py"), "controls"]
        out = subprocess.run(cmd + ["HELP-03"], capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0)
        self.assertIn("merged into HELP-09", out.stdout)
        out = subprocess.run(cmd + ["REG-01"], capture_output=True, text=True, check=False)
        self.assertIn("retired:", out.stdout)
        out = subprocess.run(cmd + ["NOPE-99"], capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 2)

    def test_doctor_prints_counts(self):
        out = subprocess.run([sys.executable, str(ROOT / "scripts/factory.py"), "doctor"],
                             capture_output=True, text=True, check=False)
        self.assertEqual(out.returncode, 0, out.stderr)
        self.assertRegex(out.stdout, r"\d+ core .*\d+ reference .*\d+ merged ids, \d+ retired ids")

    def test_no_legal_wording_in_controls(self):
        data = factory.catalog_data()
        texts = [json.dumps(c, ensure_ascii=False) for c in data["controls"]]
        texts += [json.dumps(r, ensure_ascii=False) for r in data["retired"]] + [data["policy"]]
        for text in texts:
            self.assertNotRegex(text, LEGAL_WORDS)

    def test_release_evidence_is_exactly_two_items(self):
        self.assertEqual(set(factory.EVIDENCE), {"clean_device_restore", "core_user_acceptance"})
        schema = factory.load(ROOT / "factory/product.schema.json")
        self.assertEqual(set(schema["properties"]["evidence"]["required"]), set(factory.EVIDENCE))
        with tempfile.TemporaryDirectory() as d:
            args = type("Args", (), {"id": "sample-app", "name": "Sample", "mode": "desktop", "market": "EG",
                                     "output": str(Path(d) / "s.json")})
            self.assertEqual(set(factory.load(factory.new_product(args))["evidence"]), set(factory.EVIDENCE))

    def test_legacy_evidence_keys_are_accepted_and_ignored(self):
        p = self.proven()
        p["evidence"].update({"market_review": "PENDING", "privacy_review": "PENDING", "security_review": "PENDING"})
        self.assertEqual(factory.valid_product(p, release=True)[0], [])
        old = factory.load(ROOT / "examples/hessa-product.json")  # still carries the legacy keys
        self.assertIn("privacy_review", old["evidence"])
        self.assertEqual(factory.valid_product(old)[0], [])
        errors = factory.valid_product(old, release=True)[0]
        self.assertFalse(any(k in e for e in errors for k in factory.LEGACY_EVIDENCE))
        del p["evidence"]["clean_device_restore"]
        self.assertTrue(any("evidence" in e for e in factory.valid_product(p)[0]))

    def test_fully_proven_product_passes_release(self):
        for name in ("hessa-product.json", "al-store-product.json", "trip-orders-product.json"):
            with self.subTest(name=name):
                self.assertEqual(factory.valid_product(self.proven(factory.load(ROOT / "examples" / name)), release=True)[0], [])

    def test_zero_competitors_is_advice_not_a_release_error(self):
        p = self.proven()
        self.assertEqual(p["competitors"], [])
        self.assertEqual(factory.valid_product(p, release=True)[0], [])
        self.assertTrue(factory.competitor_advice(p))
        p["competitors"] = [{"name": f"Alternative {i}"} for i in range(5)]
        self.assertEqual(factory.competitor_advice(p), [])
        with tempfile.TemporaryDirectory() as d:
            p["competitors"] = []
            path = Path(d) / "p.json"
            path.write_text(json.dumps(p), encoding="utf-8")
            out = subprocess.run([sys.executable, str(ROOT / "scripts/factory.py"), "check", str(path), "--release"],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(out.returncode, 0, out.stdout + out.stderr)
            self.assertIn("ADVICE: 0 of 5 competitor", out.stdout)

    def test_missing_core_proof_or_evidence_blocks_release(self):
        p = self.proven()
        core_id = next(iter(p["control_evidence"]))
        del p["control_evidence"][core_id]
        self.assertEqual(factory.valid_product(p, release=True)[0], ["Missing verified proof: " + core_id])
        p = self.proven()
        p["control_evidence"]["IAM-01"] = {"status": "implemented", "proof": "unit test"}
        self.assertEqual(factory.valid_product(p, release=True)[0], ["Missing verified proof: IAM-01"])
        p = self.proven()
        p["evidence"]["core_user_acceptance"] = "PENDING first pilot shop"
        self.assertEqual(factory.valid_product(p, release=True)[0], ["Unverified release evidence: core_user_acceptance"])

    def test_reference_controls_never_block_release(self):
        p = self.proven()
        selected = factory.valid_product(p)[1]
        reference = [c["id"] for c in selected if c["tier"] == "reference"]
        self.assertGreater(len(reference), 10)
        self.assertFalse(set(reference) & set(p["control_evidence"]))  # not one reference control has proof
        errors = factory.valid_product(p, release=True)[0]
        self.assertEqual(errors, [])
        p["control_evidence"][reference[0]] = {"status": "planned", "proof": ""}  # a planned reference control is fine too
        self.assertEqual(factory.valid_product(p, release=True)[0], [])

    def test_old_control_ids_in_manifests_still_validate(self):
        p = self.proven()
        p["control_evidence"].update({"HELP-03": {"status": "verified", "proof": "x"},
                                      "REG-01": {"status": "planned", "proof": ""}})
        self.assertEqual(factory.valid_product(p, release=True)[0], [])
        p["control_evidence"]["NOPE-99"] = {"status": "verified", "proof": "x"}
        self.assertTrue(any("Unknown control ID" in e for e in factory.valid_product(p)[0]))

    def test_examples_with_pending_evidence_still_fail_release_for_a_real_reason(self):
        for name in ("hessa-product.json", "multi-branch-reference.json", "vendor-control-center.json", "al-store-product.json"):
            with self.subTest(name=name):
                errors = factory.valid_product(factory.load(ROOT / "examples" / name), release=True)[0]
                self.assertTrue(any("Missing verified proof" in e for e in errors))
                self.assertFalse(any("Unverified release evidence: market" in e for e in errors))


if __name__ == "__main__":
    unittest.main()


class GuideControls(unittest.TestCase):
    """The three core HELP controls (HELP-07, HELP-09, HELP-11) and the `guide` subcommand (packages/af-guide)."""
    SHOP = ROOT / "packages/af-guide/examples/shop"

    def test_help_controls(self):
        by_id = {c["id"]: c for c in factory.catalog()}
        self.assertEqual(sorted(i for i in by_id if i.startswith("HELP-")), ["HELP-07", "HELP-09", "HELP-11"])
        self.assertIn("العربية الميسّرة", by_id["HELP-11"]["requirement"])
        self.assertNotIn("Egyptian Arabic a", by_id["HELP-11"]["requirement"])
        for cid in ("HELP-07", "HELP-09", "HELP-11"):
            c = by_id[cid]
            self.assertEqual(c["tier"], "core")
            self.assertEqual(c["implementation_status"], "implemented")
            self.assertTrue({"desktop", "lan", "saas"}.issubset(c["profiles"]))
        self.assertEqual(by_id["HELP-07"]["merged_from"], ["HELP-01", "HELP-02", "HELP-08", "HELP-12"])
        ids = {c["id"] for c in factory.valid_product(factory.load(ROOT / "examples/hessa-product.json"))[1]}
        self.assertTrue({"HELP-07", "HELP-09", "HELP-11"}.issubset(ids))

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
    """PRIV-01..06, TEL-01..03, FB-01, ROLL-01 (packages/af-consent, packages/af-telemetry); some ids are now merged."""

    def test_controls_present(self):
        by_id = {c["id"]: c for c in factory.catalog()}
        for cid in ["PRIV-01", "PRIV-03", "PRIV-04", "PRIV-05", "TEL-01", "TEL-02", "FB-01", "ROLL-01"]:
            self.assertIn(cid, by_id)
        for old, new in (("PRIV-02", "PRIV-01"), ("PRIV-06", "PRIV-03"), ("TEL-03", "PRIV-03"), ("SUP-04", "PRIV-03")):
            self.assertEqual(factory.lookup(old), ("merged", new))
        self.assertFalse(by_id["PRIV-05"]["required_if_applies"], "the «ماذا أُرسل؟» viewer is optional")
        text = json.dumps([by_id[c] for c in by_id if c.startswith(("PRIV", "TEL", "FB", "ROLL"))]).lower()
        for word in ("law", "lawyer", "legal", "151/2020", "gdpr"):
            self.assertNotIn(word, text)
        self.assertEqual({by_id[c]["tier"] for c in ("PRIV-01", "PRIV-03", "TEL-01", "FB-01")}, {"core"})

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
