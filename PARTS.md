# Parts

Every shared part of the factory: what it is, its version (read from code), how a product takes it, where the detailed spec is, and who uses it.
**Vendoring** means copying the part into the product with `python3 scripts/vendor_<name>.py <product dir>`. The copy carries a two-line "Vendored from … do not edit here" header and is otherwise byte-identical. Each package's tests (and `.github/workflows/vendored-drift.yml`, daily) fail when a product holds a stale copy. Never edit a vendored copy; change the factory part, bump its version, vendor again.

Product use below was read from the product clones on 2026-10-09 (Store, Teachers, Yousef-Transportation, Mr.Ayman-HR). Store is Al-Store (الستور), Teachers is Hessa (حصّة), Yousef-Transportation is Trip Orders, Mr.Ayman-HR is BAMS.

## Packages (`packages/`)

### af-access — people, profiles, pages and permissions gate
- **Version:** 0.1.1 (`packages/af-access/af_access.py`). One file, standard library only.
- **Vendor:** `python3 scripts/vendor_access.py <product>` → `server/afaccess.py`. Run `afaccess.errors(auth.catalogue())` in the product's tests.
- **Spec:** `docs/ACCESS_AND_ADMINISTRATION_STANDARD.md`; package `packages/af-access/README.md`. Controls IAM-08, IAM-10, IAM-11.
- **Used by:** Store, Teachers, Yousef-Transportation (vendored). Mr.Ayman-HR has its own access code and has not vendored it.

### af-license — signed licences, licence codes, update manifests
- **Version:** 0.3.0 (`packages/af-license/af_license/__init__.py`; the package README header is historical). Supports 14-day trials, 30-day monthly codes and perpetual device-bound licences; legacy codes still verify. Ed25519 through the `cryptography` library; `requirements.txt` is for the factory side only.
- **Vendor:** `python3 scripts/vendor_licence.py <product>` → `server/afcodes.py` and `server/ed25519.py` (stdlib verifier, public key only).
- **Spec:** `docs/PROTECTION_UPDATES_AND_SUPPORT.md`; package `packages/af-license/README.md`. Controls LIC-01, BIZ-03.
- **Used by:** Store (vendored codes). Teachers, Yousef-Transportation and Mr.Ayman-HR carry their own Ed25519 code and are not on the vendored copy.

### af-guide — guided onboarding (role courses, coach, "?", problem links, style lint)
- **Version:** 0.1.1 (`packages/af-guide/af_guide.py`). Checker, Arabic style lint (`style/ar-lexicon.json`), browser walker (`testing/walk_guides.py`), JS engine and CSS.
- **Vendor:** `python3 scripts/vendor_guide.py <product>` → `server/afguide.py`, `server/afguide_ar_lexicon.json`, `<js>/vendor/af-guide.js`, `<css>/af-guide.css`. Check a product's guide with `python3 scripts/factory.py guide <product>/guide --release`.
- **Spec:** `docs/GUIDED_ONBOARDING_STANDARD.md` and `docs/HELP_AND_GUIDANCE_STANDARD.md` (Arabic register, learning path); package `packages/af-guide/README.md`. Controls HELP-07, HELP-09, HELP-11.
- **Used by:** no product has vendored it yet (demo shop in `packages/af-guide/examples/shop`).

### af-consent — two-level consent records
- **Version:** 0.1.0 (`packages/af-consent/af_consent.py`).
- **Vendor:** `python3 scripts/vendor_consent.py <product>` → `server/afconsent.py`, `<js>/vendor/af-consent.js`, `<css>/af-consent.css`.
- **Spec:** `docs/PRIVACY_TELEMETRY_STANDARD.md`; package `packages/af-consent/README.md`. Control PRIV-01.
- **Used by:** no product has vendored it yet.

### af-telemetry — ids-and-counts telemetry, offline outbox, problem reports
- **Version:** 0.2.0 (`packages/af-telemetry/af_telemetry.py`), protocol 2, taxonomy `events.json`.
- **Vendor:** `python3 scripts/vendor_telemetry.py <product>` → `server/aftelemetry.py`, `server/aftelemetry_events.json` (copied byte for byte), `<js>/vendor/af-telemetry.js`, `<css>/af-telemetry.css`. New event types go into the factory taxonomy, never into a product's copy.
- **Spec:** `docs/PRIVACY_TELEMETRY_STANDARD.md`; package `packages/af-telemetry/README.md`. Controls PRIV-03, TEL-01, FB-01.
- **Used by:** no product has vendored it yet. The rollout waits for the owner (see `DECISIONS.md`).

