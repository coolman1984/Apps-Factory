# Vendor Control Center (برج المراقبة) v0.3.0

**Status:** `implemented` — API/UI and telemetry tests pass (`tests/`). **Not deployed, not field-verified.** Manifest: [examples/vendor-control-center.json](../../examples/vendor-control-center.json) • Spec: [PROTECTION_UPDATES_AND_SUPPORT.md](../../docs/PROTECTION_UPDATES_AND_SUPPORT.md) §3–5.

## What works now
- Customer and install registry; one-time install tokens (stored hashed); deactivate an install.
- Heartbeats with a fixed field list (unknown fields refused) and Arabic health reasons: stale, old backup, licence, errors, unsynced changes, low disk.
- Help tickets from products, redacted on the server (Egyptian phones, national IDs, e-mails, secrets, keys) and marked as untrusted text.
- Customer-initiated support grants (max 120 minutes, named approver, 9-digit code); the customer can end them; ending cancels pending repairs.
- Repairs: allowlist of 4 non-destructive actions, only under a live grant with `repair` scope; the AI agent token can only *request*; the owner approves.
- Licence desk: claims template per install → sign **offline** with `af-license` → upload; the server verifies the signature before storing; expiring list.
- Audit of every write; UUIDv7 IDs; forward-only migrations; Arabic RTL dashboard (customer text rendered as text only).

- **Telemetry (0.2.0):**
  - **Ingest (protocol 2, 0.3.0):** gzip event batches with the install token (`Authorization: Bearer`, over HTTPS), either through `POST /api/agent/events` or pulled from the Cloudflare relay (`templates/telemetry-relay`).
    - The token is compared with the stored sha256. A deactivated install gets 403. There is no time window: a replay only counts duplicates (event ids are stored once). Every answer carries `server_time`. A clock that is more than 2 minutes off is corrected and shown per install (`clock_skew_s`).
    - Every event is checked again against the firm limits (exact envelope, `p_` pseudonyms only, the allowlisted and **required** fields of `events.json`, and a second redaction of report text).
    - **One transaction per batch, one savepoint per event:** a bad event (or a bug in a rule) is rolled back alone and counted with a reason (`reasons` in the answer and the audit log). Database trouble keeps the whole batch for a retry.
    - **Relay:** a batch is acknowledged (deleted on the relay) only after it was stored, parked as pending, or kept in `rejected_batches` (quarantine, 30 days, at most 1000). The list of installs (id + token hash) is pushed to the relay when it changes, so the relay refuses strangers cheaply. Network calls run outside the database lock.
  - **New PCs:** a PC that is not registered yet is not dropped. Its batches wait in `pending_installs` / `pending_batches` (at most 50 PCs, 20 batches of 64 KB each, 30 days). The dashboard lists them under «أجهزة جديدة مستنية موافقتك»: approve (choose the customer and tier; the PC keeps its id and token, and its batches are replayed) or discard. API: `GET /api/installs/pending`, `POST /api/installs/pending/{id}/approve`, `POST /api/installs/pending/{id}/discard`.
  - **Incidents:** grouped by product + fingerprint, with counts, installations and versions. An incident re-opens when it returns on a new version, and the `regression` rule alerts once per fingerprint and version.
  - **Usage:** per person (pseudonym) per day.
  - **Guides:** a guide funnel (started, finished, abandoned).
  - **Releases:** errors and failed upgrades per release.
  - **Problem reports and ideas:** stored as tickets (untrusted text).
