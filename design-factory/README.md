# Design Factory | مصنع التصميم

**A working, offline-first visual-system starter plus audited upstream references.** This does **not** certify pixel-perfect quality without screenshot inspection. App business logic, security, login, licensing and backups remain owned by the existing Apps Factory contracts.

## Start here
1. Agent: read [design-factory/AGENTS.md](AGENTS.md), [DESIGN_CONSTITUTION.md](DESIGN_CONSTITUTION.md), [WORKFLOW.md](WORKFLOW.md), [QA_CHECKLIST.md](QA_CHECKLIST.md); review the app's user journey, current screens and permitted tech before changing code.
2. Open [reference/index.html](reference/index.html) locally. No network, Node, Python or CDN required. Synthetic screen only.
3. Edit [core/tokens.css](core/tokens.css) for brand and density; use [core/components.css](core/components.css) for shared patterns. No product secrets or customer data.
4. Pick **one** UI runtime approach: vanilla HTML + these CSS tokens/components for small apps; Tabler **or** Web Awesome for larger vanilla apps; shadcn/ui for existing React projects. Do **not** mix all kits.
5. Capture visual comparison of *actual running pages* at desktop/tablet/mobile, light/dark, Arabic RTL/English LTR and 200% zoom. Run interactive checks and [tests](tests/).
6. Bring visual improvements back into this factory only when 2 apps prove the shared tokens/components without regressions. Preserve specialized industrial or 3D canvas layouts.

## Source repositories brought under version control
Six original repositories are **pinned Git submodules**, not GitHub forks. Their code remains attributed to their owners and physically fetched only via:
```bash
git clone https://github.com/coolman1984/Apps-Factory.git
cd Apps-Factory
git submodule update --init design-factory/upstream/ui-ux-pro-max
git submodule update --init design-factory/upstream/tabler
# Optional: only the sources you need
git submodule update --init design-factory/upstream/anthropic-skills design-factory/upstream/vercel-agent-skills
git submodule update --init design-factory/upstream/shadcn-ui design-factory/upstream/webawesome
```
Offline Windows customers **must not** need these submodules or internet: bundle only built, approved local assets needed by their product. No CDN requirement. See [UPSTREAMS.md](UPSTREAMS.md) for exact source/commit/licence caveats and updates.

## Deliverables
- A usable, locally runnable bilingual design reference with functional theme, language, mobile navigation, table search/filter and menu.
- Versioned CSS tokens and lightweight reusable patterns (no framework lock-in).
- Source-of-truth design constitution, process, reusable agent skill and visual QA checklist.
- Static automated contract checks; screenshot/E2E testing remains a required product gate, NOT asserted by passing static checks.

## What this does not do
- It cannot reliably judge beauty or exact image fidelity from source code alone.
- Submodules are not forks under `coolman1984`, nor does GitHub automatically copy their content into this repository.
- Do not assume upstream licence applies to all bundled assets, brands, pro add-ons or third-party files.
- A visually good reference does not make customer login, invoice, subscription or security correct.
