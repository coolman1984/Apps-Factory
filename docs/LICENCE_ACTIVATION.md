# Licence activation chain: request → Telegram → policy → code → the shop switches itself on

Reference spec (not a living doc: rules are in [RULES.md](../RULES.md) LIC-01 and BIZ-03, parts in [PARTS.md](../PARTS.md)). Written for Al-Store; any product with a device-bound code can use it.

**Owner decisions behind it** ([DECISIONS.md](../DECISIONS.md)): the three kinds of code (14-day trial, monthly, permanent); **Telegram is the owner's notification channel, not WhatsApp**; the private signing key lives only on the owner's trusted PC; automatic issuing follows a trial policy the owner switches on; subscriptions and permanent activation need confirmed payment and the owner's own approval.

**Status:** `implemented` and tested end to end over real HTTP (relay Worker + Licence Studio + codes), including the owner's **✅ موافق / ❌ رفض** buttons on Telegram (0.14.0, section 4b). **Not deployed.** Not field-verified. What the owner still has to do is in section 9.

## 1. The chain

```
 shop PC (Al-Store)                relay (Cloudflare Worker + D1)            owner's trusted PC
 ─────────────────                 ───────────────────────────               ──────────────────
 «اطلب تجربة 14 يوم»  ──POST /licence/request──►  row "pending"  ──Telegram──►  owner's phone: "طلب جديد" [✅ موافق] [❌ رفض]
 (device code, machine tag,                        (no signing key)   ◄──POST /telegram (secret token + owner chat)
  nonce — no secret)                                     ▲   │
                                              GET /licence/pending │ POST /licence/decide
                                                          │   ▼
                                                  Licence Studio pulls, sees «موافق» (or applies the policy),
                                                  signs with the key held in its memory only,
                                                  sends the owner's phone a COPY of the code (manual way)
 shop polls  ◄──GET /licence/status (poll token)──  row "issued" + code   (before that: stage "approved")
 verifies the code with the vendor's PUBLIC key,
 saves it, switches itself on  ──POST /licence/ack──►  the code leaves the relay
```
No copy and paste on the happy path. The manual way (device code out, code in) stays on the same screen.

## 2. What already existed, and what was reused (inventory first)

