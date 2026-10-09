import copy
import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))
import factory


class FourPlanContractTests(unittest.TestCase):
    def store(self):
        return copy.deepcopy(factory.load(ROOT / "examples/al-store-product.json"))

    def reference(self):
        return copy.deepcopy(factory.load(ROOT / "examples/multi-branch-reference.json"))

    def test_existing_products_remain_valid_without_commercial_plan(self):
        product = self.store()
        self.assertNotIn("commercial_plan", product)
        self.assertEqual([], factory.valid_product(product)[0])

    def test_solo_requires_one_local_windows_pc_and_can_use_existing_office_server(self):
        product = self.store()
        product["commercial_plan"] = "solo"
        self.assertEqual([], factory.valid_product(product)[0])
        product["connectivity"]["sites"] = "multi"
        self.assertTrue(any("Solo plan" in x for x in factory.valid_product(product)[0]))

    def test_paid_solo_cannot_be_released_without_real_off_device_proof(self):
        product = self.store()
        product["commercial_plan"] = "solo"
        errors, _ = factory.valid_product(product, release=True)
        self.assertTrue(any("off_device_cloud_restore" in x for x in errors), errors)
        product["evidence"]["off_device_cloud_restore"] = "PENDING"
        self.assertTrue(any("off_device_cloud_restore" in x for x in factory.valid_product(product, release=True)[0]))
        product["evidence"]["off_device_cloud_restore"] = "Clean Windows restore run 2026-10-09, case 1"
        self.assertFalse(any("off_device_cloud_restore" in x for x in factory.valid_product(product, release=True)[0]))

    def test_connected_and_mobile_ops_require_sync_and_mobile_app(self):
        product = self.store()
        for plan in ("connected", "mobile_ops"):
            product["commercial_plan"] = plan
            self.assertTrue(any("cloud_sync" in x for x in factory.valid_product(product)[0]))
        product = self.reference()
        product["commercial_plan"] = "connected"
        self.assertEqual([], factory.valid_product(product)[0])
        errors, _ = factory.valid_product(product, release=True)
        self.assertTrue(any("owner_mobile_read_only_acceptance" in x for x in errors), errors)
        self.assertTrue(any("multi_device_sync_acceptance" in x for x in errors), errors)
        product["commercial_plan"] = "mobile_ops"
        errors, _ = factory.valid_product(product, release=True)
        self.assertTrue(any("mobile_write_acceptance" in x for x in errors), errors)

    def test_cloud_business_must_be_cloud_first_and_cannot_claim_untested_hosting(self):
        product = self.reference()
        product["commercial_plan"] = "cloud_business"
        self.assertTrue(any("hosted browser" in x for x in factory.valid_product(product)[0]))
        product["deployment"] = "saas"
        product["connectivity"]["tier"] = "cloud_only"
        product["connectivity"]["clients"] = ["browser", "mobile_pwa"]
        product["connectivity"].pop("mobile_offline_actions", None)
        product["monetization"]["entitlement_method"] = "cloud_entitlement"
        self.assertEqual([], factory.valid_product(product)[0])
        errors, _ = factory.valid_product(product, release=True)
        self.assertTrue(any("hosted_business_acceptance" in x for x in errors))

    def test_schema_names_are_in_sync_with_validator(self):
        schema = factory.load(ROOT / "factory/product.schema.json")
        self.assertEqual(set(schema["properties"]["commercial_plan"]["enum"]), factory.COMMERCIAL_PLANS)
        self.assertIn("off_device_cloud_restore", schema["properties"]["evidence"]["properties"])


if __name__ == "__main__":
    unittest.main()
