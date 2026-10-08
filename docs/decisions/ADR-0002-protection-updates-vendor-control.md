# ADR-0002 • Copy protection, signed updates, Vendor Control Center, AI-assisted support

- **Date:** 2026-10-08
- **Status:** ACCEPTED by owner as factory direction (session request, 2026-10-08). Tool picks marked *spike* stay pending evidence.
- **Constraint from the owner:** simple, free and proven first; paid tools only when revenue allows.

## Decisions
1. **Copy protection = 6 cheap layers, no "uncrackable" promise:** signed licence (`packages/af-license`, Ed25519, offline private key), activation/device binding, compiled builds (Nuitka core), tamper evidence + clock-rollback guard, Authenticode signing, traceable customer name and update/support/cloud value only for valid licences. Licence failure never harms customer data.
2. **Updates:** CI-built, Authenticode-signed binaries + update manifest signed with a **separate** `update` key; data and settings outside the program folder; verified backup before migration; automatic rollback; canary rollout. Updater engine *spike*: tufup vs Velopack.
3. **Vendor Control Center** is a factory product of its own (`examples/vendor-control-center.json`): customer/install registry, licence desk, health board, crash inbox (GlitchTip), support tickets, consented remote sessions (RustDesk self-hosted, attended), release desk.
4. **AI agent via MCP** connects to the Control Center only; read by default; writes to our repo through PRs; repair actions on a customer install only from a tested allowlist under a live customer grant, vendor approval and audit; logs/tickets treated as untrusted input.
5. **Paid minimum accepted:** code-signing certificate, one small server, a domain.

## Rejected for now
Hand-written crypto; PyArmor free tier for commercial builds; permanent unattended remote passwords by default; agent shell access on customer machines; hidden kill switches; Tactical RMM (sponsorship needed for signed agents); paid licence SaaS.

## Spec
[PROTECTION_UPDATES_AND_SUPPORT.md](../PROTECTION_UPDATES_AND_SUPPORT.md)
