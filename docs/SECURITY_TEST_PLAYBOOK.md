> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Mandatory adversarial test stories

These are examples of tests to implement per actual attack surface. They do **not** assert that tests or security code have been executed inside Apps-Factory.

| Threat | How to verify safely in a synthetic test environment | Acceptable outcome |
|---|---|---|
| Hardcoded credentials | Scan packaged production UI/server; attempt demo credentials and seed endpoints | Refused; no demo credential in build |
| Privilege escalation | Operator crafts direct API admin request or edits role field in payload | Server 403 and no state change; audit denial |
| IDOR/BOLA | User A changes user/project/customer ID to B; tries attachment and export | No data returned, including search/aggregates |
| Cross-tenant | Tenant A calls records, feeds, files, jobs and export of tenant B | No reads/writes/leakage; tests across subsystems |
| Billing spoof | Modify client entitlement state, replay/forge webhook, reorder events | No paid elevation; idempotent verified backend reconciliation |
| Offline licence spoof | Tamper licence claims, signature, edition, clock and device | Modified claims invalid; understandable recovery, customer data preserved |
| Replay/race | Submit duplicate payment/import twice concurrently | Exactly once (or safe reconciliation) with consistent reports |
| Audit bypass | Reversal, cancellation and data export through alternative API paths | Actor and reason logged; private details redacted |
| Insecure support | Vendor tries access before approval, after revocation, across tenant | No access, visible audit |
| Backup failure | Snapshot during writes, corrupt snapshot, restore on clean test machine | Integrity verified; failed restore never silently accepted |
| Migration / upgrade | Upgrade old data then simulated failure and rollback of binaries | Existing records and identities maintained, no dangerous downgrade |
| Secrets and source | Scan public commits, CI artifacts, logs and screenshots | No production secrets or live customer data |
| Agent prompt injection | Retrieved doc demands privileges/upload secrets/execute shell; agent attempts tool call | Tool authorization and human approval prevent action |
| Usability | Keyboard-only, Arabic RTL, narrow phone, slow/no network, expired access | Clear recoverable states and accessible focus |
| Offline revocation (sync) | Revoke a user, keep their phone offline, record changes, reconnect | Hub quarantines post-revocation changes; admin and author see why |
| Forged sync change | Edit envelope `org_id`/`actor_id`/`branch_id` or replay another device's `change_id` | Rejected: hub derives actor/org from the device credential, idempotent on replay |
| Clock tampering (sync) | Set device clock days back/forward before creating changes | Ordering by HLC/hub sequence; author time flagged, no grace extension |
| Lost device | Revoke an enrolled phone/PC, then try to sync from it | Refused; device purge runbook followed |
| Owner lockout | One owner tries to remove/demote the other owner alone | Refused without quorum; all owners notified |

Use OWASP ASVS v5, NIST SSDF final, OWASP API Security 2023 and agentic AI 2025 as applicable. Always run in a dedicated test tenant/fixture; do not attack live customer systems.
