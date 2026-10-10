"""Regression tests for every Company OS handoff, including negative cases."""
import copy
import json
import re
import runpy
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "company-os"
VALIDATOR = CONTRACT / "validate_task.py"


class CompanyOSContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((CONTRACT / "task.schema.json").read_text(encoding="utf-8"))
        cls.examples = json.loads((CONTRACT / "examples.json").read_text(encoding="utf-8"))
        cls.validate = staticmethod(runpy.run_path(str(VALIDATOR))["validate_task"])

    def sample(self):
        return copy.deepcopy(self.examples[0])

    def assertInvalid(self, task, fragment):
        problems = self.validate(task)
        self.assertTrue(problems, "invalid task accepted")
        self.assertTrue(any(fragment in p for p in problems), repr(problems))

    def test_examples_pass_strict_validation(self):
        self.assertGreaterEqual(len(self.examples), 2)
        self.assertEqual(len({e["task_id"] for e in self.examples}), len(self.examples))
        for sample in self.examples:
            self.assertEqual(self.validate(sample), [])

    def test_missing_source_ref_is_rejected(self):
        t = self.sample()
        t.pop("decision_ref")
        self.assertInvalid(t, "decision_ref")

    def test_bad_source_refs_rejected(self):
        for value in (None, "", "docs/", "foo.md", 27):
            with self.subTest(value=value):
                t = self.sample()
                t["decision_ref"] = value
                self.assertInvalid(t, "decision_ref")

    def test_unsupported_legacy_field_names_rejected(self):
        t = self.sample()
        t["product"] = t.pop("project")
        t["assigned_agent"] = t.pop("assignee")
        self.assertInvalid(t, "project")
        self.assertInvalid(t, "assigned_agent")

    def test_reviewer_cannot_be_assignee(self):
        t = self.sample()
        t["reviewer"] = t["assignee"]
        self.assertInvalid(t, "independent reviewer")

    def test_reviewer_comparison_case_and_whitespace(self):
        t = self.sample()
        t["reviewer"] = "  " + t["assignee"].upper() + "  "
        self.assertInvalid(t, "independent reviewer")

    def test_distinct_reviewer_is_accepted(self):
        t = self.sample()
        t["reviewer"] = "separate-auditor-session"
        self.assertEqual(self.validate(t), [])

    def test_done_without_evidence_rejected(self):
        t = self.sample()
        t["status"] = "done"
        self.assertInvalid(t, "evidence")

    def test_done_without_verified_date_rejected(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type": "ci", "reference": "https://example.org/ci/123"}]
        self.assertInvalid(t, "evidence")

    def test_done_with_null_verified_date_rejected(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type": "ci", "reference": "ci-123", "verified_at": None}]
        self.assertInvalid(t, "evidence")

    def test_done_with_aware_verified_date_accepted(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type": "ci", "reference": "ci-123", "verified_at": "2026-10-10T09:20:00+03:00"}]
        self.assertEqual(self.validate(t), [])

    def test_naive_or_malformed_dates_rejected(self):
        for date in ("2026-10-10T09:20:00", "bad-date"):
            with self.subTest(date=date):
                t = self.sample()
                t["status"] = "done"
                t["evidence"] = [{"type": "ci", "reference": "ci-123", "verified_at": date}]
                self.assertInvalid(t, "date-time")

    def test_unknown_evidence_type_rejected(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type": "pretend", "reference": "okay", "verified_at": "2026-10-10T09:20:00Z"}]
        self.assertInvalid(t, "type")

    def test_previous_status_aliases_rejected(self):
        for stage in ("idea", "defined", "independent_review", "owner_gate_if_high_risk"):
            with self.subTest(stage=stage):
                t = self.sample()
                t["status"] = stage
                self.assertInvalid(t, "status")

    def test_owner_gate_is_waiting_not_approval(self):
        t = self.sample()
        t["status"] = "owner_gate"
        self.assertEqual(self.validate(t), [])
        self.assertIn("merge_main", t["requires_owner_approval"])
        self.assertNotIn("merge_main", t["allowed_actions"])

    def test_malformed_evidence_does_not_crash_validator(self):
        for bad in (None, 5, {"not": "an array"}):
            with self.subTest(bad=bad):
                t = self.sample()
                t["status"] = "done"
                t["evidence"] = bad
                self.assertInvalid(t, "evidence")

    def test_negative_budget_and_bad_actor_rejected(self):
        for field, bad in (("budget_usd", -1), ("budget_usd", True), ("assignee", ""), ("reviewer", "")):
            with self.subTest(field=field):
                t = self.sample()
                t[field] = bad
                self.assertInvalid(t, field)

    def test_handbook_example_uses_actual_schema(self):
        doc = (ROOT / "docs/PIXEL_PLUS_ONE_PERSON_COMPANY_OS.md").read_text(encoding="utf-8")
        fence = chr(96) * 3
        expression = r"## Task object:.*?" + re.escape(fence) + r"json\s*(\{.*?\})\s*" + re.escape(fence)
        match = re.search(expression, doc, re.DOTALL)
        self.assertIsNotNone(match, "must publish a canonical example")
        self.assertEqual(self.validate(json.loads(match.group(1))), [])

    def test_playbook_uses_contract_statuses(self):
        playbook = (ROOT / "docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md").read_text(encoding="utf-8")
        states = self.schema["properties"]["status"]["enum"]
        self.assertEqual(states, ["backlog", "ready", "working", "review", "owner_gate", "blocked", "done"])
        for stage in states:
            self.assertIn(stage, playbook)
        self.assertIn("validate_task.py", playbook)

    def test_no_fake_evidence_or_secrets_in_samples(self):
        raw = (CONTRACT / "examples.json").read_text(encoding="utf-8").lower()
        for sample in self.examples:
            self.assertEqual(sample["evidence"], [])
            self.assertNotEqual(sample["reviewer"], sample["assignee"])
            self.assertIn(sample["customer_data_policy"], ("none", "synthetic_only"))
        for secret in ("password", "api_key", "token_value", "national_id", "customer_phone"):
            self.assertNotIn(secret, raw)

    def test_cli_accepts_valid_samples_and_rejects_self_review(self):
        ok = subprocess.run([sys.executable, str(VALIDATOR), str(CONTRACT / "examples.json")],
                            capture_output=True, text=True, check=False)
        self.assertEqual(ok.returncode, 0, ok.stdout + ok.stderr)
        t = self.sample()
        t["reviewer"] = t["assignee"]
        with tempfile.TemporaryDirectory() as tmp:
            file = Path(tmp) / "invalid.json"
            file.write_text(json.dumps(t), encoding="utf-8")
            bad = subprocess.run([sys.executable, str(VALIDATOR), str(file)],
                                 capture_output=True, text=True, check=False)
            self.assertEqual(bad.returncode, 1, bad.stdout + bad.stderr)
            self.assertIn("independent reviewer", bad.stdout)


    def test_blank_actor_identities_rejected(self):
        for field in ("assignee", "reviewer"):
            for value in ("  ", chr(9), "  " + chr(10) + "  "):
                with self.subTest(field=field, value=value):
                    t = self.sample()
                    t[field] = value
                    self.assertInvalid(t, field)

    def test_decision_link_requires_actual_path(self):
        for bad in ("https://", "https://example.com", "DECISIONS.mdgarbage", "docs/", "docs/no-extension", "docs/../", "docs/../SECRET.md", "https:// ", "https://../fake"):
            with self.subTest(bad=bad):
                t = self.sample()
                t["decision_ref"] = bad
                self.assertInvalid(t, "decision_ref")

    def test_decision_link_examples_are_valid(self):
        for good in ("DECISIONS.md", "docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md", "https://example.org/article"):
            with self.subTest(good=good):
                t = self.sample()
                t["decision_ref"] = good
                self.assertEqual(self.validate(t), [])

    def test_date_syntax_is_strict_even_when_format_assertion_off(self):
        for bad in ("2026-10-10 09:20:00+03:00", "2026-10-10T09:20+03:00", "2026-10-10T09:20:00", "2026-02-30T09:20:00Z"):
            with self.subTest(bad=bad):
                t = self.sample()
                t["status"] = "done"
                t["evidence"] = [{"type":"ci","reference":"https://example.org/ci/1","verified_at":bad}]
                self.assertInvalid(t, "verified_at")

    def test_owner_gate_requires_named_pending_approval(self):
        t = self.sample()
        t["status"] = "owner_gate"
        t["requires_owner_approval"] = []
        self.assertInvalid(t, "requires_owner_approval")

    def test_owner_gate_refuses_blank_approval_name(self):
        t = self.sample()
        t["status"] = "owner_gate"
        t["requires_owner_approval"] = ["    "]
        self.assertInvalid(t, "requires_owner_approval")

    def test_cross_session_handoff_fields_are_required(self):
        for field in ("current_commit","branch","open_prs","known_errors","tests_run","tests_skipped","next_action"):
            with self.subTest(field=field):
                t = self.sample()
                t.pop(field)
                self.assertInvalid(t, field)

    def test_cross_session_lists_are_strictly_typed(self):
        for field in ("open_prs","known_errors","tests_run","tests_skipped"):
            with self.subTest(field=field):
                t = self.sample()
                t[field] = "one text entry instead of array"
                self.assertInvalid(t, field)

    def test_cross_session_pr_needs_url_and_commit_needs_sha(self):
        t = self.sample()
        t["open_prs"] = ["https://example.org/pr/123"]
        self.assertInvalid(t, "open_prs")
        t = self.sample()
        t["current_commit"] = "not-a-commit"
        self.assertInvalid(t, "current_commit")

    def test_handoffs_accept_real_reviewable_context(self):
        t = self.sample()
        t["branch"] = "review/store-safe-fix"
        t["current_commit"] = "a" * 40
        t["open_prs"] = ["https://github.com/coolman1984/Store/pull/20"]
        t["known_errors"] = ["Licence Studio unavailable for end-to-end field test"]
        t["tests_run"] = ["unittest suite: 300 passed, 0 failed"]
        t["tests_skipped"] = ["Real 58mm receipt printer unavailable"]
        self.assertEqual(self.validate(t), [])

    def test_schema_has_mandatory_handoff_and_owner_gate_conditions(self):
        schema = self.schema
        for field in ("branch","current_commit","open_prs","known_errors","tests_run","tests_skipped","next_action"):
            self.assertIn(field, schema["required"])
        owner_gate_cond = schema["allOf"][1]
        self.assertEqual(owner_gate_cond["if"]["properties"]["status"]["const"], "owner_gate")
        self.assertEqual(owner_gate_cond["then"]["properties"]["requires_owner_approval"]["minItems"], 1)


if __name__ == "__main__":
    unittest.main()
