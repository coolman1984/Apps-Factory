---
name: licence-codes
description: Add trial/paid licence codes to a product, or check/request codes through the Licence Studio (UI or MCP). Use for anything about activation, trial periods or device codes.
---
# Licence codes
- Product side: run `python scripts/vendor_licence.py <product-dir>` to copy the stdlib verifier into `server/afcodes.py` + `server/ed25519.py`; follow Al-Store `server/licence.py` (trusted keys file, device code, cached status, clock-back guard, locked = read/export/backup only).
- Public key only in `licence_keys.txt`. Private key never leaves the Studio (encrypted, auto-locks). Never put a key in a repo, CI or logs.
- Studio: `cd apps/licence-studio && python -m licence_studio serve` (owner) or `… mcp` (agent; env `LS_URL`, `LS_AGENT_TOKEN`).
- Agents: use `verify_code`, `list_codes`, `request_code`. `issue_trial_code` works only if the owner enabled it (≤ 14 days, daily cap). Paid codes: owner only.
- Tests to keep green: `packages/af-license` (incl. vendored copy not stale) and `apps/licence-studio/tests` (full chain with a product).
