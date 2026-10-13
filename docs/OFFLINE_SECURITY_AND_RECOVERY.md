# Offline security and recoverable storage (factory reference)

Template for desktop products that must keep working offline. **Status:** reference spec; optional `packages/af-atrest` is `implemented`, **not field-verified**.

## Principles

- Suspected tampering or reverse-engineering must **never** delete, corrupt, re-encrypt, or ransom customer data. Treat integrity failures as **recoverable incidents**, not punishment.
- Signed licences use **public keys only** in customer builds; private signing keys stay on the vendor machine.
- When a licence blocks writes, **read, export, and backup** stay available (control `BIZ-03`).
- CI customer-style builds use ephemeral keys and a separate installer identity (`AppChannel=ci-test`); they are **not** commercial releases.
- **Escrow private keys** never enter the repository, CI, or the Cloudflare worker. Only sealed blobs and vendor **public** keys in client config.

## Opt-in at-rest encryption (`packages/af-atrest`)

| Topic | Behaviour |
|---|---|
| Default | **Off.** Unset `AF_ENCRYPT` → ordinary `sqlite3`, no `atrest.key` |
| Live DB | SQLCipher 4 with a per-data-dir random 32-byte key when `AF_ENCRYPT=1` |
| Backups | ChaCha20-Poly1305 archives; wrapped key in authenticated header only |
| Local wrap | `data/atrest.key` sealed with a per-user secret (Windows DPAPI target; Linux stand-in under `$XDG_CONFIG_HOME/<profile-subdir>`) |
| Plaintext DB | **Refused** when encryption is on (use `migrate_to_encrypted` first) |
| Missing `sqlcipher3` | Process **refuses to start** when encryption is on (no plaintext work file) |
| `AF_ENCRYPT_BACKEND=file` | **Refused** (no whole-file fallback) |
| Vendor escrow | **Mandatory at activation.** Client seals data key to vendor X25519 **public** key; upload via crash-safe outbox (retries when online) to worker template |
| New device restore | Owner uses `tools/key-vault` to build a **recovered-key package** (decrypt escrow, re-seal to new device transfer public key). `restore_on_new_device` verifies backup and re-wraps under local DPAPI stand-in. **No** client password recovery file |
| Off-site backup | **On by default**; uploads **already-sealed** backup blob via the same outbox; scheduler uses business timezone |
| Offline sync | Persistent outbox in data dir; `sync_warning` (ar/en) when escrow or backup not synced for N days (default 3) |
| Migration | `migrate_to_encrypted`: plaintext safety copy until row-count verify; rollback on failure |

### Remaining gaps (do not treat as production-ready)

- No product has vendored 0.2.0 or run the **acceptance drill** on real office data.
- Worker template is **not deployed**; tokens and R2 lifecycle are owner operations.
- Non-database files remain plaintext unless the product adds its own policy.

Keep verified plaintext backups until migration and restore drills pass on a second clean machine.

## Acceptance drill (factory tests exist; field proof still required)

1. Stop all writers; take **two** independent plaintext backups; verify checksums and row counts.
2. Run `migrate_to_encrypted` on a **copy**; compare counts and hashes.
3. On a **second clean PC**, show `device_transfer_public_hex`; owner runs Key Vault `make-recovery-package`; `restore_on_new_device` with the sealed backup; exercise daily work.
4. Confirm escrow reached the worker (or outbox drained after reconnect).
5. Only then switch the live office; retain plaintext backups until a new encrypted backup is restored once on purpose.
6. On any failure, restore plaintext data and leave `AF_ENCRYPT` unset.

## Commercial runtime (`packages/af-license` `runtime.py`)

- **Distributed builds** without `_release_policy` fail closed: no trusted keys, edits blocked.
- **Upgrade grace** (`UPGRADE_GRACE_DAYS`, default 30): one-time for offices with provably old data upgrading to commercial; not for fresh installs or `ci-test` builds; clock rollback locks edits without consuming grace permanently.

Products wire grace to their primary database (including via vendored `af-atrest` when encryption is on).

## Before commercial handoff

- Private source repo where required; assume prior clones may exist.
- Customer-signed installer (not CI-test `AppId`).
- Offline licence activation, expiry read/export/backup, and negative-role tests.
- Disaster-recovery drill on Windows with real data before advertising encryption or cloud restore.

**Distinction:** tamper hints are not proof of who inspected an offline binary. Local administrators with sufficient access can still observe decrypted runtime data.
