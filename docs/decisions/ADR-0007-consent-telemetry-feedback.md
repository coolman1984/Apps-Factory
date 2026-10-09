# ADR-0007 • Consented telemetry, per-person usage, problem reports

- **Date:** 2026-10-09
- **Status:** ACCEPTED by owner (approval of the plan, 2026-10-09).

## Decisions
1. **Two consent levels:** installation and person. They are recorded append-only with the exact text ID. Decline and withdraw delete pending events (`packages/af-consent`).
2. **Usage is visible per person** through a pseudonymous reference: an HMAC with the installation secret, never a name.
3. **Firm limits are code.** Only allowlisted IDs, counts, durations and booleans are sent; the never-list is refused, and errors are sent without their message text (`packages/af-telemetry`, `PrivacyError`).
4. **Problem reports are allowed without tracking consent.** They are redacted, fully previewed, and sent exactly as previewed.
5. **Delivery path:** the offline outbox sends signed batches to a Cloudflare Worker relay, and the Control Center pulls from the relay. The relay and Control Center side are in PR 3.
6. **Alerts fan out** to every enabled channel in parallel: dashboard, e-mail, WhatsApp, Telegram and LinkedIn. There is no priority or fallback, and each channel's delivery is logged. The LinkedIn and Telegram adapters are disabled until configured. Cost and verification items stay open ([OPEN_POINTS.md](../OPEN_POINTS.md)).
7. **Rollout:** practice/demo data first, then installations (ROLL-01).
8. **Consent text:** the prompt names the vendor through one setting, `vendor_display_name`. It defaults to the product's `DEVELOPER`, with `coolman1984` as the fallback.
