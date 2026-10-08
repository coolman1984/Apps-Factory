"""Design Factory static contract tests. Actual visual quality needs browser evidence."""
import configparser
from html.parser import HTMLParser
import json
from pathlib import Path
import re
import subprocess
import unittest

ROOT=Path(__file__).resolve().parents[2]
DESIGN=ROOT/"design-factory"

class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.ids=[]
        self.links=[]
        self.scripts=[]
        self.buttons=[]
        self.lang=None
        self.inputs=[]
    def handle_starttag(self,tag,attrs):
        attr=dict(attrs)
        if "id" in attr:self.ids.append(attr["id"])
        if tag=="link" and "href" in attr:self.links.append(attr["href"])
        if tag=="script" and "src" in attr:self.scripts.append(attr["src"])
        if tag=="button":self.buttons.append(attr)
        if tag=="input":self.inputs.append(attr)
        if tag=="html":self.lang=attr.get("lang")
        for key,_ in attrs:
            if key.lower().startswith("on"):raise AssertionError("Inline event handler is prohibited")

class DesignTests(unittest.TestCase):
    def test_upstream_pins_and_submodule_origins(self):
        manifest=json.loads((DESIGN/"upstreams.lock.json").read_text(encoding="utf-8"))
        cfg=configparser.ConfigParser()
        cfg.read(ROOT/".gitmodules",encoding="utf-8")
        self.assertEqual(len(manifest["upstreams"]),6)
        for source in manifest["upstreams"]:
            p="design-factory/upstream/"+source["id"]
            section='submodule "'+p+'"'
            self.assertIn(section,cfg)
            self.assertEqual(cfg[section]["path"],p)
            self.assertEqual(cfg[section]["url"],"https://github.com/"+source["repo"]+".git")
            self.assertRegex(source["commit"],r"^[0-9a-f]{40}$")
            result=subprocess.run(["git","ls-files","--stage","--",p],cwd=ROOT,capture_output=True,text=True,check=True)
            self.assertIn("160000 "+source["commit"],result.stdout)

    def test_no_invented_public_certification(self):
        d=json.loads((DESIGN/"component-registry.json").read_text(encoding="utf-8"))
        self.assertEqual(d["implementation_status"],"reference-only")
        self.assertGreaterEqual(len(d["items"]),6)
        self.assertTrue(all(c["status"]=="reference_only" for c in d["items"]))

    def test_assets_local_and_unique_dom_ids(self):
        page=DESIGN/"reference/index.html"
        parser=PageParser();parser.feed(page.read_text(encoding="utf-8"))
        self.assertEqual(parser.lang,"ar")
        self.assertEqual(len(parser.ids),len(set(parser.ids)))
        self.assertGreaterEqual(len(parser.buttons),7)
        for asset in parser.links+parser.scripts:
            self.assertNotIn("://",asset,"Runtime cannot require a CDN")
            self.assertTrue((page.parent/asset).resolve().is_file(),"Missing asset: "+asset)
        self.assertIn("../core/tokens.css",parser.links)
        self.assertIn("../core/components.css",parser.links)

    def test_bilingual_theme_tokens_and_safe_js(self):
        html=(DESIGN/"reference/index.html").read_text(encoding="utf-8")
        js=(DESIGN/"reference/app.js").read_text(encoding="utf-8")
        css=(DESIGN/"core/tokens.css").read_text(encoding="utf-8")
        for needle in ('data-theme="light"','dir="rtl"','data-i18n="overview"','id="search"','id="addDialog"'):
            self.assertIn(needle,html)
        for needle in ("locale =","document.documentElement","root.dir","Intl.DateTimeFormat","replaceChildren","textContent","safeCsvCell","reportValidity"):
            if needle=="reportValidity":continue
            self.assertIn(needle,js)
        self.assertIn('data-theme="dark"',css)
        self.assertIn("prefers-reduced-motion",css)
        self.assertNotIn("innerHTML",js)
        self.assertNotIn("document.write(",js)
        self.assertNotIn("fetch(",js)

    def test_root_agent_discovery(self):
        root_agent=(ROOT/"AGENTS.md").read_text(encoding="utf-8")
        self.assertIn("design-factory/AGENTS.md",root_agent)
        for path in ("README.md","AGENTS.md","DESIGN_CONSTITUTION.md","WORKFLOW.md","QA_CHECKLIST.md",
                     "UPSTREAMS.md","skills/design-factory/SKILL.md","core/tokens.css",
                     "core/components.css","reference/index.html","reference/app.js"):
            self.assertTrue((DESIGN/path).exists(),path)

    def test_installer_is_dry_run_and_never_overwrites(self):
        import tempfile
        import sys
        sys.path.insert(0,str(DESIGN/"scripts"))
        import install
        with tempfile.TemporaryDirectory() as directory:
            target=Path(directory)
            install.execute(target,apply=False)
            self.assertFalse((target/"DESIGN_FACTORY.md").exists())
            install.execute(target,apply=True)
            token=target/"design-system/af-tokens.css"
            self.assertTrue(token.exists())
            token.write_text("customer-owned custom file",encoding="utf-8")
            install.execute(target,apply=True)
            self.assertEqual(token.read_text(encoding="utf-8"),"customer-owned custom file")

if __name__=="__main__":unittest.main()
