"""Keep mandatory external-learning instructions discoverable to coding agents.

This tests documentation wiring only. It does NOT mean external tools have been
installed, licensed, or validated in a real target environment.
"""
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[1]
CASES = "docs/knowledge/AGENT_USE_CASES_MANDATORY_LEARNING.md"
MANIM = "docs/knowledge/MANIMGX_MANDATORY_REFERENCE.md"


class MandatoryResearchContractTests(unittest.TestCase):
    def test_entrypoints_link_both_references(self):
        for entrypoint in ("AGENTS.md", "design-factory/AGENTS.md"):
            with self.subTest(entrypoint=entrypoint):
                content = (ROOT / entrypoint).read_text(encoding="utf-8")
                self.assertIn("AGENT_USE_CASES_MANDATORY_LEARNING.md", content)
                self.assertIn("MANIMGX_MANDATORY_REFERENCE.md", content)

    def test_creative_workflow_requires_task_fit_and_license(self):
        content = (ROOT / "design-factory/CREATIVE_AGENT_PLAYBOOK.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("MANIMGX_MANDATORY_REFERENCE.md", content)
        self.assertIn("AGENT_USE_CASES_MANDATORY_LEARNING.md", content)
        self.assertIn("GPL", content)
        self.assertIn("Never install", content)

    def test_reference_sources_are_present(self):
        case_text = (ROOT / CASES).read_text(encoding="utf-8")
        manim_text = (ROOT / MANIM).read_text(encoding="utf-8")
        self.assertIn("https://agentusecases.ai/", case_text)
        self.assertIn("failure", case_text.lower())
        self.assertIn("NOT VERIFIED", case_text)
        self.assertIn("https://github.com/academa-labs/manimgx", manim_text)
        self.assertIn("https://manimgx.academa.ai/", manim_text)
        self.assertIn("3.13", manim_text)
        self.assertIn("GPL", manim_text)
        self.assertIn("not applicable", manim_text.lower())

    def test_catalogue_links_references(self):
        catalogue = (ROOT / "docs/knowledge/SCREENSHOT_AGENT_TOOLS_CANDIDATES_2026-10-11.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("MANIMGX_MANDATORY_REFERENCE.md", catalogue)
        self.assertIn("AGENT_USE_CASES_MANDATORY_LEARNING.md", catalogue)


if __name__ == "__main__":
    unittest.main()
