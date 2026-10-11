"""The global design standard is wired into what agents read, scoped by connectivity tier, and enforced by core controls (not only written)."""
import json
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = (ROOT / 'design-factory' / 'DESIGN.md').read_text(encoding='utf-8')
CONTROLS = {c['id']: c for c in json.loads((ROOT / 'factory' / 'controls.json').read_text(encoding='utf-8'))['controls']}
SCHEMA = json.loads((ROOT / 'factory' / 'product.schema.json').read_text(encoding='utf-8'))


class DesignStandard(unittest.TestCase):
    def test_every_ui_agent_is_sent_to_the_global_standard_first(self):
        agents = (ROOT / 'design-factory' / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('design-factory/DESIGN.md', agents.split('## Creative Factory', 1)[0], 'first read of the design contract')
        root = (ROOT / 'AGENTS.md').read_text(encoding='utf-8')
        self.assertIn('design-factory/DESIGN.md', root)

    def test_no_network_behaviour_is_defined_for_every_connectivity_tier(self):
        tiers = SCHEMA['properties']['connectivity']['properties']['tier']['enum']
        section = DESIGN.split('## What «no network» looks like, by connectivity tier', 1)[1].split('\n## ', 1)[0]
        for tier in tiers:
            self.assertRegex(section, rf'\|\s*`{tier}`\s*\|', tier)
        self.assertRegex(section.split('`cloud_only`', 1)[1], r'Not asked to work offline')
        # the old unconditional wording must not come back
        self.assertNotRegex(DESIGN, r'keyboard navigation, offline operation')

    def test_the_gates_by_class_are_core_controls_that_apply_to_the_visual_profiles(self):
        section = DESIGN.split('## Quality gates by class', 1)[1].split('\n## ', 1)[0]
        listed = re.findall(r'\|\s*(UX-\d\d|PERF-01|A11Y-01)\s*\|', section)
        self.assertEqual(sorted(listed), sorted({'UX-04', 'UX-08', 'UX-09', 'PERF-01', 'A11Y-01'}))
        for cid in listed:
            c = CONTROLS[cid]
            self.assertEqual(c['tier'], 'core', cid)
            self.assertTrue({'desktop', 'lan', 'saas'} <= set(c['profiles']), cid)
            self.assertTrue(c['required_if_applies'], cid)

    def test_the_network_control_names_every_tier_rule(self):
        text = CONTROLS['UX-04']['requirement']
        for word in ('standalone', 'office_server', 'office_mesh', 'cloud_sync', 'cloud_only'):
            self.assertIn(word, text)

    def test_the_store_is_not_named_after_the_owners_accounting_product(self):
        self.assertNotRegex(DESIGN, r'(?i)working brand proposal:\s*\*\*MIZAN')
        self.assertIn('withdrawn', DESIGN)
        self.assertIn('Al-Store', DESIGN)


if __name__ == '__main__':
    unittest.main()
