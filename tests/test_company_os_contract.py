"""Pixel Plus one-person-company handoff contract: pure stdlib, no accounts or network."""
import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONTRACT = ROOT / "company-os"

class CompanyOSContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = json.loads((CONTRACT / "task.schema.json").read_text(encoding="utf-8"))
        cls.examples = json.loads((CONTRACT / "examples.json").read_text(encoding="utf-8"))

    def test_schema_and_examples_exist(self):
        self.assertEqual(self.schema["$schema"], "https://json-schema.org/draft/2020-12/schema")
        self.assertGreaterEqual(len(self.examples), 2)
        self.assertEqual(len({x["task_id"] for x in self.examples}), len(self.examples))

    def test_required_fields_present_in_each_handoff(self):
        required = set(self.schema["required"])
        allowed = set(self.schema["properties"])
        for x in self.examples:
            with self.subTest(task=x["task_id"]):
                self.assertEqual(required-set(x), set())
                self.assertEqual(set(x)-allowed, set())
                self.assertTrue(x["task_id"].startswith("PX-"))
                self.assertGreaterEqual(len(x["acceptance"]), 1)
                self.assertNotIn("production_deploy", x["allowed_actions"])
                self.assertNotIn("send_customer_message", x["allowed_actions"])
                self.assertGreaterEqual(x["budget_usd"], 0)
                self.assertIn(x["risk"], self.schema["properties"]["risk"]["enum"])
                self.assertIn(x["status"], self.schema["properties"]["status"]["enum"])
                self.assertNotEqual(x["reviewer"], x["assignee"])

    def test_no_claimed_evidence_or_secret_in_sample(self):
        for example in self.examples:
            self.assertEqual(example["evidence"], [])
            self.assertIn(example["customer_data_policy"], ("none", "synthetic_only"))
        content = (CONTRACT / "examples.json").read_text(encoding="utf-8").lower()
        for secret in ("password", "token_value", "api_key", "customer_phone", "national_id"):
            self.assertNotIn(secret, content)

if __name__ == "__main__":
    unittest.main()
