# Changelog

Factory versions (the `README.md` version line). The control catalogue has its own `catalog_version` in `factory/controls.json`.

## 0.6.0 (2026-10-09)
- **New package `packages/af-guide` 0.1.0.** It contains:
  - a guide catalogue checker and the «العربية الميسّرة» style lint;
  - per-person server progress (`guide_progress` table, `/api/guide/state` and `/api/guide/progress` helpers);
  - the browser runtime (the «الدليل» button and panel, an auto-advancing coach with resume, a per-page "?", error → problem links, and a per-guide language switch);
  - a Playwright guide walker, a demo shop served under a strict CSP, and unit, node and browser tests.
- **New `scripts/vendor_guide.py`** and the `python scripts/factory.py guide <folder>` subcommand.
- **Controls (catalogue 1.8.0, 127 controls):**
  - HELP-04 changes from "polished Egyptian" to «العربية الميسّرة».
  - New HELP-07 role courses + server progress, HELP-08 auto-advance + resume, HELP-09 error → problem links, HELP-10 guide language switch, HELP-11 style lint, HELP-12 browser walk.
- **Docs:**
  - new `docs/GUIDED_ONBOARDING_STANDARD.md` and ADR-0006;
  - `HELP_AND_GUIDANCE_STANDARD.md` language section rewritten;
  - AGENTS.md and the capability map updated.
- **CI:** af-guide unit and node tests in `validate`, plus a new `guide-browser` job.

## 0.5.0
Licence codes + Licence Studio (MCP), the Showroom design system (`af-ui`), the UI Lab and the factory knowledge base.