| Part | Used for | Changed |
|---|---|---|
| `packages/af-license` (codes) | the signed, device-bound code, verified offline with the public key | **nothing** |
| `apps/licence-studio` | the only place that signs; key lock, append-only codes and audit, agent requests, MCP | relay client, request intake, owner policy, trial ledger, payment gate |
| `templates/telemetry-relay` | a Cloudflare Worker + D1 mailbox the shops can reach (the shop PC is behind a router; the owner's PC is not reachable) | licence mailbox added (same D1, same limits discipline, same test shim) |
| `apps/control-center` | customer/install registry, heartbeats, alerts incl. Telegram, licence desk | **nothing.** Its licence desk works for a *registered* install (after the sale, token known). A shop asking for its first trial is unknown to it, so the relay and the Studio carry this part. The Control Center's licence state and expiry alerts keep working on the code that results. |
| Store `licence.py` | device code, check, save of the code | the client side (Store repo `server/trial.py`) |

Duplicated on purpose: a 15-line Telegram sender in the Studio and the Worker (the Studio and the Worker cannot import the Control Center). Both use the same environment names.

## 3. Request, replay and answers (relay protocol)

`POST /licence/request` (JSON, ≤ 2 KB, no secret): `product`, `kind` (`trial` | `monthly` | `permanent`), `device` (10-character code), `machine` (sha256 tag, required for a trial), `nonce` (the shop's own UUID for this request), optional `shop` (≤ 60 characters; runs of 7+ digits are blanked: no phone or account numbers in the cloud), `ref` (accepted but **not stored**: the owner writes the payment reference in the Studio), `version`. The per-address, per-device and waiting-list limits are checked in the same statement that stores the request. `GET /licence/pending?after=<created_at>:<id>` reads the next page.

| Answer | Meaning |
|---|---|
| 202 `{id, poll_token, status:'pending'}` | new request, owner alerted; the poll token is shown **once** (only its hash is stored) |
| 200 `{id, status, replay:true}` | same `nonce` again: **nothing created, nobody alerted, no token** |
| 202 `{status:'issued', reason:'reissued'}` | the code for this very device is already waiting (the shop lost its token): the same code is handed over, not a second trial |
| 200 `{status:'refused', reason:'already_used'}` | this PC or this device already had a trial: refused quietly, the owner is not woken |
| 429 / 503 / 400 | rate limit, waiting list full, a field named in `field` |

`GET /licence/status?id=` and `POST /licence/ack` need `Authorization: Bearer <poll token>`; an unknown id and a wrong token look the same. Owner side: `GET /licence/pending`, `POST /licence/decide {id, action: issue|refuse, code|reason}`, `GET /licence/events`, with `LICENCE_ADMIN_TOKEN` (never the telemetry token). Decisions are repeatable (a retry after a network error is fine) and a conflicting second decision is 409. An issued trial nobody collected expires as `unacked` and still counts as given.

## 4. The trial policy (Licence Studio; OFF until the owner switches it on)

Automatic only when **all** hold: the key is unlocked; the device code and machine tag are well formed; the product is known; **this PC never had a trial** (permanent ledger, one row per product and machine, primary key so even a race cannot issue two); today's cap is not reached (default 10); the sender is not flooding (more than 5 requests from one address in a day are held for the owner, never refused: shops share addresses). Terms: 14 days at most, bound to the device.

- A second request from the **same device** gets the **same code** again.
- Another device on a PC that had its trial is refused (`already_used`): reinstalling does not give a second trial, because the machine tag does not change with the install.
- A policy refusal needs no key and is delivered to the shop with its reason.
- Everything else waits for the owner and the shop sees "waiting".

**Key handling.** The key is encrypted on disk and lives in memory after the passphrase. For unattended issuing the owner chooses «افضل مفتوح N ساعة» (at most 12): the key stays in memory for that time only; locking, a restart or the end of the time puts it back behind the passphrase. If the key is locked when a request arrives, the request waits, the owner's phone says so once, and the next round after unlocking issues it. Nothing signs without the owner having unlocked it that day.

## 4b. The owner's buttons on Telegram (0.14.0)

Every alert carries **«✅ موافق»** and **«❌ رفض»**. Telegram sends a press to the relay's `POST /telegram` (the bot's webhook). The relay trusts a press only when **all** hold: the request carries the secret token Telegram was told to send (`TELEGRAM_WEBHOOK_SECRET`, compared in constant time); the press comes **from** the owner's id **and** was made on a message **in** the owner's private chat (`TELEGRAM_OWNER_CHAT_ID`; a group is refused); the button data is exactly `ok:<request id>` or `no:<request id>`. Anything else changes nothing. A wrong or missing secret is answered 401 without touching the database (the address is public and the plan is free; `wrangler tail` shows it); other refused presses are logged (`tg_refused`, no secret in it, capped at 50 an hour).

| Press | What happens | What does not |
|---|---|---|
| **❌ رفض** | the request is refused at once on the relay (the shop sees «رفض»), the message is edited to say so, no button is left. **Final**: a later «موافق» cannot bring it back. After an approval the button is «سحب الموافقة» and works until the code is signed. | After the code is signed it changes nothing (a code may already be on the shop's PC). |
| **✅ موافق** | the relay records the approval (table `licence_owner`); the request stays waiting; for a **trial** the shop's screen says «الشركة وافقت، الكود بيتجهّز» while the approval counts (never "active"; a paid kind shows nothing new, because it is only the owner's intent). The Studio sees it on its next round and, for a **trial**, signs it **even when the automatic policy is off** (the owner chose this request by hand), then hands the code back. | It signs nothing by itself. The owner's own daily cap and flood check do not hold it back, but every hard rule does: key unlocked, well-formed device and PC tag, known product, one trial per PC. An approval older than the relay's window (`LICENCE_APPROVAL_HOURS`, 72 by default, never less than one hour) is not acted on: the relay answers `expired` and the Studio never uses its own clock. |
| **✅ موافق on monthly / permanent** | records the owner's intent only. | The Studio never signs a paid kind without «الدفع وصل» and a payment reference typed in the Studio (`payment.required`). |

Pressing twice (or Telegram resending) changes nothing. The Studio closes, in its own list, any request the owner refused on the phone (`POST /licence/states`), and refuses to sign for a request the relay closed while its page was open. Whenever a code is signed for a shop's request (by a button, by the policy, or by the owner's click in the Studio) the owner's phone gets **a copy of the code** in the owner's own chat: once per request, retried until Telegram accepts it, never written to the audit or a log. This is the manual way when the shop is offline.

## 5. Paid kinds

`monthly` (30 days + 3 grace, the Studio default) and `permanent` (device-bound, never ends) are **never automatic**. The request waits in the Studio with the reference the shop typed (shown as text). The owner must tick that the payment arrived and write its reference (3 characters or more); the server refuses to sign otherwise (`payment.required`). The approved code goes back through the same mailbox. Payment itself stays manual until the owner decides on Paymob/Fawry/InstaPay.

## 6. Threat model, honestly

