# Capability map 🧰 — what the factory can do today, and where it lives

Status words follow the constitution: `planned` → `implemented` → `verified` → `field_accepted`.

| Capability | Where | Status | Use it for |
|---|---|---|---|
| Product specification gate | `scripts/factory.py new/check/doctor`, `factory/product.schema.json`, `controls.json` (138 controls) | implemented | Every new product starts with a manifest (`examples/al-store-product.json`) |
| **People, profiles and permissions** (BAMS model) | `docs/ACCESS_AND_ADMINISTRATION_STANDARD.md`, gate `packages/af-access` vendored by `scripts/vendor_access.py`; reference BAMS `server/auth.py` | implemented; gate in Al-Store, Hessa, Trip Orders tests | Every product with more than one person |
| Signed licences (JSON documents) | `packages/af-license` core | implemented | Paid editions, update manifests |
| **Licence codes** (144-char, device-bound, Ed25519) | `packages/af-license/af_license/codes.py` + stdlib verifier `ed25519_verify.py`, vendored by `scripts/vendor_licence.py` | implemented, cross-tested with Al-Store | 14-day trials that cannot be passed to another PC |
| **Licence Studio** (برنامج الأكواد) | `apps/licence-studio` — encrypted key, issue/verify/list, agent requests, audit, WhatsApp hand-off | implemented | The owner makes codes; agents check and request |
| **MCP for agents** | `apps/licence-studio` (`python -m licence_studio mcp`); WinSight (`Performance` repo) has its own | implemented | Claude Code / Codex read, verify, request codes, run doctor |
| Vendor Control Center (برج المراقبة) | `apps/control-center` — registry, heartbeats, tickets, grants, allowlisted repairs, licence desk | implemented (15 tests) | Support after the sale |
| **Design system** (Showroom) | `packages/af-ui` — tokens, base components, fonts, icons, motion | implemented in 2 consumers | Every new UI |
| **UI Lab** (performance + a11y) | `tools/ui-lab` — Playwright + axe-core, CPU ×4, budgets | implemented | Release gate PERF-01 / A11Y-01 |
| Measured layout sweep | Pattern in `Store/tests/test_e2e_browser.py`, `Teachers/tests/test_layout_overflow.py` | verified in 2 products | UX-08 |
| Office mesh sync | Hessa `server/sync.py` | implemented in Hessa | Products whose PCs must keep working alone |
| The Watch / owner's eye | Hessa `journal`/watch, Al-Store `server/reports.py::watch` | implemented in 2 products | Money-leak detection |
| Help standard (Guide me / Solve a problem, «العربية الميسّرة») | `docs/HELP_AND_GUIDANCE_STANDARD.md`, `Store/web/i18n/help-*.js` | implemented | Every product |
| **Guided onboarding** (af-guide) | `packages/af-guide` (checker + style lint + per-person progress + coach/panel + `testing/walk_guides.py`), `scripts/vendor_guide.py`, `factory.py guide`; `docs/GUIDED_ONBOARDING_STANDARD.md` | implemented; unit + browser tests on the demo shop; no product yet | HELP-07…12 in every product |
| **Consent + telemetry + problem reports** | `packages/af-consent`, `packages/af-telemetry` (taxonomy, firm limits in code, outbox, signed batches), `scripts/vendor_consent.py`, `scripts/vendor_telemetry.py`; `docs/PRIVACY_TELEMETRY_STANDARD.md` | implemented; unit-tested; no product yet | PRIV-01…06, TEL-01…03, FB-01, ROLL-01 |
| Compiled Windows build + installer | `templates/windows-installer` (from Al-Store: Nuitka + Inno Setup + smoke test + workflow); Hessa, BAMS, Atrium have their own | **verified** on a real Windows runner (Al-Store, Actions run 3); clean-PC install by a person still pending | Every Windows product |
| Junk-input robustness test | Al-Store `tests/test_fuzz.py` (control QA-02) | verified in Al-Store; found 20+ crashes and 6 real bugs | Every product with write routes |
| Product → Control Center heartbeat | Al-Store `server/support.py` (opt-in, exact fields, secrets outside the DB); contract-tested against the Control Center model | implemented, contract-tested | SUP-01/04 in every product |
| Barcode on receipts + sticker labels | Al-Store `web/js/barcode.js` (Code 128 SVG, decoded by a scanner library in the check) | verified in Al-Store | Any shop product |
| Chrome DevTools automation | `opening-nerp-tcode` (G-MES), Store UI Lab uses CDP for throttling | verified in production automation | Testing, RPA, measurement |
| Windows desktop automation via accessibility | `win-agent-desktop` | implemented | Agents testing desktop apps |
| Promo films from real screens | `Animation` studio + `promo-video-generator` | implemented | Marketing each product (capture with UI Lab screenshots or `lib/app-capture.mjs`) |
| WebGPU visual effects | `shaders` fork | external | Marketing pages only |

## Gaps (honest)
Signed update channel used by a product; a shared (not copied) heartbeat client library; support grant/repair UI in products;
ETA e-receipt integration (Egypt); a shared sync package extracted from Hessa; field-verified anything.
