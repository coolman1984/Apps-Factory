# Changelog

Factory versions (the `README.md` version line). The control catalogue has its own `catalog_version` in `factory/controls.json`.

## 0.14.0 (2026-10-10)
The owner's buttons on Telegram, end to end. Relay template and Licence Studio change; `af-license` and the catalogue do not.
- **Relay (`templates/telemetry-relay`):** every alert has «✅ موافق» / «❌ رفض» (only when the webhook can really answer them); new `POST /telegram` webhook trusted only with the secret token **and** a press from the owner's private chat. «رفض» closes the request at once (final; «سحب الموافقة» after an approval until the code is signed); «موافق» only records the approval in a new table `licence_owner` (re-running `schema.sql` is the whole upgrade) and, for a trial, makes the shop's status `stage: approved` while it counts. The relay judges how long an approval counts (`LICENCE_APPROVAL_HOURS`, 72, at least 1) and answers `expired`. A wrong secret costs no database query; other refused presses are logged, capped at 50 an hour. `POST /licence/states` for the Studio. `test/telegram.test.mjs`: 19 tests.
- **Licence Studio 1.2.0:** follows the owner's buttons: «موافق» signs that one trial on the next round even with the policy off (every hard rule still holds; the owner's own cap and flood check do not hold it back); «رفض» is closed here too; the owner's click, and the unattended signing, re-check with the relay right before signing; paid kinds still need the payment tick and reference. **A copy of every signed code goes to the owner's own Telegram chat** (private chat only, claimed atomically with a timeout, once, retried, one try per round, never in the audit). `python -m licence_studio telegram-webhook` sets the webhook. Signing for a button never extends the key's unlock time. An older relay or one in trouble never stops a round. Codes issued by a button are labelled as such. `tests/test_telegram_buttons.py` (23, real Worker over HTTP) and a browser test.
- Found by the independent review of this PR and fixed before merge: the round aborted when `/licence/states` failed; the policy loop re-worded a button-approved request each round; the alert could carry buttons that always fail; an upgrade needed an `ALTER` that re-running `schema.sql` would not do; an old approval measured with the PC's clock; the shop was told «approved» for paid requests; the copy could be lost when the PC was killed mid-send or sent to a group; wrong-secret floods cost database queries.
- `docs/TELEGRAM_APPROVED_ACTIVATION.md` and `docs/LICENCE_ACTIVATION.md`: status, what was built, where it differs from the design on purpose, threat-model rows.
- **Not done / not claimed:** nothing is deployed; no real bot or chat was used; no fresh-install challenge; the Windows clean-PC trial and a live approval on a phone are the owner's.

## 0.13.0 (2026-10-09)
Records for the activation chain and the practice shop. No code, package or catalogue change in this entry (the code is in the stacked PRs for the relay and the Studio).
- **Licence mailbox on `templates/telemetry-relay`:** a shop asks for a trial or a paid code, the owner's phone is told on **Telegram** (not WhatsApp), the owner's trusted PC signs, the shop checks the code with the public key and switches itself on. The signing key is never in the bot or the cloud. Spec and threat model: `docs/LICENCE_ACTIVATION.md`.
- **Licence Studio 1.1.0:** pulls requests, applies the owner's policy (automatic trials **off** until the owner switches them on), one trial per PC in an append-only ledger, monthly and permanent only after payment is confirmed and the owner approves, «افضل مفتوح N ساعة» for the key (at most 12 hours).
- **`docs/PIXEL_PLUS_WEBSITE_REQUIREMENTS.md`:** pages, honesty rules, the three ways to "try it", lead intake (Telegram alert, no automated WhatsApp), non-functional limits, acceptance checks and the owner's open items. Nothing is built or hosted.
- **Review fixes (Codex, before merge):** the relay's limits and insert are one statement; payment references and phone-like digits are not kept in the cloud; an issued trial nobody collected still counts as given; the Studio decides each request once (owner or automatic round), never reports a request the relay closed as sent, never lets automatic signing keep the key open past the owner's deadline, reads the waiting list page by page, and counts the daily cap in UTC.
- `DECISIONS.md`, `PARTS.md`: the Telegram channel and the trial-policy defaults recorded as decisions awaiting the owner's numbers; Studio 1.1.0.

## 0.12.0 (2026-10-09)
- **af-license 0.3.0:** new code edition `perpetual`, always device-bound: issuing one without a device fails (`device_required`), and a reader refuses an unbound one (`unbound_perpetual`). It never expires: its last day is stored as day 65535 and readers report no last day. Older readers refuse it (`unknown_edition`). Tests cover a monthly code (days → grace → expired), a perpetual code (2299, other device, not yet valid) and an older reader.
- **Licence Studio:** quick buttons «تجربة 14 يوم», «اشتراك شهري» (standard 30 days + 3 grace) and «تفعيل دائم» (device-bound). The codes list, WhatsApp text and verify page show «دائم». The MCP `request_code` accepts `perpetual`. The full-chain test proves that each kind unlocks Al-Store.
- `docs/knowledge/LESSONS.md`: release-proof lessons from Al-Store 1.5.0 (backup `.part`, one-file copies, empty-database review, extending a signed format, a real shop through an update).
- `examples/al-store-product.json`: evidence from Store 1.5.0.

