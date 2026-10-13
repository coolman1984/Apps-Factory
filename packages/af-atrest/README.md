# af-atrest v0.1.0 — SQLite at-rest encryption (optional)

**Status:** `implemented` (unit-tested here). **Not** `verified` in a shipped product or field-accepted.

Generic SQLCipher 4 database encryption and ChaCha20-Poly1305 backup archives for offline desktop products. **Off by default** (`AF_ENCRYPT` unset or not `1`).

## Feature flag

| Variable | Meaning |
|---|---|
| `AF_ENCRYPT=1` | Enable SQLCipher live databases and sealed backups |
| `AF_ENCRYPT_BACKEND` | Only `sqlcipher` (or unset). Value `file` is **refused** (no plaintext fallback) |
| `AF_DPAPI_DIR` | Override directory for the DPAPI stand-in secret (tests) |
| `AF_ATREST_PREFIX` | Override env prefix (default `AF`). Example: `MYAPP` → `MYAPP_ENCRYPT` |
| `AF_ATREST_PROFILE_SUBDIR` | Profile subfolder under `XDG_CONFIG_HOME` (default `apps-factory`) |

`sqlcipher3` (`pip install sqlcipher3-binary`) is required only when encryption is on. With the flag off, the module never imports `sqlcipher3`.

`cryptography` seals backup archives and the wrapped per-data-dir key when encryption is on.

## Known gaps (honest)

Ported from product hardening notes; **not implemented** in this package:

- No owner **recovery key** export or import
- No **plaintext → encrypted migration** command (enabling the flag refuses existing plaintext SQLite files)
- **Second-PC restore** of sealed backups fails when the wrap key differs (same user profile on one PC only)
- Non-database files (photos, journals on disk, exports) are **not** encrypted by this module

Do not enable `AF_ENCRYPT=1` for a real office until recovery, migration, and restore drills exist in the product.

## Vendor

```bash
python3 scripts/vendor_atrest.py <product>   # → server/afatrest.py
python3 -m unittest discover -s packages/af-atrest/tests -v
```

Spec: [docs/OFFLINE_SECURITY_AND_RECOVERY.md](../../docs/OFFLINE_SECURITY_AND_RECOVERY.md). Controls: `DATA-02` (advice), `PROT-02` (product policy).
