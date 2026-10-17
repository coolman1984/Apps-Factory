# Handoff: feat/af-auth-port-yousef-115

## Scope delivered
- New shared part **af-auth 0.1.0** (`packages/af-auth/af_auth.py`, optional `af-auth.js`, `scripts/vendor_auth.py`).
- Ported Trip Orders v1.1.5 rules: pending sign-up, approve/refuse/suspend, reset codes with replicated burn, login lockout, sole-manager exemption, last-manager guard, suspended username re-registration block.
- Spec: `docs/AUTH_ACCOUNT_LIFECYCLE_STANDARD.md`; `PARTS.md` and `CHANGELOG.md` updated.

## Upstream / mandatory learning (NOT VERIFIED offline)
- **Agent Use Cases** (https://agentusecases.ai/): live category search not run in this environment — **NOT VERIFIED (offline)**. Applied local pattern from Trip Orders regression tests instead.
- **ManimGX**: **N/A** (no motion/video).
- **Upstream capability catalogue** (`docs/knowledge/SCREENSHOT_AGENT_TOOLS_CANDIDATES_2026-10-11.md`): no separate auth SaaS adopted; factory-native `af-auth` + existing `af-access` retained. OWASP ASVS auth guidance already cited in `docs/ACCESS_AND_ADMINISTRATION_STANDARD.md` — not re-fetched.

## Source reference
- Upstream product auth: `/workspace/y114/server/auth.py`, `tests/test_yt_115.py` (auth-related cases), `js/views/auth.js` (UI patterns → generic `af-auth.js`).
- Checked in repo: 2026-10-17; not a live pull from product `main`.

## Tests run
- `python3 -m unittest discover -s packages/af-auth/tests -v` (60 tests)
- `node --test packages/af-auth/tests/core.test.mjs`
- Factory suite per PLAYBOOK section 1 (record counts in PR)

## Not in this PR
- Vendoring into Store / Trip Orders product repos (separate product PRs).
- Full journal/replica integration (products keep `UserFolder`; af-auth supplies rules + test store).
