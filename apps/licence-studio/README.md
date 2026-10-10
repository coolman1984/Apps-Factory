# Licence Studio | برنامج الأكواد 🔑

The owner's program that makes **trial and paid codes** for every factory product. A code is 144 characters (24 groups of 6),
signed with Ed25519, bound to one PC's device code, and carries product, edition, start and end day. A product verifies it
offline with the stdlib verifier (`packages/af-license/af_license/codes.py`, vendored by `scripts/vendor_licence.py`).

**Status:** implemented and tested (`tests/test_studio.py`: key lock, issue → verify, other PC refused, agent limits, MCP over a
real subprocess, full chain with Al-Store). Not field-verified yet.

## Run
```bash
pip install -r requirements.txt
python -m licence_studio serve            # opens http://127.0.0.1:8770 (loopback only)
python -m licence_studio doctor           # check this PC
python -m licence_studio verify CODE --product al-store --device XXXXX-XXXXX
```
Data lives in `~/.af-licence-studio` (or `LS_HOME`). The private key is stored **encrypted with the owner's passphrase**, is
unlocked into memory only, and locks itself after 30 minutes. It never enters a repository, CI or a product.

## The three kinds a shop buys
The Issue page has three quick buttons. Each one fills the form, and the days and grace stay editable:
| Button | Edition | Days | Grace | Device |
|---|---|---|---|---|
| «تجربة 14 يوم» | `trial` | 14 | 0 | required |
| «اشتراك شهري» | `standard` | 30 | 3 | optional (bind it) |
| «تفعيل دائم» | `perpetual` | never ends | — | required |
A permanent code needs af-license 0.3.0 in the product. An older product refuses it as `unknown_edition`, so it is never granted by mistake.

## Pages
Issue a code · Codes (search, copy, WhatsApp message, issue the next code) · Requests from shops and agents · Verify · Products · Keys (create, unlock,
export the **public** key for `licence_keys.txt`) · Agent access (tokens, trial policy).

## Shop requests, Telegram buttons and automatic trials (1.2.0)
A shop asks for a trial from its own screen; the owner's phone gets a Telegram message; this program, on the trusted PC, pulls the request through the relay, decides by the policy the owner switched on, signs, and sends the code back; the shop checks it with the public key and switches itself on (no copying). Full chain, threat model and limits: [docs/LICENCE_ACTIVATION.md](../../docs/LICENCE_ACTIVATION.md).
- **Page «طلبات المحلات»:** connect the relay (address + token, stored only in `relay.json` here with owner-only permissions, or `LS_RELAY_URL` / `LS_RELAY_TOKEN`), pull now, switch the policy on, set the daily cap, and «افضل مفتوح» (the key stays in memory for at most 12 hours so trials go out while you are away; locking or restarting ends it).
- **Policy (off until you switch it on):** a trial is automatic only for a PC that never had one (permanent `trial_ledger`), within the day's cap, from a sender that is not flooding, with the key unlocked. The same device asking again gets the same code. Everything else waits for you.
- **Paid kinds never go out alone:** a monthly (30 days + 3 grace) or permanent code needs «الدفع وصل» ticked and a payment reference; the server refuses without them.
- **Telegram** (environment only, never stored): `TELEGRAM_BOT_TOKEN`, `TELEGRAM_OWNER_CHAT_ID`. One message per event: refused, held, locked, old approval.
- **The owner's buttons (1.2.0):** the relay's alert has «✅ موافق» / «❌ رفض». «موافق» makes this program sign **that one trial** on its next round even when the policy is off (key unlocked; one trial per PC and every hard rule still apply; an approval older than 72 hours is not acted on). «رفض» is closed here too, and a click in this program on a request you refused on the phone is refused. For a monthly or permanent request the button records your intent only: you still tick «الدفع وصل» and write the reference here. Whenever a code is signed for a shop's request, **your phone gets a copy of it** (once, retried until Telegram accepts it, never in the audit) for the phone readout when the shop is offline.
- **Set the buttons up:** `python -m licence_studio telegram-webhook --make-secret` (shows the secret once; give it to the relay: `wrangler secret put TELEGRAM_WEBHOOK_SECRET`). Telegram is told to send only button presses, over https, with that secret.
- A round runs every 60 seconds while `serve` runs (`LS_RELAY_EVERY`, 0 = off) and from the button. A failed delivery is retried each round.
- Tests: `tests/test_relay_chain.py` and `tests/test_telegram_buttons.py` run the **real relay Worker** (Node 22.13+) over HTTP; `tests/test_ui_relay.py` clicks the page in a real browser.

## AI agents (MCP)
Add to Claude Code / any MCP client:
```json
{ "mcpServers": { "licence-studio": { "command": "python", "args": ["-m", "licence_studio", "mcp"],
  "cwd": "apps/licence-studio", "env": { "LS_URL": "http://127.0.0.1:8770", "LS_AGENT_TOKEN": "<agent token from the Agent page>" } } } }
```
Tools: `studio_doctor`, `studio_status`, `list_products`, `list_codes`, `get_code`, `verify_code`, `request_code`,
`issue_trial_code`, `list_requests`. Agents **read and request**; issuing trials directly is off by default, capped at 14 days
and a daily limit when the owner turns it on. Paid codes always need the owner. Every action is audited.

## Product side (Al-Store example)
1. Put the public key line from the Keys page in the product's `licence_keys.txt`.
2. The customer opens the product → Licence card shows the **device code** → sends it to you.
3. Issue a 14-day trial for that device → paste the code → product unlocks. After the end day it locks to read/export/backup only.
4. When the customer pays: a monthly code each month («اشتراك شهري»), or one permanent code («تفعيل دائم») for that device.
