# Adoption strategy: use the factory without breaking existing products

## What we already have
- [Business-Template](https://github.com/coolman1984/Business-Template): existing generic platform (tenancy, role permissions, audit, commands, orders/inventory/accounting/service engines, customer recipes); **integrate, don't clone**.
- [Perfect-Project-Template](https://github.com/coolman1984/Perfect-Project-Template): proven design of reusable Excel adaptation and offline packaging, with a currently **unsealed** master baseline in its documentation.
- [Teachers](https://github.com/coolman1984/Teachers) and [Yousef-Transportation](https://github.com/coolman1984/Yousef-Transportation): common Python/local app ancestry and realistic paid pilot scopes; good first consumers for UI/identity/backup/licence standards.
- [3D-Modeling](https://github.com/coolman1984/3D-Modeling): different geometry/canvas; reuse **shell and platform ports**, not force a generic dashboard into it.

## Phases (don't declare these done until accepted)
0. **This repository now:** design governance, manifest, control catalog, agent kickoff, audit/research, CI docs/spec checks.
1. **Reference adapters:** one adapter for Hessa's actual app, one for Trip Orders; compare account provisioning, scopes, audit, license, restore and invoices. Both complete baseline contract tests.
2. **Shared package v0.1:** extract only behavior used by at least two products (navigation tokens, UX states, permission contracts, role templates, licence verification) with deprecation/migration/version policy. Avoid a universal mega-backend.
3. **Revenue reference path:** a paid, assisted Egypt pilot, with expiry, renewal, customer-data export, clean Windows install and independent recovery. Customer acceptance evidence.
4. **LAN/SaaS adapter:** from Business Template, prove permission tenant isolation, subscriptions with signed webhook/reconciliation, cancellation, backup/restore and hosting threat model.
5. **Market expansion:** Saudi/UAE/EU compliance plug-ins **only after** qualified regional customer demand, counsel decision and current source review.

## Metrics to prove factory worth it
- Time from idea to one usable paid workflow; <= 20% product-owned platform code once proven (target, not a factual result).
- Count of reused **tested** capabilities rather than copied source files.
- Regression count / migration incidents / release failure rate.
- Clean-device onboarding completion and time; first-user journey success.
- Activation-to-paid and renewal rates; support hours per active customer.
- Unresolved high-risk issues and customer data-recovery drills.

## Work method
Select 1 pilot; snapshot its main commit and existing data fixtures; only add new branch/PR. Never reset another product's main, discard session work, combine divergent branches or change customer pricing silently. Retain isolated rollback and communicate with owner before introducing a breaking commercial contract.
