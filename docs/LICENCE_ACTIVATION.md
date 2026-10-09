# Licence activation chain: request → Telegram → policy → code → the shop switches itself on

Reference spec (not a living doc: rules are in [RULES.md](../RULES.md) LIC-01 and BIZ-03, parts in [PARTS.md](../PARTS.md)). Written for Al-Store; any product with a device-bound code can use it.

**Owner decisions behind it** ([DECISIONS.md](../DECISIONS.md)): the three kinds of code (14-day trial, monthly, permanent); **Telegram is the owner's notification channel, not WhatsApp**; the private signing key lives only on the owner's trusted PC; automatic issuing follows a trial policy the owner switches on; subscriptions and permanent activation need confirmed payment and the owner's own approval.

**Status:** `implemented` and tested end to end over real HTTP (relay Worker + Licence Studio + codes). **Not deployed.** Not field-verified. What the owner still has to do is in section 9.

## 1. The chain

```
 shop PC (Al-Store)                relay (Cloudflare Worker + D1)            owner's trusted PC
 ─────────────────                 ───────────────────────────               ──────────────────
 «اطلب تجربة 14 يوم»  ──POST /licence/request──►  row "pending"  ──Telegram──►  owner's phone: "طلب جديد"
 (device code, machine tag,                        (no signing key)
  nonce — no secret)                                     ▲   │
                                              GET /licence/pending │ POST /licence/decide
                                                          │   ▼
                                                  Licence Studio pulls, applies the policy,
                                                  signs with the key held in its memory only
 shop polls  ◄──GET /licence/status (poll token)──  row "issued" + code
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
| A shop's typed text | shown as text only, never in an alert | — |

The honest summary: the trial is **limited abuse**, not **no abuse** (14 days of a cash-only till on a PC that can be told apart); paid use is protected by the signature, the device binding and the payment gate.

## 7. When the shop is offline (Al-Store screen)

One status line, never silence: *sending → waiting for the company → activated* / *refused: reason* / *no connection: retrying (next try in …)*. Retries back off (1 min, 5 min, 15 min, 1 h) and a button retries at once. The manual way is always there: copy the device code, send it to the company on **Telegram**, paste the code. The program keeps working in the read, print, export and backup mode while it waits (BIZ-03).

## 8. Audit

Studio (append-only): `request.relay` (id, kind, device, machine prefix), `code.issue`, `request.approve/refuse` (policy or owner, reason, payment reference), `request.delivered`, `key.keep_unlocked`, `relay.save`. Relay (`licence_events`, 90 days): created, issued, refused, delivered, reissued, with no code and no text from the shop. Shop (Al-Store audit): `licence.request`, `licence.auto` (activated by the answer), with the serial.

## 9. What the owner still has to do (nothing here is bought or deployed)

1. On the trusted PC: `python -m licence_studio serve`, create the key (passphrase on paper), copy the **public** key line into the shop program's `licence_keys.txt` before building the installer. Without it the installed program refuses every code.
2. Create the Cloudflare Worker and D1 from `templates/telemetry-relay` (README), set `LICENCE_ADMIN_TOKEN`, and optionally the Telegram secrets; put the Worker address into the shop program (`licence_relay.txt`, a public file like `licence_keys.txt`).
3. Create the Telegram bot (BotFather) and set `TELEGRAM_BOT_TOKEN` / `TELEGRAM_OWNER_CHAT_ID` for the Studio too.
4. In the Studio: relay address and token, then the policy switch and «افضل مفتوح».
5. Decide the open items: prices, how customers pay, Windows signing, cost ceiling of the free Cloudflare plan.

## 10. Tests

- `templates/telemetry-relay/test/licence.test.mjs` (16): request, replay, token, decide, refuse, one trial per machine/device, re-issue, supersede, limits, input and shop-text cleaning, Telegram trouble, the event log, D1 query counts and index use, clean-up, no secret in the template.
- `apps/licence-studio/tests/test_relay_chain.py` (10): the **real Worker** over HTTP with the Studio: automatic trial checked with the public key, one trial per PC, a locked key, paid kinds, owner refusal, caps, relay trouble and retried delivery, the audit holds no secret, the key stays open only as long as the owner chose.
- Al-Store (`tests/test_trial.py`, `test_e2e_browser`): the shop client, the screen states, and the full chain against the real Worker when Node is there.
