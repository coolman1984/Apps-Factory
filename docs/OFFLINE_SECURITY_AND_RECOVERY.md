# Offline security and recoverable storage (factory reference)

Template for desktop products that must keep working offline. **Status:** reference spec; optional `packages/af-atrest` is `implemented`, not field-verified.

## Principles

- Suspected tampering or reverse-engineering must **never** delete, corrupt, re-encrypt, or ransom customer data. Treat integrity failures as **recoverable incidents**, not punishment.
- Signed licences use **public keys only** in customer builds; private signing keys stay on the vendor machine.
- When a licence blocks writes, **read, export, and backup** stay available (control `BIZ-03`).
- CI customer-style builds use ephemeral keys and a separate installer identity (`AppChannel=ci-test`); they are **not** commercial releases.

## Opt-in at-rest encryption (`packages/af-atrest`)

| Topic | Behaviour |
|---|---|
| Default | **Off.** Unset `AF_ENCRYPT` → ordinary `sqlite3`, no `atrest.key` |
| Live DB | SQLCipher 4 with a per-data-dir random 32-byte key when `AF_ENCRYPT=1` |
| Backups | ChaCha20-Poly1305 archives; wrapped key in authenticated header only |
| Local wrap | `data/atrest.key` sealed with a per-user secret (Windows DPAPI target; Linux stand-in under `$XDG_CONFIG_HOME/<profile-subdir>`) |
| Plaintext DB | **Refused** when encryption is on (no silent migration) |
| Missing `sqlcipher3` | Process **refuses to start** when encryption is on (no plaintext work file) |
| `AF_ENCRYPT_BACKEND=file` | **Refused** (no whole-file fallback) |

### Known gaps (do not enable for production offices yet)

- **Recovery key** export/import: not implemented
- **Plaintext → encrypted migration**: not implemented
- **Second-PC restore** of sealed backups: header wrap is local-user scoped; another PC cannot unwrap without a planned recovery workflow
- **Attachments and exports** (photos, journals on disk, CSV): not covered by af-atrest

Keep verified plaintext backups until migration and restore drills pass on a second clean machine.

## Planned acceptance drill (not automated in the factory)

1. Stop all writers; take **two** independent plaintext backups; verify checksums and row counts.
2. *(Planned)* Encrypt a **copy** with a product migration command; compare counts and hashes.
3. *(Planned)* Restore on a **second clean PC** with owner recovery material; exercise daily work.
4. Only then switch the live office; retain plaintext backups until a new encrypted backup is restored once on purpose.
5. On any failure, restore plaintext data and leave `AF_ENCRYPT` unset.

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
