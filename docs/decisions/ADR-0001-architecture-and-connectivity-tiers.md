# ADR-0001 • Modular monolith, default stack and connectivity tiers

- **Date:** 2026-10-08
- **Status:** ACCEPTED by owner as the factory default (session decision, 2026-10-08). Library-level picks marked *spike* below stay **pending evidence**.
- **Scope:** every new product manifest using `schema_version` 1.1. Existing products migrate only through `docs/ADOPTION_PLAN.md`.

## Context
The owner's apps (Teachers/Hessa, Yousef-Transportation, rest-house management, HR-System, Business-Template, 3D-Modeling) repeat the same capabilities in different copies: login/permissions (3 diverging copies), device sync (3 similar engines), backup (3 apps), a byte-identical signing file, and 3 storage engines. The owner wants a "Meccano" factory: small independent pieces with one standard plug, and **commercial tiers** from one PC up to multi-branch, multi-owner, offline-capable cloud sync with phones.

## Decision 1 — Modular monolith
One deployable program per product (customer sees one app), built from modules with versioned contracts. No microservices, no per-module database or server.
- A module owns its tables; other modules call its contract, never its tables (`ARCH-01`).
- Every record carries `org_id` (+ `branch_id` where relevant) **from the first schema**, even single-PC editions (`ARCH-02`).
- Every synced-capable record uses a globally unique client-generated ID (UUIDv7/ULID); human document numbers are device-safe (`ARCH-03`). This makes tier upgrades a configuration change, not a data rewrite.

## Decision 2 — Default stack (override only with recorded reason)
| Layer | Default | Status |
|---|---|---|
| Business logic / server | Python 3.12 + FastAPI | default for new products; legacy servers stay |
| UI | HTML + CSS tokens + TypeScript | default |
| Shared UI pieces | Web Components; Lit **or** a ready Lit-based kit (e.g. Web Awesome) | *spike*: RTL, accessibility, Arabic typography on 4 pieces in Hessa |
| Design identity | CSS custom-property tokens, framework-independent | default (survives any UI library change) |
| Local database | SQLite (WAL, single writer process) | default |
| Cloud database | PostgreSQL | when tier needs cloud |
| Tests | pytest, Playwright | default |
| Windows delivery | PyInstaller + installer + Authenticode signing | default for desktop/office tiers |
| Mobile | Installable PWA (no app-store fees) | `mobile_pwa` client, needs HTTPS origin |
| Sync engine | own outbox/event protocol **vs** evaluated engine | *spike* (see `docs/CONNECTIVITY_AND_SYNC.md` §8) |
| Licence signatures | vetted crypto library (Ed25519), not hand-rolled | must replace/verify the current dependency-free signing file before commercial use |

## Decision 3 — Four connectivity tiers (sold as plans)
| Tier (`connectivity.tier`) | Who writes when the main PC is off | Internet needed | Typical buyer |
|---|---|---|---|
| `standalone` | n/a (one PC) | no | single desk |
| `office_server` | nobody — others wait (by design) | no | one office, several PCs |
| `cloud_sync` (premium) | **every device keeps working offline**, queues changes, syncs via cloud hub | only to sync | branches, owners away from the shop, phones |
| `cloud_only` | n/a, browser to hosted service | yes | pure SaaS |

Rules enforced by `scripts/factory.py`:
- `desktop` → `standalone | cloud_sync`; `lan` → `office_server | cloud_sync`; `saas` → `cloud_only | cloud_sync`.
- `mobile_pwa` client and `sites: multi` require a cloud tier (PWA offline needs a trusted HTTPS origin; office IPs have none).
- `cloud_sync` requires `offline_grace_days` (bounded offline authority) and `data.residency`; it activates `sync` **and** `saas` controls (the hub is a hosted multi-tenant service).

## Decision 4 — Hybrid factory product
Mechano libraries **plus** an optional ready base app (shell, login, users, roles, settings, backup, licence, sync status). The base app is **extracted from Hessa after its pilot works**, not designed in a vacuum. A capability becomes shared only after two products consume it with cross-product tests (constitution §18).

## Consequences
- Upgrading a customer from `office_server` to `cloud_sync` must not require re-keying or rewriting records (proved by a migration test in the pilot).
- Offline-capable mobile means some validation also exists in TypeScript. Mitigation: mobile offline is **capture-only** for declared actions; the hub re-validates everything; shared rule vectors run against both implementations.
- Cloud tier has recurring hosting cost; it is a paid tier. "Free" applies to app-store fees and open-source tooling, not to hosting.
- Personal data leaving the premises (cloud tiers) triggers privacy/transfer legal review before any pilot (Egypt Law 151/2020 + Executive Regulations; children's data in tutoring centres needs explicit review).

## Open owner decisions (not decided here)
1. Cloud provider, hosting region and monthly budget ceiling per customer.
2. Price of each tier.
3. Which mobile actions work offline in v1.
4. Multi-owner rule: quorum (e.g. 2 of N) vs vendor-mediated dispute process.
5. Sync engine choice after the spike.
