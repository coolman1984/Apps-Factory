# Changelog

Factory versions (the `README.md` version line). The control catalogue has its own `catalog_version` in `factory/controls.json`.

## 0.9.0 (2026-10-09)
Telemetry hardening (roadmap step 1; the product rollout is paused until this lands). Each fix has a regression test.
- **Protocol 2 (simpler and safer):** batches go over HTTPS with the install token (`Authorization: Bearer`), and event ids de-duplicate.
  - Removed: HMAC signature, nonce and 5-minute window (`af_telemetry.sign`/`verify`, the relay's `RELAY_INGEST_KEY`). No product vendors af-telemetry yet, so no compatibility layer is needed.
  - af-telemetry 0.2.0, Control Center 0.3.0, relay schema `inbox` + `installs` (the 0.8 `batches` table is no longer used).
- **1. A bad event no longer sinks the batch:**
  - `events.json` can mark fields `required` (`code` and `fingerprint` for `err.*`); they are checked on the PC and again on arrival.
  - The Control Center stores a batch in one transaction with one savepoint per event: a bad event, or a bug in a rule, is rolled back alone and counted with a reason. Database trouble keeps the whole batch.
  - The relay batch is deleted only after it was stored, parked or quarantined (`rejected_batches`); a temporary failure leaves it on the relay.
- **2. Clock skew:**
  - No time window any more. Every answer carries `server_time`; the PC keeps the offset and stamps later events with corrected time, and the Control Center corrects a batch that is more than 2 minutes off (`installs.clock_skew_s`).
  - No endless retries: 400/413/422 dead-letter the batch at once, and events refused 12 times go to a bounded `dead` table (`dead_letters()`). Being offline only waits.
- **3. Relay within Cloudflare D1 Free limits:**
  - `/ack` deletes with one `DELETE … WHERE id IN (…)` per 100 ids (at most 5 statements);
  - `/installs` upserts 25 rows per statement (at most 42 queries);
  - `/ingest` uses at most 3 queries.
- **4. No whole-table count:** the global `COUNT(*)` against `MAX_ROWS` is gone. Ingest reads only the sender's own rows (index `install_id, received_at`) or the small pending area.
- **5. Strangers cannot fill the relay:**
  - The Control Center pushes the install list (id + sha256 of the token, never the token) to the relay when it changes. A wrong token is refused after one lookup.
  - Per-install caps: `RATE_PER_HOUR` 120, `MAX_ROWS_PER_INSTALL` 2000, `MAX_BYTES_PER_INSTALL` 20 MB.
  - Unknown installs: a capped pending area (200 rows; 5 per install; 10 per address per day, the address kept only as a salted hash; 64 KB per batch).
- **6. New PCs are not lost:**
  - Unknown installs are parked as «أجهزة جديدة مستنية موافقتك» (first token pinned; 50 PCs, 20 batches each, 30 days).
  - The dashboard and `/api/installs/pending` approve (choose the customer and tier; the PC keeps its id and token, and its batches are replayed) or discard. `af_telemetry.new_identity()` gives an unregistered PC its own id and token.
- **7. Alerts never freeze the dashboard:**
  - Alerts raised during ingest are queued in the same transaction, and a background `Deliverer` sends them outside the database lock with per-channel timeouts.
  - `/api/agent/events` stores on a worker thread instead of the event loop.
  - The background loop and `pull-relay` call the relay outside the lock.
- **8. Alert repeats:**
  - `incident_spike` counts the last hour only, so it no longer repeats every 6 hours forever.
  - `silent_install` and `backup_stale` count working hours in Africa/Cairo (Friday off; Saturday too with the new `saturday_off` setting) and alert once per silence.
  - A new `regression` rule fires when a known fingerprint appears in a new version (12 rules).
- **9. Problem-report text stays on the dashboard:** Telegram, e-mail and the other channels get the ticket number, category, page and a dashboard link (`CC_DASHBOARD_URL`).
- **af-guide 0.1.1:**
  - `scripts/vendor_guide.py` now also copies the style lexicon (`server/afguide_ar_lexicon.json`), which the vendored `afguide.lint`/`errors` need.
  - `testing/walk_guides.py` works under a strict CSP like Store's: no `wait_for_function` (its polling uses eval) and no JavaScript built from strings.
  - The demo now serves Store's exact policy.
- Controls catalogue 1.9.1: TEL-02 wording follows protocol 2.
- CI: #21 already runs af-guide, af-consent, af-telemetry, the Control Center and the relay (Node 22) in `validate`, so no extra workflow was needed.

## 0.8.1 (2026-10-09)
- Removed the pdpc.gov.eg link from the controls catalogue and `docs/MARKET_AND_STANDARDS.md`.
- **Telegram is a core owner channel** (owner decision 09:26):
  - Control Center `TelegramChannel` is on as soon as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` are set (the `CC_TG_*` names still work);
  - it has no switch, and settings refuse to turn it off; tests cover this.
- The WhatsApp owner-alert open point is superseded by Telegram.
- Design (`docs/CUSTOMER_PATCH_PIPELINE.md` §7): Telegram patch-approval notices, and owner `/status` and `/incidents` through the relay webhook, restricted to the owner's chat id.

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
