> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Customer patch pipeline and the customer Telegram bot (design only)

Status: **design, no code yet**. Recorded 2026-10-09 (Cairo); owner decisions taken at 09:11–09:13.
Builds on [PRIVACY_TELEMETRY_STANDARD.md](PRIVACY_TELEMETRY_STANDARD.md) (events, consent, relay, Control Center) and
[DECISIONS.md](../DECISIONS.md).

## 1. Scope

**In scope:** only problems reported by customers from **deployed programs**:
- in-app problem reports (`fb.problem`, which works without consent);
- incidents the Control Center groups from `err.server` / `err.client` events arriving through the Cloudflare relay or a
  direct POST, and shown on the dashboard.

**Out of scope:** every other PR, every CI or test failure, and internal refactors. They follow the normal factory gates
and do not use this pipeline.

## 2. Flow

```
incident / problem report on the dashboard
  → fix (a bot or the owner) on a branch linked to the incident id
  → Patch Reviewer bot: reviews ONLY when the owner explicitly asks for it (never automatic)
  → owner approval
  → existing GitHub Actions Windows installer workflow builds the EXE  →  GitHub release (notes name the incident ids)
  → delivery to the affected customers (§3)  →  incident status "fixed in X.Y.Z"
  → the next heartbeats show the new version; a new event with the same fingerprint on X.Y.Z re-opens the incident
```

Rules:
- One incident can list several installations, and every one of them is notified.
- The release notes carry incident ids and plain Arabic text («العربية الميسّرة»). They never carry customer data.
- The factory's release gates still apply: `factory.py check --release`, ROLL-01 practice evidence for telemetry, and
  signed licence checks.
- Nothing is merged or released without the owner's approval.

## 3. Delivery: all channels FREE (owner decision 09:12)

| # | Channel | How | Cost |
|---|---|---|---|
| 1 | **In-app notice (primary)** | The program already talks to the relay. It learns of a newer release that fixes one of its incidents and shows «تحديث متاح» with a download/install button that links to the incident and the release notes. | free |
| 2 | Email | A link to the release, sent through the **Resend free tier** (3,000 emails per month, 100 per day) or plain SMTP. The sending domain must be verified with DNS records, which is free. | free |
| 3 | WhatsApp, manual | The dashboard builds a `https://wa.me/<number>?text=<prefilled Arabic text + link>` click-to-chat link. The **owner sends it by hand** from his own WhatsApp. Nothing is automated. | free |
| 4 | Customer Telegram bot (optional, §5) | The bot sends the patch link to customers who linked their installation. | free |

- **Decided and rejected:** WhatsApp Cloud API utility templates for customer delivery.
  - Quoted price: about $0.0036 per message plus 14% VAT in Egypt (rates from 2026-10-01, unverified).
  - It needs a Meta business account and a payment method.
  - The owner decided all customer delivery stays free, so this option is **rejected (no payment)**. It is not an open point.
- **No automated WhatsApp to customers.** This is the anti-ban rule MSG-01: one message at a time, sent by a person.
- **Owner alerts** go to Telegram + email + dashboard. Telegram is a **core** channel (decided 09:26), on as soon as it is
  configured. The WhatsApp owner-alert open point is **superseded by Telegram** (see §7 and [DECISIONS.md](../DECISIONS.md)).

### 3.1 In-app notice: proposed contract

- The relay gains a read-only, cacheable `GET /latest?product=<p>&version=<v>&install=<id>` with a signed answer
  `{version, url, sha256, notes_ar, fixes: [incident ids], min_from}`.
  - The answer is signed with the vendor's Ed25519 release key, the same trust model as licences: the product verifies
    it with the public key only.
  - Because the repos are public, trust comes from the signature, not from secrecy.
- The product shows the notice:
  - only to the installation admin;
  - only when the signature is valid and the version is newer;
  - with a check that the download's sha256 matches before running the installer.
- Events: `upgrade.offered`, `upgrade.ok`, `upgrade.fail` (the last two already exist in `events.json`; `upgrade.offered`
  will be added when this is built).
- Without consent, the check for updates still works, because it sends nothing personal: only product, version and
  install id.

## 4. Privacy and limits

- Only IDs and counts travel. A notice, email or Telegram message carries the release link and the incident id, never
  customer, student or money records.
- Customer contact details (email, WhatsApp number) live in the Control Center's `customers` table, which the owner
  enters. They are never taken from telemetry.
