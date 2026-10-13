# Key escrow worker (template only)

**Not deployed.** Cloudflare Worker sketch for af-atrest escrow packages and optional encrypted backup blobs.

- **D1:** `escrow_packages` table (sealed data keys only; vendor private key stays offline in `tools/key-vault/`).
- **R2:** `BACKUPS` binding for already-sealed backup archives from the desktop product.
- **Auth:** `X-AF-Company-Token` per company (store `sha256(token)` in D1 via `POST /companies` with admin bearer).
- **Limits:** 64 KiB escrow JSON, 50 MiB backup body (configurable vars).

## Free tier notes

- D1 free: 5M rows read/day; keep escrow rows small; prune old backups in R2 with lifecycle rules.
- R2 free: 10 GB-month storage; size limits enforced in worker.
- Worker free: 100k requests/day — enough for daily backup per office if scheduled once per day.

## Local tests

```bash
node --experimental-sqlite --test test/worker.test.mjs
```

Replace `PLACEHOLDER` values in `wrangler.toml` before any real deploy. **Never** commit company tokens or private keys.
