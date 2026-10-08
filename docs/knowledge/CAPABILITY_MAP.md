# Capability map 🧰 — what the factory can do today, and where it lives

Status words follow the constitution: `planned` → `implemented` → `verified` → `field_accepted`.

| Capability | Where | Status | Use it for |
|---|---|---|---|
| Product specification gate | `scripts/factory.py new/check/doctor`, `factory/product.schema.json`, `controls.json` (114 controls) | implemented | Every new product starts with a manifest (`examples/al-store-product.json`) |
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
| Help standard (Guide me / Solve a problem, Egyptian Arabic) | `docs/HELP_AND_GUIDANCE_STANDARD.md`, `Store/web/i18n/help-*.js` | implemented | Every product |
| Compiled Windows build + installer | Hessa `tools/build_windows.py` (Nuitka) + Inno Setup, BAMS installer, Atrium installer | implemented per product, not shared yet | Next shared piece |
| Chrome DevTools automation | `opening-nerp-tcode` (G-MES), Store UI Lab uses CDP for throttling | verified in production automation | Testing, RPA, measurement |
| Windows desktop automation via accessibility | `win-agent-desktop` | implemented | Agents testing desktop apps |
| Promo films from real screens | `Animation` studio + `promo-video-generator` | implemented | Marketing each product (capture with UI Lab screenshots or `lib/app-capture.mjs`) |
| WebGPU visual effects | `shaders` fork | external | Marketing pages only |

## Gaps (honest)
Shared Windows installer + embedded Python; signed update channel used by a product; product ↔ Control Center heartbeat library;
ETA e-receipt integration (Egypt); a shared sync package extracted from Hessa; field-verified anything.