- Delivery attempts are logged per channel (the same pattern as alert deliveries).

## 5. Customer Telegram bot (optional channel; design only)

- **One bot for all customers.** The token is the Control Center's/relay's secret and is never in git.
- **Position:** the in-app notice stays primary. Telegram is an optional secondary channel next to email and the wa.me link.

### 5.1 Linking

1. In the app: Settings → «ربط تليجرام». The app shows a deep link and a QR code:
   `https://t.me/<bot>?start=<one-time code>`.
   - The code is random, single-use and expires after 15 minutes.
   - It is created through the relay for this installation (and person, if a person links).
2. The customer presses Start. Telegram sends `/start <code>` to the webhook. The bot binds that `chat_id` to the
   installation (and person) and replies in Arabic.
3. The bot never asks for or stores a phone number or email. The only thing it keeps is `chat_id` ↔ install/person.
4. **Unlinking:** from the app (Settings → «إلغاء ربط تليجرام») or with `/stop` in the chat. Both delete the binding at once.

### 5.2 Commands (with inline buttons for each)

| Command | Button | Does |
|---|---|---|
| `/start <code>` | — | Links (see above). Without a code, explains how to link from the app. |
| `/update` | «عايز تحديث» | Replies with the latest signed release link for **their** product and version (from the same data as `/latest`). |
| `/problem` | «في مشكلة» | Asks for a short description, then creates an `fb.problem` on the relay for their installation. Text is redacted the same way as in-app reports, and no consent is needed. |
| `/status` | «حالة البرنامج» | Version, last heartbeat and open incidents for their installation (counts only). |
| `/stop` | «إلغاء الربط» | Unlinks. |

- **Patch delivery:** when a release that fixes one of their incidents is published, the bot sends the patch download link.

### 5.3 Hosting and limits

- **Webhook:** a `/telegram/<secret path>` route on the existing Cloudflare Worker relay, checked with Telegram's
  `X-Telegram-Bot-Api-Secret-Token` header.
  - Bindings live in the same D1 database: `tg_links(chat_id, install_id, subject, linked_at)` and
    `tg_codes(code_hash, install_id, subject, expires_at)`.
  - Cost: free. It shares the relay's free-plan limits, which are already an open point.
- **Consent:** the person-level consent flag is respected.
  - Without consent, the bot links at installation level only.
  - It never uses a per-person pseudonym.
  - `/status` shows installation data only.
- The bot never sends marketing, and never messages a chat that has not linked itself.

## 6. When this gets built

This happens after PR3 (Control Center + relay) is merged, as its own PR. It covers:
- the signed `/latest` endpoint;
- the in-app notice in af-telemetry's JS;
- the dashboard "patch delivery" view with Resend/SMTP email and wa.me link buttons;
- the Telegram webhook on the relay (customer bot §5 and owner commands §7).

## 7. Owner Telegram bot (core channel; decided 2026-10-09 09:26)

All of this is free: one BotFather bot (the same bot as §5 or a second one) plus the existing Cloudflare Worker relay.

| Part | Status | How |
|---|---|---|
| **Owner alerts** (customer problems, crashes, licence, and the other alert rules) | **implemented** in the Control Center | `TelegramChannel` is a core channel. It is **on as soon as** `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` are set (the older `CC_TG_*` names still work). It has no separate switch, and settings cannot turn it off. It runs in the same parallel fan-out as email and the dashboard. |
| **Patch approvals** | design | When a fix PR from this pipeline is waiting for approval, the Control Center sends the owner «إصلاح مستني موافقتك» with the PR link and the incident id. Source: a `patch.awaiting_approval` alert raised by the owner/bot that opened the PR, or by a GitHub webhook to the relay. |
| **Owner commands** `/status`, `/incidents` | design | Telegram calls the relay webhook (`/telegram/<secret path>` plus the `X-Telegram-Bot-Api-Secret-Token` header). The Worker **ignores every chat except `OWNER_CHAT_ID`** and queues the command in D1. The Control Center picks it up on its next relay pull (or through a short-poll endpoint) and replies with `sendMessage`, using dashboard data: open alerts, open incidents, silent installations, and per-product versions as counts and ids. No customer records are sent. |

Privacy: owner messages carry rule names, counts, product/version and incident ids only, the same as the other alert channels.