## 0.11.3 (2026-10-09)
- Added owner-approved four-plan small-business offer independent of existing connectivity engine, with exact cloud-backup and mobile acceptance evidence required at release when `commercial_plan` is declared; legacy manifests unchanged.
- Factory Windows contract CI on `windows-2025` for PR and main; guidance now requires each Windows product to build/install/test on PR and main and separately test clean-PC recovery. Store Windows workflow PR trigger proposed in companion PR.
- Cloud restore, multi-device sync and installed mobile are **not implemented** by this release. No product functionality or existing customer data changed.

## 0.11.2 (2026-10-09)
- **af-guide 0.1.2:** the guide button no longer reads «الدليلnull» when the person has no course (signed out, or a role without one). `replaceChildren` printed the missing badge. A new browser test fails on 0.1.1. Store vendors 0.1.2.
- `examples/al-store-product.json`: IAM-01 is `verified` by Store 1.4.0's owner recovery code. `DECISIONS.md` records it.

## 0.11.1 (2026-10-09)
Al-Store evidence and stale facts. No code, package or catalogue change.
- `examples/al-store-product.json`: the core journey is cash only (owner decision); `control_evidence` now records each of the 32 core controls with its real proof in Store 1.3.0 (20 `verified` by green tests, 12 `implemented` with what is still missing). `--release` now lists 12 missing proofs plus the two field items instead of 32.
- `PARTS.md`: Store vendors af-guide 0.1.1, af-consent 0.1.0 and af-telemetry 0.2.0 (byte-identical below the header); the "no product has vendored it yet" lines were wrong.
- `DECISIONS.md`: Al-Store cash-only decision; three new open items (optional features start off as a factory rule, owner password recovery in IAM-01, how customers pay for their licence).

## 0.11.0 (2026-10-09)
Docs diet (review item A12). Agents and people read three files, not 27. No code, package, template, workflow or catalogue change; the only edits outside Markdown are two lines of text: the `prompt` command's reading list in `scripts/factory.py` and the doc links in `CONTROL_CENTER.html`.
- **Five living docs:** `README.md`, `RULES.md` (32 core controls with how each is checked, firm privacy limits, agent workflow, Arabic standard), `PARTS.md` (every shared part: version, vendoring, spec, users), `PLAYBOOK.md` (tests, drift check, release, controls, products, alerts), `DECISIONS.md` (dated decisions, ADR index, open items).
- **`AGENTS.md` read order is three files:** README, RULES, PARTS. `CLAUDE.md` and `GEMINI.md` point to it. The legal framing in "Task classification" is gone.
- **New:** `tests/test_docs.py` (living docs exist, read order, no broken relative links, no legal wording in living docs) and `docs/archive/README.md`.
- **Reference specs:** 15 specs that code, tests, workflows, packages or products link to stay in `docs/` with one first line pointing to RULES and PARTS. Obvious legal wording was removed from them and from ADR-0001.
- **`docs/DESIGN_SYSTEM.md` section 9** now holds the states, forms, shell and RTL rules of the old UX standard.

| File | Where it went |
|---|---|
| `FACTORY_CONSTITUTION.md` | `docs/archive/` (essentials in `RULES.md`; decisions in `DECISIONS.md`); a 3-line redirect stub stays at the old path because Store/CLAUDE.md names it |
| `docs/OPEN_POINTS.md` | `docs/archive/` (merged into `DECISIONS.md`); a 3-line redirect stub stays at the old path because `alerts.py` and the relay README name it |
| `docs/MARKET_AND_STANDARDS.md` | `docs/archive/` |
| `docs/REPOSITORY_AUDIT.md` | `docs/archive/` (see `docs/knowledge/REPO_MAP.md`) |
| `docs/COMMERCIAL_PLATFORM_BENCHMARK.md` | `docs/archive/` |
| `docs/BUILD_PLAN.md` | `docs/archive/` |
| `docs/ADOPTION_PLAN.md` | `docs/archive/` |
| `docs/HESSA_FACTORY_ALIGNMENT.md` | `docs/archive/` |
| `docs/UX_DESIGN_STANDARD.md` | `docs/archive/` (merged into `docs/DESIGN_SYSTEM.md` section 9) |
| `docs/ci/PENDING_WORKFLOW_CHANGES.md` | `docs/archive/` (every step is already in the workflows) |
| the other 15 `docs/*.md` specs, `docs/decisions/`, `docs/knowledge/` | unchanged path |
| `AGENTS.md`, `CLAUDE.md`, `GEMINI.md`, `README.md` | rewritten short |

