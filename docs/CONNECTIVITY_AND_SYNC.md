# Connectivity tiers and offline-first cloud sync

Decision record: [ADR-0001](decisions/ADR-0001-architecture-and-connectivity-tiers.md). Controls: `ARCH-*`, `SYNC-*`, `MOB-*`, `SITE-*`, `OWN-*`, `BIZ-06`, `OPS-06` in `factory/controls.json`.
**Status:** specification. No sync engine exists in this repository yet.

## 1. Tiers as the customer experiences them
| Tier | Main PC off | Internet off | Phones | Branches | Owners abroad |
|---|---|---|---|---|---|
| `standalone` | app off | works | no | no | no |
| `office_server` | other PCs **cannot write** (stated in contract) | office works | only inside office Wi-Fi, online, no offline install | no | no |
| `office_mesh` (proven in Hessa) | other PCs keep working on their full copy | every PC works alone and merges on reconnect | only inside office Wi-Fi, online | no | no |
| `cloud_sync` | other devices keep working | every device works alone and queues | installable PWA, declared offline actions | yes | live view + actions by permission |
| `cloud_only` | n/a | app unavailable | online PWA | yes | yes |

A customer moves up a tier by configuration + device enrollment. `ARCH-02/03` make that possible without rewriting data.

## 2. Topology (v1)
```text
 [PC A replica+outbox]   [PC B replica+outbox]   [Phone PWA scoped replica]
          \                     |                        /
           \______ HTTPS batches, resumable, idempotent ______/
                               |
                    [Cloud hub = authority]
          tenant isolation · ingest validation · permissions at author time
          sequence numbers · conflict log · backups · owner dashboard
```
- **Star, not mesh:** the cloud hub is the single source of truth; devices never write to each other in v1. This removes split-brain.
- The "main PC" is just the fullest replica (printer, local backup, full export). It is **not** required for others to work.
- **v2 option (not v1):** main PC as a store-and-forward LAN relay when the internet is down. Hub stays authority; relay cannot confirm hub-confirmed actions (§3 class C).

## 3. Every synced entity must be classified (`SYNC-02`)
| Class | Examples | Offline rule | Merge rule |
|---|---|---|---|
| **A. Append-only event** | receipt issued, payment, reversal, attendance mark, trip log | always allowed | union; dedupe by `change_id`; corrections are new reversal events |
| **B. Field-mergeable record** | student/customer profile, notes, contact data | allowed | per-field last-writer-wins by HLC; losing value kept in audit and shown in conflict log |
| **C. Hub-confirmed** | capacity/seat limits, stock below zero, legal/tax numbers, cash-shift close, role/permission/plan changes, hard deletes, data-region change | blocked, **or** recorded as *pending confirmation* that may be rejected | hub decides; rejection creates visible compensating task, never silent |
| **D. Derived** | balances, totals, dashboards, reports | computed locally | never synced as truth; recomputed from A/B |

Money: balances are always class D derived from class A ledger events. No offline edit of a closed shift. Internal document numbers are device-safe (`<prefix>-<device code>-<sequence>`); any legally regulated number (e.g. tax e-receipt) is class C and needs legal review — **UNKNOWN** until reviewed per market.

## 4. Change envelope (wire contract)
Draft contract: [`factory/contracts/sync-envelope.schema.json`](../factory/contracts/sync-envelope.schema.json). Every change carries: `change_id` (UUIDv7, idempotency), `org_id`, `branch_id`, `device_id`, `actor_id`, `entity`, `entity_id`, `op`, `class`, `hlc` (hybrid logical clock), `author_time` (device claim, untrusted), `schema_version`, `protocol_version`, `base_version` for class B, and `payload`. The hub adds `hub_seq` and `received_at`.
- Ordering uses HLC / hub sequence, **never** the device wall clock alone (`SYNC-04`). Author time is accepted only inside `[device last sync, received_at]`; outside → flagged.
- Local write and outbox row are written in **one SQLite transaction** (transactional outbox). Power cut at any point leaves either both or neither (`OPS-06`).
- Delivery is at-least-once; apply is exactly-once by `change_id` (`SYNC-03`). Batches resume from the last acknowledged change.

## 5. Security while offline
- **Bounded offline authority (`SYNC-05`):** each device holds a signed snapshot of its user's permissions + entitlement valid for `offline_grace_days`. After that it becomes read/export-only until it syncs. Revoking a user takes effect at the device's next sync; that residual window is documented in the contract.
- **Hub re-authorizes every change** against permissions effective at author time. Rejected changes go to a **quarantine** queue visible to admins and the author. Never dropped silently.
- **Device lifecycle (`SYNC-06`):** enrollment by one-time QR/code approved by an admin; per-device key; revoke; lost device runbook. Desktop local DB encrypted at rest where feasible. Browser storage is **not** strong protection against someone holding the unlocked phone → minimise what phones store.
- **Scoped replication (`SYNC-07`):** a device receives only its org/branch/role scope; restricted fields never leave the hub. Role change → re-scope and purge on device.
- Tenant isolation and hosted operations controls (`TEN-01/02`) apply because the hub is multi-tenant.

