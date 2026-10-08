# Hessa ↔ Factory alignment (2026-10-08)

Hessa (`coolman1984/Teachers`, main `5b2fc24`+) is the factory's first full product. This file records, in both directions,
what one has and the other lacks, and what was done about it. Reviewed from the source, not from README claims.

## A. Proven in Hessa → now factory standards
| Hessa pattern | Factory control | Why every product needs it |
|---|---|---|
| Office mesh: every joined PC keeps a full signed history and keeps working alone; admin PC is the authority; 15-minute join window; deterministic IDs; admin decides conflicts | **new tier `office_mesh`**, `MESH-01` | The old `office_server` tier stops every PC when the main one is off; Hessa proves a better model without any cloud |
| The Watch: 16 rules (reversal then smaller receipt, drawer short/over/repeated, drawer left open, attending without paying, discounts, price changes, deletions, earlier attendance changed, after-hours, denied attempts, big expenses, trials, admin changes) reviewed with a note | `WATCH-01` | Owners are not at the desk; money leaks are the first reason they buy |
| Clicks & screens log for administrators, typed values never recorded | `LOG-01` | Forensics without spying on content |
| Dated prices (`feeHistory`): a price change starts on a chosen day, never retroactive | `DATA-07` | Silent retroactive repricing is an anti-pattern already in the constitution |
| "Never block the front desk": record first, flag later | `DATA-08` | A blocked queue costs the customer more than a flagged record |
| Strict CSP, Origin check, Host check (DNS rebinding), proxy headers never count as "this PC", spreadsheet formula neutralisation | `SEC-07` | Local web apps are attacked through the browser |
| Phone helpers sign in with a personal link (never admin); admin password recovery with a vendor-signed one-time code | `IAM-07` | No shared passwords, no vendor backdoor |
| Messages that survive WhatsApp bans: one-by-one wa.me, never bulk automation; official API only with consent and a daily cap | `MSG-01` | Bans kill the customer's number |
| Advisor on the dashboard: ranked "do this now" items, each with a button to the page | `UX-06` | The dashboard tells the user what to do, not only numbers |
| Basic first-version menu: extra pages off until enabled | `UX-07` | A first-sale product must look small and simple |
| Sample centre loaded and removed exactly (prefixed ids) | covered by AGENTS demo rule + `HELP-01` | Customers learn on fake data safely |

## B. Factory standards → applied to Hessa
| Factory standard | Hessa status after 2026-10-08 |
|---|---|
| Signed licence (Ed25519, offline private key, device binding, clock rollback, read/export/backup after expiry) | **Already in Hessa** (`server/license.py`, FS8) — same rules as `af-license`; Hessa keeps its own, stdlib-only |
| Compiled build (`PROT-01`) | **Already** (Nuitka in `tools/build_windows.py`) |
| Help in polished Egyptian Arabic, "Solve a problem" + "Guide me" (`HELP-01..04`) | **Done** (PR on Teachers, 761 texts) |
| No welcome slideshow; daylight + system font (`HELP-05`, ADR-0005) | **Done** (Teachers PR #23) |
| Contact support, self-check, consented support window, safe repairs (`SUP-01..04`, `AI-04`) | **Done** (Teachers PR #22) |
| Hidden diagnostics probe (`DIAG-01..03`) | **Done** in Hessa 1.5.0: `deep_diagnosis` (data, test restore in a temp folder, ports, sync, licence, disk, errors) under the support window |
| Signed update channel with rollback (`REL-02/03`) | Hessa has upgrade safety copies and refuses newer data; the in-app signed updater is **open** (LAUNCH_SCOPE says not a first-pilot dependency) |
| Authenticode (`REL-01`, ADR-0004 stage A) | Stage A: vendor installs; customer guide **to add** to Hessa docs |
| UUIDv7 ids (`ARCH-03`) | Hessa uses random ids + deterministic ids + PC letter on numbers — **equivalent**, kept |
| Org/branch scope (`ARCH-02`) | Single centre by design; becomes a decision only when a multi-branch Hessa is sold |

## B2. Lesson from the first release review
The owner found dashboard figures spilling out of their cards in a picture; every browser test had passed because none measured
layout. New control `UX-08`: a measured layout sweep (Hessa `tests/test_layout_overflow.py`, proven to fail on the old styling).

## C. Review of money and data rules against the constitution
Checked in the source: balances are computed (`center.balances`, `domain.account`), receipts and expenses are append-only with
reversals, generic saves cannot edit money (403), payments are idempotent (`pk<key>`), stock is a merge counter, scoped users are
filtered on the server, the lock order is fixed. Three independent reviews (FS13) already fixed 6 money and 6 security findings with
regression tests. No new rule violation was found in this pass; the open items are the field gates (L2–L6) and the updater.
