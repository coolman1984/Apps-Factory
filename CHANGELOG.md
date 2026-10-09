# Changelog

Factory versions (the `README.md` version line). The control catalogue has its own `catalog_version` in `factory/controls.json`.

## 0.8.0 (2026-10-09)
- **Control Center 0.2.0: telemetry ingest and alerts:**
  - signed gzip batches through `POST /api/agent/events` or pulled from the relay, checked for HMAC, a 5-minute window, nonce replay and the firm limits (checked again on arrival);
  - incidents, per-person usage, guide funnel, releases, and problem reports as tickets;
  - 11 alert rules with de-duplication;
  - **parallel fan-out to every enabled channel** with a per-channel delivery log;
  - channel adapters: dashboard, email, WhatsApp, Telegram (free, off by default) and LinkedIn (off; cannot deliver, logs `unsupported`);
  - settings without secrets;
  - retention;
  - CLI commands `pull-relay`, `alerts` and `retention`, plus a background loop;
  - dashboard sections for alerts (with per-channel status), channels, incidents, releases, usage, guide funnel and reports.
- Fix: Control Center requests and the background loop now take turns on the shared sqlite connection. Before this, parallel dashboard requests could read each other's cursors (500 and false 401 errors); a regression test covers it.
- New template `templates/telemetry-relay`: a Cloudflare Worker + D1 relay (`/ingest`, `/pull`, `/ack`, a 14-day cron clean-up) with Node tests on a D1 shim.
- Design only: `docs/CUSTOMER_PATCH_PIPELINE.md`, covering the customer patch pipeline (all delivery free; the paid WhatsApp API is rejected for customers) and the optional customer Telegram bot.
- `docs/OPEN_POINTS.md`: new decided items for free customer delivery, the rejected customer WhatsApp API, and Telegram recommended for owner alerts.

## 0.7.0 (2026-10-09)
- New package `packages/af-consent` 0.1.0:
  - two-level, append-only consent records with exact text ids;
  - the prompt «أوافق حتى يستطيع [vendor] مساعدتي عن بُعد». The vendor name is one setting (`vendor_display_name`, default the product's `DEVELOPER`, fallback `coolman1984`);
  - a first-sign-in card and the Settings «الخصوصية والمساعدة» block.
- New package `packages/af-telemetry` 0.1.0:
  - event taxonomy `events.json` (31 types);
  - firm limits enforced in code: allowlisted IDs and counts only, a never-collect list, and `PrivacyError`;
  - pseudonymous per-person references, consent gating, and a purge when consent is declined or withdrawn;
  - error capture without message text;
  - error fingerprints written with letters only (hex digits 0-9 mapped to g-p), so a hash can never look like a long number and be refused by the long-digit privacy guard;
  - problem reports with redaction, a preview, a digest check, and no consent needed;
  - a bounded outbox with hourly merge;
  - signed gzip batches with backoff;
  - the browser `track()` call, an error hook, and the report dialog.
- `scripts/vendor_consent.py` and `scripts/vendor_telemetry.py`.
- Controls (catalogue 1.9.0, 138 controls):
  - new PRIV-01…06 (PRIV-05 is optional), TEL-01…03, FB-01 and ROLL-01;
  - SUP-04 now points to af-telemetry.
- Manifest: an optional `telemetry` block (`rollout`: off, practice or installations). `factory.py check` enforces ROLL-01.
- Docs: `docs/PRIVACY_TELEMETRY_STANDARD.md` and ADR-0007.

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
