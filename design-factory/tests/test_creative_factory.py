"""Creative Factory v2 source/contract tests; not a substitute for visual inspection."""
import json
from html.parser import HTMLParser
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT=Path(__file__).resolve().parents[2]
D=ROOT/"design-factory"

class Html(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[];self.assets=[];self.depth=0;self.buttons=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if "id" in a:self.ids.append(a["id"])
        if tag=="script" and "src" in a:self.assets.append(a["src"])
        if tag=="link" and a.get("rel")=="stylesheet":self.assets.append(a["href"])
        if "data-depth" in a:self.depth+=1
        if tag=="button":self.buttons.append(a)
        for key in a:
            assert not key.startswith("on"),"No inline event handlers"

class CreativeFactoryTests(unittest.TestCase):
    def test_all_new_sources_pin_exact_gitlinks(self):
        obj=json.loads((D/"creative-sources.lock.json").read_text(encoding="utf-8"))
        self.assertEqual(len(obj["sources"]),17)
        ids=set()
        for s in obj["sources"]:
            self.assertNotIn(s["id"],ids);ids.add(s["id"])
            self.assertEqual(len(s["commit"]),40)
            p="design-factory/upstream/"+s["id"]
            x=subprocess.run(["git","ls-files","--stage","--",p],cwd=ROOT,capture_output=True,text=True,check=True)
            self.assertIn("160000 "+s["commit"],x.stdout)
            self.assertIn("linked-reference-not-executed",s["integration_status"])
            self.assertTrue("license" in s["supply_chain_gate"].lower() or "licence" in s["supply_chain_gate"].lower())

    def test_all_recipes_and_profiles(self):
        spec=json.loads((D/"creative-recipes/schema.json").read_text(encoding="utf-8"))
        self.assertEqual(spec["properties"]["schema_version"]["const"],"1.0")
        examples=list((D/"creative-recipes").glob("*.json"))
        self.assertGreaterEqual(len(examples),5)
        profiles=set()
        for file in examples:
            if file.name=="schema.json":continue
            value=json.loads(file.read_text(encoding="utf-8"))
            self.assertEqual(value["schema_version"],"1.0")
            profiles.add(value["profile"])
            self.assertTrue(value["acceptance"])
            for layer in value["layers"]:
                self.assertGreaterEqual(layer["depth"],0)
                self.assertLessEqual(layer["depth"],1)
        self.assertTrue({"essential","polished","cinematic","film"}.issubset(profiles))

    def test_lab_has_no_runtime_network_or_missing_files(self):
        path=D/"creative-lab/index.html"
        h=Html();h.feed(path.read_text(encoding="utf-8"))
        self.assertEqual(len(set(h.ids)),len(h.ids))
        self.assertEqual(h.depth,4)
        self.assertGreaterEqual(len(h.buttons),5)
        for a in h.assets:
            self.assertNotIn("://",a)
            self.assertTrue((path.parent/a).resolve().is_file(),a)
        script=(D/"creative-lab/creative.js").read_text(encoding="utf-8")
        for s in ("window.__AF_CREATIVE__","requestAnimationFrame","cancelAnimationFrame",
                  "prefers-reduced-motion","visibilitychange","setLang","recipe()","seek(ms)"):
            self.assertIn(s,script)
        self.assertNotIn("eval(",script)
        self.assertNotIn("fetch(",script)

    def test_drop_in_primitives_are_progressive_and_offline(self):
        js=(D/"core/creative-primitives.js").read_text(encoding="utf-8")
        css=(D/"core/creative-effects.css").read_text(encoding="utf-8")
        self.assertIn("IntersectionObserver",js)
        self.assertIn("prefers-reduced-motion",css)
        self.assertIn("af-motion-ready",css)
        self.assertNotIn("fetch(",js)
        self.assertIn("window.AFCreative",js)

    def test_installer_creative_opt_in_and_no_overwrite(self):
        sys.path.insert(0,str(D/"scripts"))
        import install
        with tempfile.TemporaryDirectory() as tmp:
            target=Path(tmp)
            standard=install.execute(target,apply=False)
            self.assertTrue(all("creative/creative-effects.css"!=p for p,_,_,_ in standard))
            withcreative=install.execute(target,apply=True,creative=True)
            self.assertTrue(any(p=="creative/creative-effects.css" for p,_,_,_ in withcreative))
            file=target/"creative/creative-effects.css"
            self.assertTrue(file.is_file())
            file.write_text("customer owned",encoding="utf-8")
            install.execute(target,apply=True,creative=True)
            self.assertEqual(file.read_text(encoding="utf-8"),"customer owned")

    def test_agent_routers_reference_creative_playbook(self):
        for path in ("AGENTS.md","design-factory/AGENTS.md","design-factory/skills/design-factory/SKILL.md"):
            self.assertIn("CREATIVE_AGENT_PLAYBOOK.md",(ROOT/path).read_text(encoding="utf-8"))

if __name__=="__main__":
    unittest.main()
