# Telegram-owner-approved activation: Factory to Store
Owner request: 2026-10-09. **Status (Factory 0.14.0): `implemented` and tested end to end against a fake Telegram and an isolated test-only signing key. Not deployed, not field-verified.** Steps A–D of the implementation order are built (relay webhook with the owner's buttons, local signer, Store screen and polling); E and F (live bot on a real chat, Windows clean-PC trial, operator setup) still need the owner. The rest of this page is the design; what was built and the few places where it differs on purpose are in the section "What was built (0.14.0)" at the end.

## Desired buyer-visible experience
Owner is installing Store in front of a shop:
1. The real app shows the customer's **registered shop/company name**, local device fingerprint and a **«اطلب تجربة ١٤ يوم»** action. Shop owner consent is explicit, and the page explains which minimal information leaves the PC.
2. A single click queues an authenticated, replay-safe request to a tiny HTTPS relay and displays **"طلبك وصل / منتظر موافقة الشركة"**. It must not block local POS thread or wrongly claim the app is active.
3. The **private owner Telegram chat** gets shop/company display name, product, short install/device reference, request ID and requested trial (14 days), with two buttons **✅ موافق** / **❌ رفض**. Approval is not issuance.
4. Only after a verified approval, a **trusted owner's Licence Studio on the owner's actual computer** retrieves the approved request, checks trial policy, prompts/unlocks the encrypted Ed25519 key if necessary, signs an exactly 14-day **device-bound** code. The bot/relay/hosting NEVER possesses the private signing key, key passphrase or a general-purpose signing endpoint.
5. The signer sends the finished public signed code through the authenticated relay to the **originating installation only**. Store polls/backoffs over HTTPS, verifies the signed code locally using its existing public key and checks product/device/start/end, and calls its normal activation routine. The UI changes to «تم التفعيل» and Telegram displays result and **the code** to the owner (fallback for reading out by phone; confidential code sent to *verified owner chat only*).
6. If the shop goes offline: issued code waits with bounded retention. The vendor owner can read the code from their Telegram and tell the shop owner by telephone; shop enters it in the usual code field and verifies **offline**. Online activation resumes safely; never apply a code blindly from the server or treat a server flag as a licence.

Offline/owner-PC-off/Studio-key-locked must be honest: state says queued/approved/awaiting signer, with retry/backoff and optional manual code entry. Fast under ideal connectivity, **not guaranteed instant**.

## Existing reusable implementations
- `packages/af-license` 0.3.0 signs/validates trial, monthly and device-bound perpetual codes; `server/afcodes.py` vendored into Store. Do not weaken device restrictions.
- `apps/licence-studio` issues codes with encrypted **local** private key, its owner-only interface, limited agent trial functions and audit. Existing `issue_trial_code` is off by default; never grant unlimited autonomous issue through an external bot.
- `apps/control-center/control_center/alerts.py` already has outbound Telegram via `TELEGRAM_BOT_TOKEN` + `TELEGRAM_OWNER_CHAT_ID`. Notification delivery is **not** inbound approval workflow.
- `templates/telemetry-relay` Worker+D1 already supports bounded queued events/polling. Its `/telegram` inbound webhook is **planned only** in current docs; extend the existing worker only after test and deploy review, not a paid VPS per customer.
- `Store` already has signed-code, device-ID, licence UI and online/nonblocking support heartbeat. Extend the existing licence page and guide; do not copy a second licence engine.

## Strict security contract before ANY hosted use
- **Consent/data minimization:** name of shop is personal/business information and device identifier pseudonymous. Require the actual installing user’s disclosure/confirmation. Send only chosen shop display name, opaque per-install ID, shortened fingerprint reference (full value only to trusted signer if actually needed), product and request ID. Never send business records, tax ID, phone, payroll, full DB or raw device hardware identifiers in Telegram.
- **Trusted admission:** install ID alone cannot authenticate an unregistered customer. A fresh install needs a one-use challenge/nonce and binding to the device via approved onboarding; unauthenticated submissions stay rate-limited/pending owner review. Do NOT trust only a `device_id` supplied by a client. Assess spoofing/reinstall/old trial abuse honestly; no false "one free trial cannot be bypassed" claim.
- **Telegram:** verify secret webhook token AND allowlisted owner chat ID and callback actor; inline button payload contains ONLY opaque request ID + action, no signer key or code; auth is enforced on server, not based on the button’s label. Expire stale approval, reject changed/duplicate requests, make approve/deny idempotent and one-way; allow revocation before signing.
- **State machine:** created → pending → approved/denied → awaiting_trusted_signer → signed → delivered → locally_activated (or expired/revoked/failed). Retried send must not issue 2 codes or accidentally activate 2 PCs. Every transition stores actor/time/request id/reason; bounded queues with retry, explicit TTL, and user-visible non-sensitive error reason.
- **Token separation:** Store/install token authenticates only its requests/status/code retrieval; signer agent authenticates signed issuance result with a separate minimal-scope token; owner Telegram bot is unable to call issuance directly. No public sign endpoint, no secret in binaries/web assets/repo/CI/logs. Pin trusted product id/device and enforce server-side per-tenant isolation.
- **Sensitive code handling:** signed codes are bearer-value licence artifacts (though device bound). Deliver only to that device and verified owner Telegram chat; short storage retention, redact logs/analytics, never put code in a URL, hide previews on shared-screen if necessary. A forwarded Telegram code still must fail on any other PC.
- **Approvals:** every activation from the button requires owner yes/no. Monthly and perpetual additionally require explicit human approval **and recorded proof of payment**; the bot cannot issue them automatically just because a request arrived. Owner chooses any future auto-approve-trial policy separately; none assumed.
- **Signing machine availability:** safely handle offline or locked Licence Studio; do not decrypt key on the relay, put key in Telegram, maintain permanently unlocked signer, or silently fall back to unsafe issuance.
- **Abuse/cost:** bounded queue, rate limits per installation and source, replay protection, monitoring, quota alerts, estimated Worker+D1 load before signing up. No paid external service without owner confirmation.

## Acceptance matrix required for phase P1
1. New install (approved) → owner gets one private notification with recognizable shop/product/device ID → approves; trusted local Studio unlocks → code signed → app polls, locally verifies, activates, shows 14 days; exactly one audit trail.
2. Owner rejects: no code issued, no activation; clear UI explanation, no leaking rejection detail to arbitrary requesters.
3. Owner chat spoof, bad webhook token, forged callback, old callback, unknown shop, wrong install token, malicious/malformed body, duplicate request, approval double-click: refused and logged (without secrets).
4. Device B obtains device A's code: verifier rejects; perpetual/monthly never generated through trial workflow.
5. Owner computer offline, Studio locked, shop offline, bot unavailable, relay unavailable, restart/power loss in every step: operation queued/resumable without silent success or duplicate trial; manual phone readout works offline.
6. After expiry, shop can **still read, export and back up**; unsupported actions blocked only as existing licence enforcement specifies.
7. UI guide + browser tests AR/EN, all roles, keyboard and mobile sizes; screenshots before/after plus network and DB state. No skipped successful tests.
8. End-to-end test with a **fake Telegram API** and an **isolated test-only signing key**; a separate owner-controlled live chat + Windows clean-PC trial with approved real secrets, never captured in CI artifacts.
9. Check portal state (requested / pending / approved / signed / delivered / activated), notifications retry, owner receipt, cost/quota; no success claim until the entire journey was verified on real installations.

## Implementation order / independent review
A. Short ADR plus request/status/poll payloads & fixed privacy schema and finite-state machine tests.
B. Relay endpoints with Telegram webhook and mock bot/owner, strict rate-limited onboarding and auth, **no signing**.
C. Local trusted Studio agent with owner-approved queue and encrypted key; test signed returns, lock/unlock and restart.
D. Product UI button + server handling + polling + local licence validation and offline fallback; test against an isolated fake relay and signing stub.
E. System integration & malicious actor tests; Windows PR+main installer; full live owner demo only with permission and explicit deployment cost decision.
F. Write operator setup: BotFather secret and chat-id in secured environment, worker URL, signing PC online/locked behavior, key recovery, support checklist; after user approval and tests, canary first.

Source docs: [Factory current protection](PROTECTION_UPDATES_AND_SUPPORT.md), [patch bot architecture](CUSTOMER_PATCH_PIPELINE.md), [company execution](PIXEL_PLUS_EXECUTION_ROADMAP_2026.md).

## What was built (0.14.0)

| Step in the design | Where | How it is checked |
|---|---|---|
| Alert with **✅ موافق / ❌ رفض** (button data = action + opaque request id only) | `templates/telemetry-relay/src/licence.js` (`alertText`, `keyboard`) | `test/telegram.test.mjs` |
| Webhook `POST /telegram`: secret token **and** allow-listed owner chat **and** callback actor; stale buttons refused; idempotent; refusals logged without secrets (capped; a wrong secret costs no database query) | `handleTelegram` | 19 relay tests: wrong/missing secret, other person, group chat, copied message, junk body/data, double click, old button, log cap |
| **رفض** closes the request at once; a denial is final; **موافق** only records the owner's decision (table `licence_owner`); the owner may withdraw it until the code is signed | relay + `schema.sql` (a new table: re-running the file is the upgrade) | same |
| Trusted signer: only the Licence Studio on the owner's PC, key unlocked, signs; the relay and the bot never hold a key or a signing endpoint | `apps/licence-studio` `autotrial.py` (`decide_auto` with `by='telegram'`) | `tests/test_telegram_buttons.py` (real Worker over HTTP) |
| Hard rules still hold after «موافق»: one trial per PC (append-only ledger), well-formed device and PC tag, known product; the owner's own daily cap and flood check do not hold back a request the owner chose by hand | `verdict(approved=True)` | button tests |
| Monthly / permanent: the button records intent only; signing needs the payment tick and reference in the Studio | `verdict` (`payment_needed`) + `decide` | button tests (paid) |
| The Studio closes a request the owner refused on the phone, and refuses to sign for one the relay closed meanwhile | `sync_closed`, `refresh_one`, relay `POST /licence/states` | button tests |
| Code delivered to the **originating installation only**, checked locally with the public key, activates | existing `/licence/status`, Store `server/trial.py` | Store `tests/test_trial.py`, Studio `test_store_chain.py` |
| **A copy of the code to the owner's chat** for the phone readout: once per request, claimed atomically, retried until Telegram accepts it, never in the audit or a log | `send_copies` | button tests (retry; 6 concurrent senders give 1 message) |
| The shop is told honestly «الشركة وافقت، الكود جاي» (`stage: approved`) without being treated as active | relay `/licence/status`, Store 1.8.0 | Store tests |
| Setting the webhook up (`setWebhook` with `secret_token`, only `callback_query`, https only) | `python -m licence_studio telegram-webhook` | button tests |

**Differences from the design, on purpose.**
- The relay edits the owner's message to show the outcome and, after an approval, leaves one button «❌ سحب الموافقة» (revocation before signing).
- An approval counts for 72 hours by default (`LICENCE_APPROVAL_HOURS` on the relay, at least 1). The **relay** judges it (it answers `expired`), never the owner's PC clock; after that the owner approves again in the Studio.
- Before the Studio signs without the owner at the keyboard it asks the relay once more whether the request is still open (an owner who refused a second ago gets no code); if the relay cannot confirm, nothing is signed that round. A relay older than 0.14 (no such call) is simply not asked.
- The signer **pulls** (it never listens): nothing reaches the owner's PC from the internet. The round is every 60 seconds while the Studio runs, so «instant» means about a minute plus the shop's 20-second look, and only while the Studio is open and unlocked.
- No fresh-install one-use challenge was added. The admission rules are the existing ones (nonce, per-address / per-device / waiting-list limits, one trial per machine tag); spoofing by a determined person with a new identity remains possible and is stated in the threat model of `LICENCE_ACTIVATION.md`.

**Still not done (needs the owner):** create the bot and the Worker secrets; run `telegram-webhook`; a live approval on a real phone; a Windows clean-PC trial with real secrets; the owner's decision on a fresh-install challenge.

## Hardening (0.15.1)
- Codes go only to the owner's **private** chat (a positive id). Plain alerts (no code in them) may also go to a group (a negative id). A pasted id is trimmed.
- An approval that nobody used for longer than `LICENCE_APPROVAL_HOURS` is stale: a repeated «✅ موافق» says so and signs nothing.
- A copy of a code is sent only while the code is under two days old; older unsent copies are settled as skipped.
- A waiting request the relay does not know is kept and marked `relay_gone` for the owner (never signed automatically); closed as expired after three days.
- The Studio's click returns when the decision is saved; delivery and the copy run on their own thread and are retried each round.
