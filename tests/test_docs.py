"""Docs checks (standard library only): the 5 living docs exist, AGENTS.md has the 3-file read order,
no relative link in the factory's own Markdown is broken, and the living docs carry no legal framing."""
import os
import re
import unittest
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parents[1]
LIVING = ["README.md", "RULES.md", "PARTS.md", "PLAYBOOK.md", "DECISIONS.md"]
# vendored or external trees: not ours to fix
SKIP_TOP = {"packages", "apps", "templates"}
SKIP_ANY = {".git", "node_modules", "__pycache__"}
LEGAL_WORDS = re.compile(r"\b(law|legal|lawyer|jurisdiction|compliance|regulator)\b", re.I)

FENCE = re.compile(r"^(```|~~~).*?^\1[^\n]*$", re.S | re.M)
CODE_SPAN = re.compile(r"(`+)(?:(?!\1).)+?\1", re.S)
INLINE_LINK = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REF_LINK = re.compile(r"^\s{0,3}\[[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$", re.M)


def submodule_paths():
    gm = ROOT / ".gitmodules"
    if not gm.exists():
        return set()
    return {m.group(1).strip() for m in re.finditer(r"^\s*path\s*=\s*(.+)$", gm.read_text(encoding="utf-8"), re.M)}


def markdown_files():
    subs = submodule_paths()
    for dirpath, dirnames, filenames in os.walk(ROOT):
        rel = Path(dirpath).relative_to(ROOT)
        keep = []
        for d in dirnames:
            r = (rel / d).as_posix()
            if d in SKIP_ANY or r in subs or (rel == Path(".") and d in SKIP_TOP):
                continue
            keep.append(d)
        dirnames[:] = keep
        for f in filenames:
            if f.endswith(".md"):
                yield Path(dirpath) / f


def links_of(text):
    text = FENCE.sub("", text)
    text = CODE_SPAN.sub("", text)
    return INLINE_LINK.findall(text) + REF_LINK.findall(text)


def is_external(target):
    return bool(re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*:", target)) or target.startswith(("#", "//"))


class DocsTests(unittest.TestCase):
    def test_five_living_docs_exist(self):
        for name in LIVING:
            self.assertTrue((ROOT / name).is_file(), f"{name} is missing")

    def test_agents_read_order_is_three_files(self):
        text = (ROOT / "AGENTS.md").read_text(encoding="utf-8")
        section = text.split("## Read order", 1)[1].split("\n## ", 1)[0]
        items = re.findall(r"^\d+\.\s*\[([^\]]+)\]", section, re.M)
        self.assertEqual(items, ["README.md", "RULES.md", "PARTS.md"], section)

    def test_no_broken_relative_links(self):
        broken = []
        for md in markdown_files():
            for target in links_of(md.read_text(encoding="utf-8")):
                if is_external(target):
                    continue
                path = unquote(target.split("#", 1)[0].split("?", 1)[0])
                if not path or path.startswith("/"):
                    continue
                if not (md.parent / path).exists():
                    broken.append(f"{md.relative_to(ROOT).as_posix()} -> {target}")
        self.assertEqual(broken, [], "broken relative links:\n" + "\n".join(broken))

    def test_living_docs_have_no_legal_framing(self):
        for name in LIVING + ["AGENTS.md", "CLAUDE.md", "GEMINI.md"]:
            text = (ROOT / name).read_text(encoding="utf-8")
            hit = LEGAL_WORDS.search(text)
            self.assertIsNone(hit, f"{name}: legal wording {hit.group(0)!r}" if hit else "")

    def test_link_checker_sees_a_broken_link(self):
        bad = "see [x](nope/missing.md) and `[y](ignored.md)`\n```\n[z](also-ignored.md)\n```\n[ok](https://a.b) [a](#top)"
        self.assertEqual(links_of(bad), ["nope/missing.md", "https://a.b", "#top"])


if __name__ == "__main__":
    unittest.main()
