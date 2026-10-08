# Shared administration, demo, vendor support and revenue UX

These are **implementation contracts**, not an assertion that the code exists. Every new paid product selects deployment mode + entitlement port in its manifest.

## Standard routes/sections
| Workspace | Recommended page | Core actions | Negative test |
|---|---|---|---|
| First run | Create owner / organization | Create unique owner; bootstrap once; show how to recover | Second owner registration refused |
| Sign in | Login / forgot password / sessions | Sign in, rate limit, revoke sessions, reset with proof of identity | Reused token after logout denied |
| My Account | Preferences | My profile, language, theme, notifications, password/MFA | Cannot alter another actor's preference |
| Dashboard | Today's work | Assigned tasks, filtered indicators, quick action, current subscription warning | Hidden data inaccessible through API |
| Users | Accounts, invitations, activity | Invite/disable, scoped roles, session revoke, user lifecycle | Cannot self-escalate/re-enable revoked account |
| Permissions | Role templates and matrix | Role per module/action/record/branch, least privilege, deny by default | Denied batch/export endpoints too |
| Organization | Company / branches / fiscal locale | Branding, regional currency/calendar, assigned branches, legal contacts | Tenant A cannot modify tenant B |
| Data & Recovery | Backups, import, export, retention | Backup, scheduled policy, preview import, reconciliation, restore rehearsal | Broken backup cannot be labeled healthy |
| Security & Audit | Audit/search/alerts | Search who, when, action, before/after refs; login failures, data exports | Logs redact secrets and restricted PII |
| Billing / Licence | Plan, invoices, devices, renewals | Clear expiry, feature limits, seats/devices, grace, upgrades, cancel, reactivation, export | Tampered browser cannot grant entitlement |
| Support | Request/support session status | Customer consent, scope, ticket, expiry, view activity/revoke | No vendor access without current grant |
| Help | Guides, product/version/status | Role-specific how-to, support details, release notes | Broken connection has readable recovery |

Use role/ability names semantically: `owner`, `administrator`, `manager`, `operator`, `auditor`, `vendor_support`; names are templates, not authorization. Every action enforces authority on the server. Operator with read-only dashboard must not automatically obtain report/file exports.

## A. Development, demo and real customer
- **Development:** localhost loopback/isolated synthetic DB; random or environment-injected credentials, easy reset of fake data; may offer a DEMO button that seeds fixtures and signs in to a demo-only account. It must never reach real production data.
- **Preview/demo release:** distinct build ID, synthetic data, non-production payment/AI endpoints, visible DEMO ribbon. Demo credentials can be printed only in that isolated deployment, not embedded in sold executables.
- **Production:** first-run owner sets unique password via secure provisioning/invite; no `admin/123`, no `?dev=true` bypass, no clickable vendor superuser shortcut. CI asserts demo flag disabled and server refuses demo APIs/seed in production, even when HTML is modified.
- **Developer support:** user-controlled consent with requested ticket, declared reason, permissions, expiry, vendor identity, activity records, direct revoke and default-off. Remote screen sharing can be alternative when support API is unjustified.

## B. Billing / subscription
1. Define product `plan`, billing interval, quotas, entitlements, seat/device policy, grace, currency/taxes on invoice and cancellation semantics.
2. Customer signs up in trusted backend; payment provider handles sensitive card fields (avoid handling PAN/PCI scope).
3. Provider sends **verified signature** event; system records `eventId` once, fetches authoritative subscription state and reconciles idempotently. Delay/out-of-order/retry events do not double-entitle or double-charge.
4. Backend issues snapshot that entitlement middleware verifies **on every paid action** (including API/agent/batch/export where licensing applies).
5. 7/3/1-day warnings are **configurable commercial policy**, not a legal default. Visible date/time zone and last sync.
6. Grace means retained limited service as contracted; expired/restricted preserves rights to read/export/backup, account notices and renewal. Never corrupt/delete business records.
7. Upgrade/downgrade with seat reductions, refunds, chargebacks and cancellation has a written, tested, deterministic rule. Invoice is not automatically a legally compliant VAT invoice.
8. Vendor billing key stays server-side; no private signing key or entitlement editing field in customer/client database.

## C. Offline desktop licences
- Seller generates signed claim `{licenseId, productId, edition, features, seats, devicePolicy, issued, notBefore, expires, gracePolicy, customerRef, keyId}`. Cryptographic signature (e.g. Ed25519) produced with vendor **private** key held server-side/offline vault.
- Customer executable contains only trusted verification public key(s), keyed for rotation. Verify canonical claims/signature, product and feature selection before paid actions.
- Offline activation by copying request/response code or signed file. No assumption of permanent network access.
- License move/reissue/revocation and device loss are support processes with auditable grants; support clock skew or rollback checks without claiming tamper resistance is perfect.
- Expiry cannot hide/decrypt away customer business data; read/export/backup allowed by contract. Enforced licence is **not** equivalent to finance/legal-grade DRM.
- Cloud subscription and offline licence verification are **different adapters**, not one hardcoded global check.

## D. Required acceptance cases
- Admin invites operator, operator can complete their task but cannot see hidden pricing or other branch/customer.
- Login throttled; password reset revokes old sessions.
- Subscription payment event replay, forged signature and out-of-order cancel/restart all fail safely.
- At expiration, customer can still login/export/backup but cannot perform contracted restricted operations.
- Vendor support without grant / after expiry / revoke = denied, audited.
- Demo bootstrap never responds in production; a developer changing client JS cannot escalate.
- Safe restore on different clean PC retains license/reference consistency (device transfer handled separately).