| Attack | What stops it | What it cannot stop |
|---|---|---|
| Stealing the signing key from the cloud | not there: relay, bot and Worker secrets hold no signing key | — |
| Reading someone else's code | poll token (hash only), codes bound to one device, code deleted on ack and after 14 days | — |
| Forging a code | Ed25519 signature checked by the shop with the public key; the relay is not trusted | — |
| Replaying a request | `nonce` finds the same row; the answer never repeats the token | — |
| Second trial by reinstalling | machine tag in a permanent ledger (Studio) and a 400-day memory (relay) | a new PC, a cloned VM, or a changed machine id: a determined person can get a second trial on another identity |
| Flooding the owner | per-address, per-device and total caps; held requests; Telegram only for new ones | many addresses can fill the waiting list (300): an upstream WAF/Turnstile is the next step if it happens |
| Free paid code | payment tick + reference + the owner's own click, enforced by the server | an owner who ticks without checking |
| Telegram secrets | environment only; never stored, logged, returned or audited | — |
| A forged or replayed button | secret token + owner id **and** owner chat + opaque request id + one-way states + 72-hour limit; the relay never takes a code or a key from a button | the owner's own phone being used by someone else |
| Approving by mistake | «سحب الموافقة» until the code is signed | after signing a code exists |
| A shop's typed text | shown as text only, never in an alert | — |

The honest summary: the trial is **limited abuse**, not **no abuse** (14 days of a cash-only till on a PC that can be told apart); paid use is protected by the signature, the device binding and the payment gate.

## 7. When the shop is offline (Al-Store screen)

One status line, never silence: *sending → waiting for the company → activated* / *refused: reason* / *no connection: retrying (next try in …)*. Retries back off (1 min, 5 min, 15 min, 1 h) and a button retries at once. The manual way is always there: copy the device code, send it to the company on **Telegram**, paste the code. The program keeps working in the read, print, export and backup mode while it waits (BIZ-03).

## 8. Audit

Studio (append-only): `request.relay` (id, kind, device, machine prefix), `code.issue`, `request.approve/refuse` (policy or owner, reason, payment reference), `request.delivered`, `key.keep_unlocked`, `relay.save`. Relay (`licence_events`, 90 days): created, issued, refused, delivered, reissued, with no code and no text from the shop. Shop (Al-Store audit): `licence.request`, `licence.auto` (activated by the answer), with the serial.

## 9. What the owner still has to do (nothing here is bought or deployed)

1. On the trusted PC: `python -m licence_studio serve`, create the key (passphrase on paper), copy the **public** key line into the shop program's `licence_keys.txt` before building the installer. Without it the installed program refuses every code.
2. Create the Cloudflare Worker and D1 from `templates/telemetry-relay` (README), set `LICENCE_ADMIN_TOKEN`, and optionally the Telegram secrets; put the Worker address into the shop program (`licence_relay.txt`, a public file like `licence_keys.txt`).
3. Create the Telegram bot (BotFather) and set `TELEGRAM_BOT_TOKEN` / `TELEGRAM_OWNER_CHAT_ID` for the Studio too (the owner's **private** chat with the bot: press Start first). For the buttons: `python -m licence_studio telegram-webhook --make-secret` shows a secret once; put it in the relay with `wrangler secret put TELEGRAM_WEBHOOK_SECRET`. Upgrading an existing database is just running `schema.sql` again (a new table, no `ALTER`). Deploy the relay first: a Studio 1.2.0 on an older relay still works as 1.1 (no buttons).
4. In the Studio: relay address and token, then the policy switch and «افضل مفتوح».
5. Decide the open items: prices, how customers pay, Windows signing, cost ceiling of the free Cloudflare plan.

## 10. Tests

- `templates/telemetry-relay/test/telegram.test.mjs` (19): the buttons: alert keyboard (only when it can work), closed unless fully configured, wrong/missing secret (no D1 query), log cap, other person / group / forwarded press, approve records and keeps waiting, the word «approved» for a trial only and only while it counts, double press, refuse is final, withdrawal, nothing after signing, stale approval judged by the relay, junk input, D1 query count, `states`, schema upgrade by re-running `schema.sql`.
- `apps/licence-studio/tests/test_telegram_buttons.py` (23): the real Worker over HTTP with the Studio: approve, sign, deliver, the shop verifies; locked key waits; refuse closes everywhere, also between the pull and the signature; paid kinds; forged presses never reach the Studio; hard rules; cap; old approval (relay's clock); copy retry, a dead sender's claim, one try per round, private chat only, 6 concurrent senders; an older or ailing relay never stops the round; audit once; webhook set-up; upgrade from 1.1.
- `templates/telemetry-relay/test/licence.test.mjs` (16): request, replay, token, decide, refuse, one trial per machine/device, re-issue, supersede, limits, input and shop-text cleaning, Telegram trouble, the event log, D1 query counts and index use, clean-up, no secret in the template.
- `apps/licence-studio/tests/test_relay_chain.py` (10): the **real Worker** over HTTP with the Studio: automatic trial checked with the public key, one trial per PC, a locked key, paid kinds, owner refusal, caps, relay trouble and retried delivery, the audit holds no secret, the key stays open only as long as the owner chose.
- Al-Store (`tests/test_trial.py`, `test_e2e_browser`): the shop client, the screen states, and the full chain against the real Worker when Node is there.
