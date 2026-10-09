# Telemetry relay (Cloudflare Worker + D1)

A mailbox between installed products and the Control Center. It is used when the Control Center is not reachable from
customers' networks, which is the usual case (decision 4 in the parity plan).

```
product (af-telemetry) --POST /ingest--> relay (D1) <--GET /pull, POST /ack-- Control Center (pull-relay, every 5 min)
```

## What the relay does and does not do

- It checks the shape of the headers (`X-AF-Install` UUID, `X-AF-Timestamp` within 5 minutes, `X-AF-Nonce`,
  `X-AF-Signature`) and that the body is gzip and at most 512 KB.
- It enforces a per-install rate limit (`RATE_PER_HOUR`, default 120), a total-row cap (`MAX_ROWS`; when full it answers
  503 and the product keeps the batch in its outbox), and a UNIQUE (install, nonce).
- An optional shared `RELAY_INGEST_KEY` (header `X-AF-Relay-Key`) blocks casual noise.
- It stores the batch bytes **exactly** (base64), so the Control Center can verify the signature later.
- It **never opens a batch and holds no install secrets.** The Control Center verifies every signature (HMAC keyed with
  sha256 of the install token), every nonce and every privacy rule again when it pulls. Anything forged dies there.
- `GET /pull` and `POST /ack` need `Authorization: Bearer <RELAY_PULL_TOKEN>`, compared in constant time. With no token
  set, they are closed.
- A daily cron deletes anything older than `KEEP_DAYS`, which is capped at 14.

## Deploy

```bash
npm i -g wrangler                     # or npx wrangler
wrangler d1 create af-telemetry-relay # copy the id into wrangler.toml (database_id)
wrangler d1 execute af-telemetry-relay --remote --file=schema.sql
wrangler secret put RELAY_PULL_TOKEN  # long random value; same value as CC_RELAY_TOKEN on the Control Center
wrangler secret put RELAY_INGEST_KEY  # optional
wrangler deploy
```

On the Control Center, set `CC_RELAY_URL=https://<worker>.workers.dev` and `CC_RELAY_TOKEN=<same token>`.
`python -m control_center serve` then pulls every `CC_RELAY_EVERY` seconds (default 300). You can also run
`python -m control_center pull-relay` once, or use the dashboard button «سحب الأحداث من الوسيط».

Products send to `https://<worker>.workers.dev/ingest`.

**Never commit secrets:** `wrangler.toml` only has placeholders, and the test checks this.

## Cost and limits

«⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين»

The Workers and D1 free-plan limits (requests per day, rows read/written, storage) versus real fleet traffic are not
measured yet. Nothing is bought; see `docs/OPEN_POINTS.md`.

Rough load per installation: one batch per hour, plus one for each urgent error. That is about 24–50 requests a day per PC.

## Notes

- **Compression:** the signature covers the gzip bytes. Products send `Content-Encoding: gzip`, and the Worker reads the
  raw body.
  - If a proxy in front ever decompresses request bodies, the Control Center will refuse the batches (bad signature) and
    nothing wrong is stored.
  - Check this on the first real deployment.
- **Planned (design only):** the customer Telegram bot webhook and the signed `/latest` update endpoint. See
  `docs/CUSTOMER_PATCH_PIPELINE.md`.

## Test

The tests need Node 22 or newer. They use a D1 shim over `node:sqlite`.

```bash
node --experimental-sqlite --test test/relay.test.mjs
```
