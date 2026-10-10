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


    def test_owner_gate_blocks_contradictory_permissions(self):
        t = self.sample()
        t["status"] = "owner_gate"
        t["allowed_actions"].append("production_deploy")
        self.assertInvalid(t, "allowed_actions")

    def test_other_statuses_block_approval_permission_overlap(self):
        t = self.sample()
        t["allowed_actions"].append("merge_main")
        self.assertInvalid(t, "allowed_actions")

    def test_owner_gate_does_not_allow_case_or_space_alias(self):
        t = self.sample()
        t["status"] = "owner_gate"
        t["allowed_actions"].append("  PRODUCTION_DEPLOY  ")
        self.assertInvalid(t, "allowed_actions")

    def test_local_decision_path_must_exist(self):
        t = self.sample()
        t["decision_ref"] = "docs/THIS_FILE_DOES_NOT_EXIST.md"
        self.assertInvalid(t, "decision_ref")

    def test_local_decision_file_exists_in_repository(self):
        t = self.sample()
        t["decision_ref"] = "DECISIONS.md"
        self.assertEqual(self.validate(t), [])

    def test_punctuation_only_approval_name_is_rejected(self):
        for bad in ("---", "...", "__", "---!!!"):
            with self.subTest(bad=bad):
                t = self.sample()
                t["status"] = "owner_gate"
                t["requires_owner_approval"] = [bad]
                self.assertInvalid(t, "requires_owner_approval")

    def test_punctuation_only_evidence_reference_is_rejected(self):
        for bad in ("---", "......", "----///"):
            with self.subTest(bad=bad):
                t = self.sample()
                t["status"] = "done"
                t["evidence"] = [{"type":"customer_acceptance","reference":bad,
                                  "verified_at":"2026-10-10T09:20:00Z"}]
                self.assertInvalid(t, "reference")

    def test_good_done_reference_and_approval_name(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type":"ci","reference":"https://github.com/coolman1984/Apps-Factory/actions/runs/38032982570",
                          "verified_at":"2026-10-10T09:20:00Z"}]
        self.assertEqual(self.validate(t), [])
        t["status"] = "owner_gate"
        t["requires_owner_approval"] = ["release_prod"]
        self.assertEqual(self.validate(t), [])


    def test_padded_single_letter_evidence_rejected(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type":"customer_acceptance", "reference":"     a",
                          "verified_at":"2026-10-10T09:20:00Z"}]
        self.assertInvalid(t, "reference")

    def test_padded_one_letter_next_action_rejected(self):
        t = self.sample()
        t["next_action"] = "       x"
        self.assertInvalid(t, "next_action")

    def test_padded_short_goal_rejected(self):
        t = self.sample()
        t["goal"] = "           abc"
        self.assertInvalid(t, "goal")

    def test_informative_values_with_real_spaces_pass(self):
        t = self.sample()
        t["goal"] = "Review the real Store workflow carefully"
        t["next_action"] = "Inspect and test the next build"
        t["status"] = "done"
        t["evidence"] = [{"type":"ci","reference":"ci-run-12345",
                          "verified_at":"2026-10-10T09:20:00Z"}]
        self.assertEqual(self.validate(t), [])


    def test_schema_calendar_rejects_impossible_days(self):
        pattern = self.schema["properties"]["evidence"]["items"]["properties"]["verified_at"]["pattern"]
        for bad in ("2026-02-30T09:20:00Z", "2025-02-29T09:20:00Z",
                    "1900-02-29T09:20:00Z", "2100-02-29T09:20:00Z",
                    "2026-04-31T09:20:00Z", "0000-01-01T09:20:00Z"):
            with self.subTest(bad=bad):
                self.assertIsNone(re.fullmatch(pattern, bad))
                t = self.sample()
                t["status"] = "done"
                t["evidence"] = [{"type":"ci", "reference":"ci-run-1234",
                                  "verified_at":bad}]
                self.assertInvalid(t, "verified_at")

    def test_schema_calendar_accepts_valid_leap_years(self):
        pattern = self.schema["properties"]["evidence"]["items"]["properties"]["verified_at"]["pattern"]
        for good in ("2024-02-29T09:20:00Z", "2000-02-29T09:20:00+03:00",
                     "2026-02-28T09:20:00Z", "2026-04-30T09:20:00Z"):
            with self.subTest(good=good):
                self.assertIsNotNone(re.fullmatch(pattern, good))
                t = self.sample()
                t["status"] = "done"
                t["evidence"] = [{"type":"ci", "reference":"ci-run-1234",
                                  "verified_at":good}]
                self.assertEqual(self.validate(t), [])

    def test_cli_rejects_duplicate_task_ids_in_one_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicates.json"
            path.write_text(json.dumps([self.sample(), self.sample()]), encoding="utf-8")
            result = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("duplicate task identifier", result.stdout)


    def test_references_and_identity_fields_reject_trailing_newlines(self):
        for field, value in (("task_id", "PX-001" + chr(10)),
                             ("current_commit", "abcdef0" + chr(10)),
                             ("branch", "feature/x" + chr(10)),
                             ("decision_ref", "https://example.org/source" + chr(10))):
            with self.subTest(field=field):
                t = self.sample()
                t[field] = value
                self.assertInvalid(t, field)
                pattern = self.schema["properties"][field]["pattern"]
                self.assertIsNone(re.search(pattern, value),
                                  "portable schema must reject trailing line terminators")

    def test_open_pr_url_rejects_trailing_newline(self):
        t = self.sample()
        t["open_prs"] = ["https://github.com/coolman1984/Store/pull/20" + chr(10)]
        self.assertInvalid(t, "open_prs")

    def test_completed_evidence_date_rejects_trailing_newline(self):
        t = self.sample()
        t["status"] = "done"
        t["evidence"] = [{"type":"ci", "reference":"ci-run-1234",
                          "verified_at":"2024-02-29T09:20:00Z" + chr(10)}]
        self.assertInvalid(t, "verified_at")

    def test_batch_id_deduplication_canonicalizes_trailing_whitespace(self):
        first = self.sample()
        second = self.sample()
        second["task_id"] = first["task_id"] + chr(10)
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "duplicates.json"
            path.write_text(json.dumps([first, second]), encoding="utf-8")
            result = subprocess.run([sys.executable, str(VALIDATOR), str(path)],
                                    capture_output=True, text=True, check=False)
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            self.assertIn("duplicate task identifier", result.stdout)