## 6. Versions, deletions, backups
- **Version skew (`SYNC-08`):** hub accepts protocol N and N-1; older clients go read-only with an "update" message. Event upcasters convert old payloads. Mixed-version fleets are tested.
- **Deletes (`SYNC-10`):** tombstones; legal erasure is a hub command that offline devices execute on reconnect; hub tracks replicas still holding erased data.
- **Replicas are not backups (`SYNC-11`):** a bad delete syncs everywhere. Hub point-in-time backups + scheduled export + main-PC local backup. After a hub restore the hub bumps an **epoch**; devices on an older epoch upload their outbox to quarantine for review, then re-bootstrap, so restored-away data is not resurrected.
- **Exit right:** each site can export its full scope locally even if the vendor/hub is gone (constitution §8).

## 7. Mobile PWA realities (`MOB-*`)
- Needs a trusted **HTTPS** origin for install + offline (service worker). Office LAN IPs do not provide that → mobile requires a cloud tier.
- iOS/iPadOS: web push only after "Add to Home Screen"; no Background Sync API; storage eviction rules differ for non-installed sites → sync when the app is open, show unsynced count, request persistent storage, warn before logout.
- No WebUSB/Web Bluetooth on Safari → receipt printing stays on a PC or uses a print-via-hub job.
- Camera barcode/QR: `BarcodeDetector` is not universal → bundled fallback library.
- v1 mobile scope recommendation: owner dashboard (online, read) + **capture-only** offline actions declared in `connectivity.mobile_offline_actions`; the hub re-validates.

## 8. Sync engine spike (decide with evidence, `PRO`/ADR rule)
Candidates to evaluate in a 2-week spike against Hessa's real entities: **own outbox/event protocol** (FastAPI + SQLite + PostgreSQL), PowerSync, ElectricSQL, CouchDB/PouchDB, Replicache/Zero, cr-sqlite, libSQL embedded replicas.
Score each on: Python + browser support, offline **writes** (not only reads), conflict control per class, self-hosting and licence terms (verify current), Arabic/RTL irrelevance (UI-independent), maturity/maintenance, cost per tenant, migration/exit path, and the §9 test suite. Record result as ADR-0003. Licence/maintenance claims must be checked on the vendor's current pages with dates.

## 9. Mandatory sync test suite (`SYNC-12`)
Deterministic simulation in CI, plus one field drill:
1. Two devices offline edit the same class-B field → deterministic winner, loser in audit.
2. Same change delivered 3× and out of order → applied once.
3. Kill process mid-batch and mid-transaction → no loss, no duplicate.
4. Device clock 3 days wrong → ordering correct, flag raised.
5. User revoked while device offline → post-revocation changes quarantined.
6. Class-C capacity oversold by two offline devices → one rejected with visible compensation.
7. Client N-2 connects → read-only + update prompt, no corruption.
8. Hub restored from backup → epoch bump, no resurrection.
9. Legal erasure while a phone is offline → purged on reconnect.
10. 30 days offline device exceeds grace → read/export only.
11. Upgrade a customer from `office_server` to `cloud_sync` → all records keep IDs and history.
12. Power cut on the main PC during sync and during backup → consistent.

## 10. Multiple owners and branches (`OWN-*`, `SITE-*`)
- `owner` is a protected role, ≥1 per org. Adding/removing/demoting an owner, transferring billing, deleting the org or changing data region need **quorum** of owners (rule chosen by the customer at setup) or a documented vendor dispute process. No single partner can lock another out.
- Every owner sees the audit trail of permission, money and admin changes; full export by any owner is allowed (data rights) and notified to the other owners.
- Branch scope on records; branch managers see their branch; cross-branch dashboards show **per-branch freshness** ("last synced 2h ago") so nobody acts on stale numbers.

## 11. Cost and honesty
- Cloud sync has a recurring cost (hosting, storage, bandwidth, backups, monitoring). Measure cost per tenant before pricing (`SYNC-14`). Free hosting tiers may pause or cap projects; never base a paid promise on them.
- Data leaving the premises needs privacy/transfer review and a declared hosting region (`SYNC-13`).
- Power cuts and mobile-data quotas are normal in the first market: compact delta batches, attachments on Wi-Fi by default, UPS recommendation for the main PC.