### af-ui — the "Showroom" design system
- **Version:** 0.1 (`packages/af-ui/README.md`; no version constant in code).
- **Take it:** copy `packages/af-ui/{css,fonts,img,js}` or serve it (Licence Studio serves it at `/af-ui/`). Re-brand `css/tokens.css` only. No vendor script.
- **Spec:** `docs/DESIGN_SYSTEM.md`; package `packages/af-ui/README.md`. Control UX-09.
- **Used by:** Licence Studio. Store has its own token file now ("Ledger" identity).

## Apps (`apps/`)

### apps/control-center — Vendor Control Center (برج المراقبة)
- **Version:** 0.3.0 (`control_center/app.py` `VERSION` and the README title; `control_center/__init__.py` still says 0.1.0).
- **What:** customer and install registry, heartbeats, tickets, consented support grants, allowlisted repairs, licence desk, telemetry ingest, incidents, per-person usage, alerts to every enabled channel (dashboard, e-mail, Telegram, …). Not deployed yet.
- **Run:** `pip install -r requirements.txt`, then `python3 -m control_center serve` (tokens, relay pull and keys in its README).
- **Spec:** `docs/PROTECTION_UPDATES_AND_SUPPORT.md`, `docs/PRIVACY_TELEMETRY_STANDARD.md`; `apps/control-center/README.md`; manifest `examples/vendor-control-center.json`.
- **Used by:** the owner. Store sends its heartbeat to it (contract-tested in `tests/test_product_heartbeat.py`).

### apps/licence-studio — the owner's licence-code program (UI + MCP)
- **Version:** 1.1.0 (`licence_studio/__init__.py`). Three sales types: trial, monthly and lifetime; paid issuance requires the owner.
- **Run:** `pip install -r requirements.txt`, then `python3 -m licence_studio serve` (loopback only). MCP: `python3 -m licence_studio mcp`. Skill: `.claude/skills/licence-codes`.
- **Spec:** `apps/licence-studio/README.md`; codes format in `packages/af-license`.
- **Used by:** the owner issues the codes that Store verifies.

## Templates (`templates/`)
Templates are copied and edited by hand; they are not byte-identical vendored code.

- **templates/telemetry-relay** — Cloudflare Worker + D1 mailbox between products and the Control Center (`/ingest`, `/pull`, `/ack`). Not deployed. Spec: its `README.md`, `docs/PRIVACY_TELEMETRY_STANDARD.md`. Used by: the Control Center pulls from it.
- **templates/windows-installer** — Nuitka build, Inno Setup installer, smoke test and Windows workflow, verified in Store. Copy the files and change the marked names (its `README.md`; lessons in `docs/knowledge/LESSONS.md`; ADR-0004 for unsigned builds). Used by: Store; Teachers, Yousef-Transportation and Mr.Ayman-HR have their own installers.
- **templates/patch-pipeline** — ready but inactive workflows for the customer patch agent and Telegram approval notices. Spec: `docs/CUSTOMER_PATCH_PIPELINE.md`. Used by: no product yet.
- **templates/\*.md** — `PRODUCT_BRIEF.md`, `MARKET_RESEARCH.md`, `RELEASE_EVIDENCE.md`, `CUSTOMER_INSTALL_GUIDE_AR.md`. Used when starting or releasing a product (skill `new-product`).

## Tools (`tools/`)

### tools/ui-lab — performance and accessibility gate
- **Version:** 1.0.0 (`tools/ui-lab/package.json`). Playwright + axe-core, CPU throttled ×4, budgets in `factory/ui-budgets.json`.
- **Use:** `cd tools/ui-lab && npm install && node probe.mjs --config <product>/ui-lab.config.json --out <product>/docs/ui-lab`. Exit 1 means over budget. Commit the report with each release candidate. No vendoring; the product keeps a config file.
- **Spec:** `docs/PERFORMANCE_STANDARD.md`, `docs/QUALITY_SYSTEM.md`; `tools/ui-lab/README.md`. Controls PERF-01, A11Y-01. Skill: `.claude/skills/ui-quality-pass`.
- **Used by:** Store (`ui-lab.config.json`).

## Design Factory (`design-factory/`)
Offline visual-system starter (tokens, reference app, icon and creative labs, pinned upstream sources). Version 2.0.0 (`design-factory/package.json`). UI work starts at `design-factory/AGENTS.md`; its own tests run in `design-factory.yml`.

## Not parts, but read when you need them
`factory/` (control catalogue, product schema, UI budgets, event contracts), `scripts/factory.py` (the CLI), `examples/` (sample manifests), `docs/knowledge/` (capability map and matrix, repo map, lessons), `docs/*.md` (reference specs linked above).
