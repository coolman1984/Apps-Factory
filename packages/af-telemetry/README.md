# af-telemetry v0.1.0: ids-and-counts events, problem reports, offline outbox

**Status:** `implemented`. It is unit-tested here; no product uses it yet. Standard: [docs/PRIVACY_TELEMETRY_STANDARD.md](../../docs/PRIVACY_TELEMETRY_STANDARD.md).

Controls: `PRIV-03`, `PRIV-04`, `PRIV-05` (optional), `PRIV-06`, `TEL-01`…`TEL-03`, `FB-01`.

Copy it into a product with:

```
python scripts/vendor_telemetry.py <repo>
```

This writes `server/aftelemetry.py`, `server/aftelemetry_events.json`, `<js>/vendor/af-telemetry.js` and `<css>/af-telemetry.css`.

| Piece | What |
|---|---|
| `events.json` | The taxonomy: 31 event types, their consent level (install / person / feedback), priority, hourly merge keys and the **only** fields each may carry. It also holds the never-collect list, the contact choices and the diagnostics allowlist. |
| `Telemetry.emit()` | The single gate: taxonomy check, value guards (machine IDs, numbers, booleans), consent, pseudonym, hourly merge, then the bounded outbox. |
| `capture(exc)` | `err.server` with the exception type, a fingerprint and `module:function`. The message is never sent. |
| `preview()` / `feedback()` | Problem reports: redacted, fully previewed, sent only when the digest matches, and allowed without consent. |
| `from_browser()` | Accepts the browser's batch for its own types only, with the person taken from the session. |
| `send_once()` | Sends a gzip batch of at most 256 KB over HTTPS with the install token (`Authorization: Bearer`, `X-AF-Install`, `X-AF-Sent-At`; protocol 2 since 0.2.0, no HMAC/nonce/time window). The answer's `server_time` corrects this PC's clock for later events (`clock_offset`). A failed send retries after 1 minute, then up to 6 hours. A batch the receiver refuses as bad (400/413/422), or events refused `max_tries` (12) times, go to the `dead` table (`dead_letters()`), so nothing is retried forever. No network at all only waits. |
| `new_identity()` | `(install_id, install_token)` for a PC that was not registered first. The Control Center keeps its batches as a «new PC» until the owner approves it. |
| `purge_subject()` / `on_consent_change()` | Run on decline or withdrawal. |
| `pending()` / `recent_sent()` | Feed the optional «ماذا أُرسل؟» viewer. |
| `af-telemetry.js` | `track()` batches to the product server; a window error hook (file:line only); the report dialog with preview. |

```bash
python -m unittest discover -s tests -v
node --test tests/core.test.mjs
```
