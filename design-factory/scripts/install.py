#!/usr/bin/env python3
"""Safely attach Apps Factory design rules and baseline CSS to an existing project."""
from __future__ import annotations
import argparse
import shutil
import sys
from pathlib import Path

FACTORY=Path(__file__).resolve().parents[1]
ASSETS={
  "design-system/af-tokens.css": FACTORY/"core/tokens.css",
  "design-system/af-components.css": FACTORY/"core/components.css",
}
CREATIVE_ASSETS={
  "creative/creative-effects.css": FACTORY/"core/creative-effects.css",
  "creative/creative-primitives.js": FACTORY/"core/creative-primitives.js",
}
DOC="""# Apps Factory Design System integration

This is a local snapshot of Apps Factory's **design reference only**, not a production account, API, license or authorization component.
Upstream: https://github.com/coolman1984/Apps-Factory/tree/main/design-factory
Source version: Design Factory UI v2.0.0

## Agent rules
1. Before any UI/UX update, read the original Apps Factory `design-factory/AGENTS.md`, `DESIGN_CONSTITUTION.md`, `WORKFLOW.md` and `QA_CHECKLIST.md` (copy them if working offline).
2. Inspect existing application, existing `DESIGN.md`, workflows, deployed framework and reference screenshots.
3. Reuse `design-system/af-tokens.css` and `design-system/af-components.css` **only where compatible**.
4. Choose exactly one UI kit: vanilla baseline, Tabler, Web Awesome, or shadcn (existing React app). Never mix competing CSS frameworks.
5. Test actual browser UI with screenshot evidence in RTL/LTR, light/dark, desktop/mobile, zoom, keyboard, failures.
6. This script never overwrites existing project files. Merge changes via reviewed PR. Keep product security/data/release rules unchanged.

## HTML integration
```html
<link rel="stylesheet" href="/design-system/af-tokens.css">
<link rel="stylesheet" href="/design-system/af-components.css">
```
Adjust URL roots to actual framework/static folder; copy assets into the framework's served assets path.

## Production note
No third-party vendor assets are bundled by this bridge. Audit libraries/fonts/icons separately.
"""
DOCS={
 "DESIGN_FACTORY.md":DOC,
 "design-system/AGENT_DESIGN_CONSTITUTION.md":(FACTORY/"DESIGN_CONSTITUTION.md").read_text(encoding="utf-8"),
 "design-system/AGENT_DESIGN_WORKFLOW.md":(FACTORY/"WORKFLOW.md").read_text(encoding="utf-8"),
 "design-system/AGENT_DESIGN_QA.md":(FACTORY/"QA_CHECKLIST.md").read_text(encoding="utf-8"),
}

def plan(target:Path,creative=False):
    if not target.exists() or not target.is_dir():
        raise ValueError("Existing target project directory required")
    if target.resolve()==FACTORY.resolve() or target.resolve()==FACTORY.parent.resolve():
        raise ValueError("Select another project, not Apps Factory itself")
    operations=[]
    for relative,source in {**ASSETS,**(CREATIVE_ASSETS if creative else {})}.items():
        if not source.is_file():raise ValueError("Missing source asset "+str(source))
        operations.append((relative,source,None))
    for relative,content in DOCS.items():operations.append((relative,None,content))
    return [(relative,source,content,"SKIP_EXISTS" if (target/relative).exists() else "CREATE") for relative,source,content in operations]

def execute(target,apply=False,creative=False):
    operations=plan(target,creative=creative)
    for relative,source,content,status in operations:
        print(status,relative)
        if apply and status=="CREATE":
            dest=target/relative
            dest.parent.mkdir(parents=True,exist_ok=True)
            if source:
                with dest.open("x",encoding="utf-8") as f:
                    f.write(source.read_text(encoding="utf-8"))
            else:
                with dest.open("x",encoding="utf-8") as f:f.write(content)
    print("Applied without overwriting existing files." if apply else "Dry run only. Pass --apply after review.")
    return operations

def main():
    parser=argparse.ArgumentParser(description="Copy reusable design starter into another app. Default: preview only.")
    parser.add_argument("--target",required=True,type=Path,help="Path to an existing local project")
    parser.add_argument("--apply",action="store_true",help="Write missing files, never overwrite")
    parser.add_argument("--creative",action="store_true",help="Also install original lightweight motion/layer assets (opt-in)")
    args=parser.parse_args()
    try:execute(args.target,args.apply,args.creative);return 0
    except (ValueError,OSError) as error:print("ERROR:",error,file=sys.stderr);return 2

if __name__=="__main__":sys.exit(main())