## 0.10.1 (2026-10-09)
Help docs fitted to the 0.10.0 catalogue (controls catalogue 1.10.1). No code change; `packages/af-guide`, `scripts/vendor_guide.py` and the workflows are the 0.10.0 copies.
- **Help standard:** `docs/HELP_AND_GUIDANCE_STANDARD.md` gets §2 the learning path per role (setup first for the administrator, "you are here" from catalogue states, `course()` / `state()`) and §3 «العربية الميسّرة» with the stiff-word rule and a three-column example table. Both point to HELP-07 and HELP-11.
- **HELP-08 folded into HELP-07:** the proposed "learning path" control is not a new id. Its wording (administrator's course starts with setup; "you are here" with one Start button, found from real records) is now in HELP-07's requirement. `factory.py controls HELP-08` still says "merged into HELP-07".
- **Capability matrix:** new `docs/knowledge/CAPABILITY_MATRIX.md` (which product has which capability, what moves where), listed in `docs/knowledge/README.md`; `CAPABILITY_MAP.md` help row names the learning path; `LESSONS.md` gets "Help that teaches".
- **Not in the package (deferred, because it would change code the products vendor):** administrator-path-starts-with-setup check, a warning when most lessons have no state, and the stiff and street Egyptian word lists beyond `style/ar-lexicon.json`.

## 0.10.0 (2026-10-09)
Rules cleanup (step 1 of the simplification). Controls catalogue 1.10.0: 138 controls became 107 (32 core, 75 reference), plus 24 merged ids and 7 retired ids.
- **Core gate:** every control has `"tier": "core"` or `"reference"`. `check --release` fails only on applicable core controls without verified proof. Reference controls are printed as advice (count and ids) and never block. `doctor` prints the core, reference, merged and retired counts.
- **The 32 core controls:** IAM-01, IAM-02, IAM-03, IAM-06, IAM-08, IAM-10, IAM-11, DATA-02, DATA-03, DATA-05, DATA-06, OPS-06, SEC-02, SEC-03, SEC-04, SEC-07, LIC-01, BIZ-03, REL-03, OPS-07, OPS-01, QA-02, UX-08, A11Y-01, PERF-01, HELP-07, HELP-09, HELP-11, PRIV-01, PRIV-03, TEL-01, FB-01.
- **Merged** (survivor <- old ids; the survivor lists them in `merged_from`, and `factory.py controls <ID>` and manifests accept the old id):
  - HELP-07 (every role has a path, the coach works, every guide is walked) <- HELP-01, HELP-02, HELP-08, HELP-12
  - HELP-09 (every error code has a problem entry) <- HELP-03
  - HELP-11 (Arabic wording, languages and style lint) <- HELP-04, HELP-10
  - UX-05 (first run, no slideshow) <- HELP-05
  - PRIV-01 (consent, kept append-only, can be withdrawn) <- PRIV-02
  - PRIV-03 (allowlist and never-collect list, in code and in tests) <- PRIV-06, TEL-03, SUP-04
  - FB-01 (problem report with preview) <- SUP-01
  - SUP-03 (customer-approved remote help) <- IAM-05
  - BIZ-03 (no data lock at expiry) <- PROT-04
  - LIC-01 (signed licence codes) <- BIZ-04, PROT-02; now applies to paid products only
  - BIZ-01 (licence limits) <- PROT-03
  - A11Y-01 (axe and keyboard) <- UX-03
  - PERF-01 (UI Lab budgets and effect cost) <- PERF-02
  - UX-09 (af-ui tokens) <- UX-01
  - QA-01 (one quality report) <- OPS-04
  - SEC-04 (TLS, loopback and LAN trust) <- LAN-01
  - IAM-08 (permission catalogue) <- IAM-04
- **Retired** (listed in `retired` in `controls.json`; looking one up prints `retired: <reason>`):
  - OPS-03: paperwork; the checkable parts are DATA-05 and OPS-01.
  - OPS-05: now enforced by GitHub branch protection.
  - HELP-06: a habit with no checkable outcome; HELP-07 and HELP-09 already fail when a guide or problem entry is missing.
  - REG-01, REG-02: the gate has no outside-review step; consent (PRIV-01) and the never-collect limits (PRIV-03) are what is enforced.
  - PRO-01, PRO-02: `check` already requires buyer, problem, core journey and an acceptance scenario in the manifest.
- **Release evidence is two items:** `clean_device_restore` and `core_user_acceptance`. `market_review`, `privacy_review` and `security_review` are gone from the gate. Manifests that still carry them validate; the keys are ignored (the schema keeps them as optional legacy keys).
- **Competitor rows are advice:** fewer than 5 competitor/alternative rows no longer fails `--release`; `check` prints an `ADVICE:` line instead. The hosting-region check for cloud tiers stays.
- **Wording:** no law, legal or jurisdiction wording in the controls; SYNC-10 and SYNC-13 now state the practical outcome (erasure reaches every replica; the customer is told where data is stored). The advisory for cloud tiers says the same in plain words.
- **Unchanged:** all packages, apps, templates, design-factory and workflows. Control ids that stay in the catalogue keep their ids.

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