class CompanyOSSafetyTests(unittest.TestCase):
    """What the offline validator now enforces beyond the shape: no pre-granted sensitive action, no «done» over failed or skipped tests, no
    work done twice, and a way to see interrupted work. All of it is metadata: nothing here runs an agent or authorizes anything."""

    @classmethod
    def setUpClass(cls):
        mod = runpy.run_path(str(VALIDATOR))
        cls.validate, cls.conflicts, cls.stale = (staticmethod(mod[n]) for n in ("validate_task", "batch_conflicts", "stale_tasks"))
        cls.examples = json.loads((CONTRACT / "examples.json").read_text(encoding="utf-8"))

    def sample(self, **fields):
        task = copy.deepcopy(self.examples[0])
        task.update(fields)
        return task

    def done(self, **fields):
        base = dict(status="done", current_commit="a" * 40, branch="fix/x-1", tests_run=["python -m unittest discover -s tests: 113 passed"],
                    evidence=[{"type": "ci", "reference": "https://github.com/coolman1984/Store/actions/runs/1", "verified_at": "2026-10-10T06:00:00Z"}])
        base.update(fields)
        return self.sample(**base)

    def test_a_handoff_cannot_pre_grant_money_customers_production_or_secrets(self):
        for action in ("send_payment", "refund_customer", "deploy_to_production", "publish_release", "merge_main", "force_push", "delete_customer_data",
                       "send_whatsapp", "post_announcement", "rotate_signing_key", "read_secrets", "push_main", "Spend-Budget", "drop table",
                       "read_customer_data", "export_customer_records", "contact_customer", "call_client", "upload_backup", "read_real_database",
                       "issue_paid_license", "grant_licence", "activate_trial_license", "revoke_code"):
            problems = self.validate(self.sample(allowed_actions=["read_repo", action]))
            self.assertTrue(any("not on the allowlist" in p and action in p for p in problems), (action, problems))

    def test_only_actions_on_the_allowlist_are_granted_and_anything_else_is_refused(self):
        for action in ("read_repo", "run_synthetic_tests", "draft_report", "comment_on_pr", "push_branch", "write_tests", "  Read_Repo  ",
                       "edit_files", "commit_changes", "run_linter", "write_code", "create_branch"):   # ordinary coding work needs no owner approval
            self.assertEqual([p for p in self.validate(self.sample(allowed_actions=[action])) if "allowed_actions" in p], [], action)
        for action in ("inspect_payload", "frobnicate", "read_synthetic_data", "do_anything", "shell"):   # unknown is refused too: a word list is never complete
            self.assertTrue(any("not on the allowlist" in p for p in self.validate(self.sample(allowed_actions=[action]))), action)

    def test_the_same_sensitive_action_is_fine_as_a_request_for_approval(self):
        task = self.sample(allowed_actions=["read_repo"], requires_owner_approval=["merge_main", "production_deploy", "send_payment"])
        self.assertEqual(self.validate(task), [])

    def test_done_needs_clean_tests_and_no_known_errors(self):
        self.assertEqual(self.validate(self.done()), [])
        self.assertTrue(any("known errors" in p for p in self.validate(self.done(known_errors=["one test still red"]))))
        self.assertTrue(any("skipped tests are not green" in p for p in self.validate(self.done(tests_skipped=["browser tests: no Chromium"]))))
        self.assertTrue(any("must list the tests" in p for p in self.validate(self.done(tests_run=[]))))
        self.assertEqual(self.validate(self.done(current_commit=None, branch=None, tests_run=[])), [], "a task with no code needs no test list")

    def test_a_recorded_failure_or_skip_in_the_test_list_is_never_green(self):
        for line in ("pytest: 3 failed", "113 passed, 2 failed", "FAILED test_x", "5 skipped", "2 errors in 4s", "browser tests: not green", "suite is red"):
            self.assertTrue(any("records a failure or a skip" in p for p in self.validate(self.done(tests_run=[line]))), line)
        for line in ("1 failing", "pytest: failed", "npm test exited with code 1", "tests aborted", "browser run timed out", "FAIL tests/x.py", "2 errors"):
            self.assertTrue(any("records a failure" in p for p in self.validate(self.done(tests_run=[line]))), line)
        for line in ("164 passed, 12 skips", "50 passed, 3 skip", "12 passed, 1 errored", "5 failed 0 passed", "2 failed 0 warnings", "0 passed", "pass 0\nfail 3",
                     "suite timed out", "exit 1", "# fail 2"):                                    # review of PR #42: holes found by trying real summaries
            self.assertTrue(self.validate(self.done(tests_run=[line])), line)
        for line in ("error handling suite: 12 passed", "tests/test-errors.py: 12 passed"):   # a word inside a name is not a failure
            self.assertEqual(self.validate(self.done(tests_run=[line])), [], line)
        for line in ("ran the tests", "tests were run on the branch"):                       # no stated result is not a pass
            self.assertTrue(any("does not say the tests passed" in p for p in self.validate(self.done(tests_run=[line]))), line)
        for line in ("python -m unittest discover -s tests: 113 passed, 0 failed, 0 skipped", "node --test: 34 passed", "Ran 304 tests OK", "all green, no failures",
                     "# pass 34\n# fail 0\n# skipped 0", "unittest OK (failures=0)", "Failed: 0, Passed: 12"):   # the zero may come after the word as well as before
            self.assertEqual(self.validate(self.done(tests_run=[line])), [], line)

    def test_the_same_work_cannot_be_carried_twice(self):
        a = self.sample(task_id="PX-101", status="working", branch="fix/shared-1")
        b = self.sample(task_id="PX-102", status="ready", branch="fix/shared-1")
        self.assertTrue(any("already being worked on by PX-101" in p for p in self.conflicts([a, b])))
        pr = "https://github.com/coolman1984/Store/pull/20"
        c, d = self.sample(task_id="PX-103", status="review", open_prs=[pr]), self.sample(task_id="PX-104", status="owner_gate", open_prs=[pr])
        self.assertTrue(any("already carried by PX-103" in p for p in self.conflicts([c, d])))
        e = self.sample(task_id="PX-101")
        self.assertTrue(any("duplicate task identifier" in p for p in self.conflicts([a, e])))
        finished = self.sample(task_id="PX-105", status="done", branch="fix/shared-1")
        self.assertEqual(self.conflicts([a, finished]), [], "a finished task does not hold its branch")
        self.assertEqual(self.conflicts([self.sample(task_id="PX-106", branch=None), self.sample(task_id="PX-107", branch=None)]), [])
        other = self.sample(task_id="PX-108", status="working", branch="fix/shared-1", project="Factory")
        self.assertEqual(self.conflicts([a, other]), [], "the same branch name in another project is not the same work")
        again = self.sample(task_id="PX-109", status="working", branch="fix/shared-1", project=a["project"])
        self.assertTrue(self.conflicts([a, again]))

    def test_the_command_line_checks_several_files_together(self):
        a = self.sample(task_id="PX-201", status="working", branch="fix/cli-1")
        b = self.sample(task_id="PX-202", status="ready", branch="fix/cli-1")
        with tempfile.TemporaryDirectory() as d:
            fa, fb = Path(d, "a.json"), Path(d, "b.json")
            fa.write_text(json.dumps(a), encoding="utf-8")
            fb.write_text(json.dumps(b), encoding="utf-8")
            both = subprocess.run([sys.executable, str(VALIDATOR), str(fa), str(fb)], capture_output=True, text=True)
            self.assertEqual(both.returncode, 1, both.stdout)
            self.assertIn("CONFLICT", both.stdout)
            alone = subprocess.run([sys.executable, str(VALIDATOR), str(fa)], capture_output=True, text=True)
            self.assertEqual(alone.returncode, 0, alone.stdout + alone.stderr)

    def test_interrupted_work_is_seen_and_can_be_taken_over(self):
        from datetime import datetime, timezone
        now = datetime(2026, 10, 10, 12, 0, tzinfo=timezone.utc)
        fresh = self.sample(task_id="PX-301", status="working", updated_at="2026-10-10T11:00:00Z")
        old = self.sample(task_id="PX-302", status="working", updated_at="2026-10-09T09:00:00Z")
        never = self.sample(task_id="PX-303", status="working")
        waiting = self.sample(task_id="PX-304", status="ready", updated_at="2025-01-01T00:00:00Z")
        self.assertEqual(self.stale([fresh, old, never, waiting], now, 24), ["PX-302", "PX-303"])
        self.assertEqual(self.validate(fresh), [])
        self.assertTrue(self.validate(self.sample(updated_at="yesterday")), "the stamp is as strict as every other date")
        future = self.sample(task_id="PX-305", status="working", updated_at="2099-01-01T00:00:00Z")
        self.assertEqual(self.stale([future], now, 24), ["PX-305"], "a stamp in the future never makes work look fresh")
        odd = self.sample(task_id="PX-306", status="working", updated_at="2026-10-10T11:30:00.5Z")   # a one-digit fraction parses on every Python
        self.assertEqual(self.validate(odd), [])
        self.assertEqual(self.stale([odd], now, 24), [])
        with tempfile.TemporaryDirectory() as d:
            f = Path(d, "t.json")
            f.write_text(json.dumps([fresh, old]), encoding="utf-8")
            run = subprocess.run([sys.executable, str(VALIDATOR), str(f), "--stale-hours", "24", "--now", "2026-10-10T12:00:00Z"], capture_output=True, text=True)
            self.assertEqual(run.returncode, 3, run.stdout)
            self.assertIn("STALE: PX-302", run.stdout)
            self.assertNotIn("STALE: PX-301", run.stdout)
            messy = Path(d, "m.json")        # one invalid task must not hide the takeover signal of another
            messy.write_text(json.dumps([old, self.sample(task_id="PX-307", goal="x")]), encoding="utf-8")
            both = subprocess.run([sys.executable, str(VALIDATOR), str(messy), "--stale-hours", "24", "--now", "2026-10-10T12:00:00Z"], capture_output=True, text=True)
            self.assertEqual(both.returncode, 1, both.stdout)
            self.assertIn("STALE: PX-302", both.stdout)
            naive = subprocess.run([sys.executable, str(VALIDATOR), str(f), "--stale-hours", "24", "--now", "2026-10-10T12:00:00"], capture_output=True, text=True)
            self.assertEqual(naive.returncode, 2, naive.stdout + naive.stderr)
            self.assertIn("timezone", naive.stderr)


if __name__ == "__main__":
    unittest.main()
