# af-atrest v0.2.0 — SQLite at-rest encryption (optional)

**Status:** `implemented` (unit-tested here). **Not** `verified` in a shipped product or **field-verified** for recovery/escrow drills.

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

`cryptography` seals backup archives, vendor escrow, and recovered-key packages.

## Vendor recovery and sync (0.2.0)

All key storage and recovery go through the **vendor server** (escrow worker + owner Key Vault). There is **no** client-side password recovery file.

| Module | Role |
|---|---|
| `af_activation.py` | `activate_encrypted_storage` — mandatory escrow enqueue at activation |
| `af_recovery.py` | `restore_on_new_device` with vendor `recovered-key` package; device transfer key in data dir |
| `af_escrow.py` | `escrow_package` (X25519 sealed box to vendor **public** key), `upload_escrow` |
| `af_sync.py` | Crash-safe outbox for escrow and off-site backup; `flush_sync_queue`, `sync_warning` (ar/en) |
| `af_offsite.py` | Daily sealed-backup upload (**on by default**); business timezone |
| `af_migrate.py` | `migrate_to_encrypted(data_dir)` with safety plaintext backup until verify |
| `af_errors.py` | Bilingual error catalogue (`AtRestError`) |

Vendor private keys live only in `tools/key-vault/` (`make-recovery-package` for new devices). Cloud template: `templates/key-escrow-worker/` (**not deployed**).

## Known gaps (honest)

- **Field drills** on a second clean PC, owner workflow, and worker deploy are not done in the factory.
- **Attachments and exports** (photos, journals on disk, CSV) are **not** encrypted by this module.
- **Windows DPAPI** is still a per-user stand-in on Linux/macOS CI; production Windows builds should map to real DPAPI when wired in the product.
- Off-site backup and escrow require owner-configured worker URL and per-company tokens.

Do not enable `AF_ENCRYPT=1` for a real office until product-specific recovery drills pass.

## Vendor

```bash
python3 scripts/vendor_atrest.py <product>   # → server/afatrest.py
python -m unittest discover -s packages/af-atrest/tests -v
```

Spec: [docs/OFFLINE_SECURITY_AND_RECOVERY.md](../../docs/OFFLINE_SECURITY_AND_RECOVERY.md). Controls: `DATA-02` (advice), `PROT-02` (product policy).