- **Alerts (`control_center/alerts.py`):**
  - **Rules:** 12 rules:
    - new incident;
    - spike (errors of one fingerprint **within the last hour**, so it stops by itself);
    - regression (a known fingerprint in a new version);
    - spread across 3 installations;
    - failed upgrade;
    - failed backup;
    - stale backup (48 working hours);
    - silent installation (26 working hours);
    - failing sync;
    - licence attention;
    - problem report;
    - permission friction.

    Rules can be switched off and their thresholds changed in settings. A 6-hour de-duplication applies. Silent installation and stale backup count **working hours** in Africa/Cairo. Friday is always off; Saturday is off with the `saturday_off` setting. They alert **once** per silence or per stale backup, not every 6 hours.
  - **Delivery outside the lock:** alerts raised while events are stored are queued in the same transaction. A background sender then sends them outside the database lock, with per-channel time limits. A slow mail server never freezes ingest or the dashboard.
  - **Problem reports:** the channels get the ticket number, category, page and a dashboard link (`CC_DASHBOARD_URL`, default `http://127.0.0.1:8765/`), never the customer's text.
  - **Fan-out:** every alert is sent to **all enabled channels at the same time** (a thread pool, one task per channel). There is no priority and no fallback. A failing or hung channel never blocks the others: each one has its own try/except and a time limit. Every channel's result is logged in `alert_deliveries` (`sent`, `failed`, `unsupported`, `disabled`, ms) and shown on the dashboard.
  - **Channels:**

    | Channel | Settings (environment only, never stored or shown) | Default |
    |---|---|---|
    | dashboard | — | always on |
    | email | `CC_SMTP_HOST`, `CC_SMTP_PORT`, `CC_SMTP_USER`, `CC_SMTP_PASSWORD`, `CC_ALERT_EMAIL_FROM`, `CC_ALERT_EMAIL_TO` | on when configured |
    | whatsapp | `CC_WA_TOKEN`, `CC_WA_PHONE_NUMBER_ID`, `CC_WA_TO`, `CC_WA_TEMPLATE` (+ `CC_WA_TEMPLATE_LANG`). Without a template, plain text only reaches the owner inside WhatsApp's 24-hour window. **superseded by Telegram for owner alerts**; left unconfigured | on when configured |
    | telegram | `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID` (or `CC_TG_BOT_TOKEN`, `CC_TG_CHAT_ID`). Free; **core owner channel** (owner decision 2026-10-09 09:26). | **on as soon as configured**; no switch |
    | linkedin | `CC_LINKEDIN_TOKEN`. **Cannot deliver:** member DMs are partner-only and automated sends are prohibited, and the free API only makes public posts on your own profile. The adapter logs `unsupported` and never posts. «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» | **off** |

  - **Settings:** `GET/PUT /api/alert-settings` (owner) holds on/off switches and thresholds only. Secret-looking keys are refused. `POST /api/alerts/test` queues a test alert for every enabled channel. The results appear under `/api/alerts` a few seconds later.
- **Retention:** raw events 90 days, alerts and fixed incidents 12 months, daily usage 24 months, pending PCs and quarantined batches 30 days. It runs daily in the background, or once with `python -m control_center retention`.

## Not yet
MCP gateway process for the AI agent (the API is its backend), product-side agent library, GlitchTip/RustDesk/Uptime Kuma deployment, owner MFA, HTTPS deployment, backups of this server.

## Run
```bash
pip install -r requirements.txt
export PYTHONPATH=../../packages/af-license CC_DB=data/control-center.db
export CC_LICENCE_PUBLIC_KEYS="<kid>:<public key>"        # from: python -m af_license keygen
python -m control_center token --kind owner --name "Owner"  # printed once
python -m control_center token --kind agent --name "AI agent"
python -m control_center serve --host 127.0.0.1 --port 8765 # put HTTPS (reverse proxy) in front before going online
# telemetry relay (optional; see templates/telemetry-relay):
export CC_RELAY_URL=https://<worker>.workers.dev CC_RELAY_TOKEN=<same as RELAY_PULL_TOKEN>
python -m control_center pull-relay   # once; `serve` also pulls every CC_RELAY_EVERY seconds (default 300)
python -m control_center alerts       # time-based rules once
python -m control_center retention    # clean-up once
python -m unittest discover -s tests -v
```
