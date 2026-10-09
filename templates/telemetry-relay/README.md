# Telemetry relay (Cloudflare Worker + D1)

A mailbox between installed products and the Control Center. It is used when the Control Center is not reachable from
customers' networks, which is the usual case (decision 4 in the parity plan).

```
product (af-telemetry) --POST /ingest--> relay (D1) <--GET /pull, POST /ack-- Control Center (pull-relay, every 5 min)
```

## What the relay does and does not do

Protocol 2 (Apps-Factory 0.9.0): products send `Authorization: Bearer <install token>` over HTTPS, `X-AF-Install`
(UUID), optional `X-AF-Sent-At` (their clock) and a gzip body of at most 512 KB. There is no signature, nonce or
5-minute window any more. Every event carries a unique id and the Control Center stores ids with `INSERT OR IGNORE`, so a
replayed batch only counts duplicates. Every answer carries `server_time`, so a PC with a wrong clock corrects itself
instead of being refused forever.

- **Strangers are refused cheaply.** The Control Center pushes the list of registered installs (`POST /installs`: id and
  sha256 of the token, never the token). A known install with a wrong token gets 401 after one lookup: no count and no
  write.
- **Per-install caps** for registered installs: `RATE_PER_HOUR` (120), `MAX_ROWS_PER_INSTALL` (2000) and
  `MAX_BYTES_PER_INSTALL` (20 MB). When full, the relay answers 503 and the product keeps the batch in its outbox. The
  check reads only that install's rows through the `(install_id, received_at)` index. Nothing counts the whole table.
- **New PCs lose nothing.** A PC that nobody registered yet may park small batches (64 KB) in a shared pending area.
  The limits are `PENDING_MAX_ROWS` (200) in total, `PENDING_PER_INSTALL` (5) and `PENDING_PER_SOURCE` (10 per network
  address per day; the address is stored only as a daily-salted hash). The Control Center shows such PCs under
  «أجهزة جديدة مستنية موافقتك», and approving one replays its batches. `PENDING_MAX_ROWS = "0"` turns the area off.
- It stores the batch bytes **exactly** (base64) and never opens a batch. The Control Center checks the token, the
  install and every privacy rule again when it pulls. It deletes a batch (`/ack`) only after the batch was stored,
  parked as pending, or kept in its own quarantine. A batch that failed for a temporary reason stays on the relay.
- `GET /pull`, `POST /ack` and `POST /installs` need `Authorization: Bearer <RELAY_PULL_TOKEN>`, compared in constant
  time. With no token set, they are closed.
- A daily cron deletes anything older than `KEEP_DAYS`, which is capped at 14.

### D1 Free-plan limits (checked by the tests)

| Limit (D1 Free) | What the relay does |
|---|---|
| 50 queries per Worker invocation | `/ingest`: at most 3. `/ack`: one `DELETE … WHERE id IN (…)` per 100 ids, so at most 5. `/installs`: one upsert per 25 installs, at most 1000 installs per call, so at most 42. Clean-up: 1. |
| 100 bound parameters per query | `/ack`: 100 per statement. `/installs`: 75 per statement. |
| 5 million rows read per day | No whole-table `COUNT(*)`. Ingest reads only the sender's own rows (at most `MAX_ROWS_PER_INSTALL`) or the small pending area (at most `PENDING_MAX_ROWS`). |
| 100,000 rows written per day | One row per batch. The install list is pushed only when it changes, or once a day. |

## Deploy

```bash
npm i -g wrangler                     # or npx wrangler
wrangler d1 create af-telemetry-relay # copy the id into wrangler.toml (database_id)
wrangler d1 execute af-telemetry-relay --remote --file=schema.sql
wrangler secret put RELAY_PULL_TOKEN  # long random value; same value as CC_RELAY_TOKEN on the Control Center
wrangler deploy
```

On the Control Center, set `CC_RELAY_URL=https://<worker>.workers.dev` and `CC_RELAY_TOKEN=<same token>`.
`python -m control_center serve` then pulls every `CC_RELAY_EVERY` seconds (default 300). You can also run
`python -m control_center pull-relay` once, or use the dashboard button «سحب الأحداث من الوسيط».

Products send to `https://<worker>.workers.dev/ingest`.

**Upgrading from 0.8:** the 0.8 table `batches` is replaced by `inbox` and `installs` (run `schema.sql` again). Pull
everything once with the old Control Center first. After that, the old table can be dropped.

**Never commit secrets:** `wrangler.toml` only has placeholders, and the test checks this.

## Cost and limits

«⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين»

The Workers and D1 free-plan limits (requests per day, rows read/written, storage) versus real fleet traffic are not
measured yet. Nothing is bought; see `docs/OPEN_POINTS.md`.

Rough load per installation: one batch per hour, plus one for each urgent error. That is about 24–50 requests a day per PC.

## Notes

- **Compression:** products send `Content-Encoding: gzip`, and the Worker reads the raw body. The Worker refuses a
  body that does not start with the gzip magic bytes (400). If a proxy in front ever decompresses request bodies,
  batches are refused, not stored wrongly. Check this on the first real deployment.
- **Planned (design only):** the Telegram webhook (customer bot and owner `/status`/`/incidents`, owner chat id only) and the signed `/latest` update endpoint. See
  `docs/CUSTOMER_PATCH_PIPELINE.md`.

## Test

The tests need Node 22 or newer. They use a D1 shim over `node:sqlite`.

```bash
node --experimental-sqlite --test test/relay.test.mjs
```
