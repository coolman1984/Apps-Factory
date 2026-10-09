# Consent, telemetry and problem reports (af-consent, af-telemetry)

- **Decision:** [ADR-0007](decisions/ADR-0007-consent-telemetry-feedback.md).
- **Controls:** `PRIV-01`…`PRIV-06`, `TEL-01`…`TEL-03`, `FB-01`, `ROLL-01`, `SUP-04`.
- **Packages:** [`packages/af-consent`](../packages/af-consent/README.md), [`packages/af-telemetry`](../packages/af-telemetry/README.md).
- **Server side:** the Control Center ingest, alerts and dashboard ([apps/control-center](../apps/control-center/README.md)), and the Cloudflare relay ([templates/telemetry-relay](../templates/telemetry-relay/README.md)).
- **Customer patches (design only):** [CUSTOMER_PATCH_PIPELINE.md](CUSTOMER_PATCH_PIPELINE.md).

**Goal:** the vendor sees problems before the customer calls, and sees how each person uses the program and the guides. Nothing personal leaves the customer's PC.

## 1. Firm limits (in code and tests, never "by convention")
- **Never sent:**
  - passwords;
  - keystrokes or typed text;
  - screenshots;
  - names, phones, national IDs, e-mails or addresses;
  - amounts or prices;
  - full customer, student or money records.
- **Only sent:** short machine IDs (page, action, guide, error code, fingerprint), counts, durations and true/false values.
  - The field list per event type is in `packages/af-telemetry/events.json`.
  - Any other field raises `PrivacyError`.
  - A field *name* on the never-list is refused even if someone adds it to the taxonomy.
- **A person** is `p_<16 hex>`: an HMAC of the person ID with the installation's own secret.
  - The vendor sees usage **per person** (owner decision), but cannot know who the person is.
  - The customer's program can show the same reference on its People page.
- **Errors** send the exception type, a fingerprint of the program's own frames and `module:function`. The message text is never sent.

## 2. Consent
| Level | Who | When | Effect |
|---|---|---|---|
| Installation | The customer's owner | Settings, or the first-run card | Without it, **nothing** is queued except problem reports |
| Person | Each person who signs in | Once, at first sign-in | Person events only after «أوافق». A decline means zero events and no repeat questions |

- **Prompt** (text ID `consent.help.remote.ar.v1`): «أوافق حتى يستطيع [vendor] مساعدتي عن بُعد». The two buttons, «أوافق» and «لا أوافق», look the same and neither is pre-selected.
- **Vendor name:** one setting, `vendor_display_name`.
  - Default: the product's `DEVELOPER`, which is what the About box already shows ("Mohamed Fawzy" in Hessa, Trip Orders and BAMS).
  - Fallback: `coolman1984`.
- **Settings «الخصوصية والمساعدة»:**
  - shows the current state and history (who, when, the exact text);
  - lets the person withdraw. Withdrawal deletes that person's pending events at once;
  - optionally shows «ماذا أُرسل؟» (PRIV-05).
- The **support window** (SUP-02) stays a separate, time-boxed permission.

## 3. Problem reports (FB-01)
- «أبلغ عن مشكلة» (problem, idea or question) is reachable from every page through the «الدليل» panel.
- **Allowed without tracking consent** (owner decision). No person reference is attached when the person did not agree.
- Phones, e-mails, ID numbers and secrets are removed on the PC. The Control Center removes them again on arrival.
- The person sees a **full preview**. The send carries the preview's digest, so a changed text is refused.
- Device info is optional and limited to an allowlist of counts and versions.

## 4. Outbox and transport (TEL-01, TEL-02)
- **Separate `telemetry.db`.** It holds at most 5,000 events, 5 MB, or 30 days of events. When a limit is reached, the least important events are dropped first.
- **Hourly merge.** Usage and repeated errors are merged per hour into counts.
- **Batches.** Each batch is at most 256 KB and gzip-compressed.
- **Transport (protocol 2, factory 0.9.0).** Each batch goes over HTTPS with the installation's token (`Authorization: Bearer`, `X-AF-Install`, `X-AF-Sent-At`). There is no signature, nonce or time window. Every event has a unique id and the receiver stores ids once, so a replay only counts duplicates.
- **Clock.** Every answer carries the receiver's `server_time`. The outbox keeps the difference and stamps later events with corrected time. The Control Center also corrects a batch whose clock is more than 2 minutes off, and shows the difference per installation. A wrong clock is never a reason to refuse.
- **Retry.** A failed send waits before retrying, starting at 1 minute and growing to at most 6 hours. Some batches go to the bounded `dead` table (see `dead_letters()`) instead of being retried forever:
  - a batch the receiver refuses as bad (400/413/422);
  - events refused 12 times.

  No network at all only waits; the 30-day limit still applies.
- **Required fields.** `events.json` can mark fields as `required` (for example `code` and `fingerprint` of `err.*`). An event without them is refused on the PC, and again on arrival.
- **New PCs.** A PC that was not registered first may create its own id and token (`af_telemetry.new_identity()`). Its batches wait as «new PC» until the owner approves it on the dashboard; nothing from it is used before that.
- **Browser events** go only to the product's own server (`POST /api/telemetry/events`), which applies consent and the limits. The person always comes from the session, never from the request body.

## 5. Rollout (ROLL-01)
Telemetry starts on **demo/practice data first** (`env: practice`). Only after it has been checked end to end is it switched on for real installations.

The manifest records this:

```json
"telemetry": {"rollout": "practice"}
```

`installations` needs `practice_evidence`; `factory.py check` fails without it.

## 6. Product adoption (per product, separate PRs; not started)
1. Vendor the packages:
   ```
   python scripts/vendor_consent.py <repo>
   python scripts/vendor_telemetry.py <repo>
   ```
2. Add the consent table (`afconsent.SQL`) to the migrations, and create `telemetry.db`.
3. Add the routes:
   - `/api/consent/prompt`, `/api/consent` (POST), `/api/consent/status`;
   - `/api/telemetry/events`, `/api/telemetry/feedback/preview`, `/api/telemetry/feedback`;
   - optional: `/api/telemetry/sent` for the «ماذا أُرسل؟» viewer.
4. Wire af-guide's `track` and `onReport` options to `AFTelemetry`.
5. Call `tel.capture(exc)` in the server's error handler, and send from a background thread every 5 minutes.
6. Add the PRIV/TEL tests to the product suite, and set `telemetry.rollout` to `practice` in the manifest.

## Server side (Control Center)
- **Arrival checks:** every batch is checked again on arrival:
  - the installation's token (sha256 compared with the stored hash) and an active installation;
  - unknown installations are parked (small caps) until the owner approves them;
  - exact envelope;
  - `p_` pseudonyms only;
  - allowlisted fields;
  - a second redaction of report text.

  Rejected events are counted, with a reason, in the audit log and never stored. Each event is its own savepoint inside one transaction per batch. A bad event never takes the rest of the batch with it, and the relay deletes a batch only after it was stored (or kept in quarantine).
- **Alert fan-out:** alerts go to every enabled channel in parallel, and each channel's result is logged.
  - Channel secrets live only in environment variables.
  - Alert text carries rule names, counts and ids, never customer records. A problem report goes out as its ticket number, category, page and a dashboard link. The customer's own words stay on the dashboard.
  - Alerts are queued while events are stored, and sent afterwards by a background sender, outside the database lock. A slow mail server never freezes the dashboard.

Open cost and verification points for the relay and the alert channels are listed in [OPEN_POINTS.md](OPEN_POINTS.md).
