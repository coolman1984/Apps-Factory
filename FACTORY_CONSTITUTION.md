# Apps Factory Constitution • v1.2 • 2026-10-08

> One repeatable **commercial product process**, not one enormous framework forced onto every app. All MUST requirements have a named test or a documented field-acceptance gate.

## Universal commitments
1. **Evidence before code:** identify buyer, competitor capabilities/prices from dated primary evidence, pain, differentiator, one paid journey, support cost, and acceptance criteria. Mark unverifiable claims UNKNOWN.
2. **Unified product identity:** design tokens; coherent spacing, typography, navigation, forms/tables, permissions feedback, notifications, help, AR/EN and RTL/LTR where target market needs them; keyboard and WCAG 2.2 AA targets for web UI. Dedicated canvas/film/3D may diverge from ordinary administrative page layouts.
3. **Complete state UX:** loading, empty, error, offline/disconnected, retry, pending/saved, denied, expired, success. Every visible button performs a real action. No false "saved".
4. **First-run ownership:** administrator created during local setup or securely invited for hosted services. Unique credential; strong salted adaptive password hash; rate limiting, session revocation, safe recovery, optional MFA and step-up for dangerous actions.
5. **Authorization:** deny by default; enforce on server at action, record, tenant, field, export, attachment, batch job and real-time/event boundaries. Roles customizable with safe templates; separate duties for money/refunds.
6. **Vendor access is not an admin backdoor:** explicitly authorized ticket, user-selected scope, expiry, opt-out/revoke, visible session and append-only actor trail; no permanent secret vendor login.
7. **Honest monetization:** plan/feature limits enforced server-side. Cloud subscriptions consume verified gateway/billing events idempotently. Offline desktop licences are digitally signed and verified with **public** key; signing private key never shipped. Clock rollback and grace limitations are documented; no impossible anti-piracy guarantee.
8. **Customer owns exportable data:** expiry never irreversibly blocks lawful reading, backup, export or agreed retention/erasure. Grace, suspend, renewal, refund, device transfer, cancellation and deletion are designed explicitly. Data never held hostage.
9. **Data correctness:** unique idempotency keys for money/billing/retries/imports; audit who/what/when/before-after where appropriate; financial operations immutable with authorized reversals; no unapproved hard deletes of ledger events.
10. **Recovery:** separate data and binaries, atomic upgrades, safe forward-only migrations with compatibility/backup, actual restore on another clean machine, errors are actionable. Retention and deletion depend on law and documented agreements.
11. **Tenant/data isolation:** company ID enforced across SQL, files, jobs, queues, caches, logs, exports, generated links and AI retrieval; clients cannot supply arbitrary tenant/privilege context.
12. **Secure development:** threats, dependency pinning, SCA, secret scanning, static analysis, tests, SBOM/release provenance as appropriate, separate environments, least-privilege CI credentials, written incident/vulnerability process.
13. **Privacy by design:** data map, purpose/legal basis, minimization, consent when appropriate, subject rights, processor/subprocessor inventory, deletion/retention schedule, regional transfer assessment.
14. **Works for humans:** one-click customer installation when sold as desktop; locally usable without technical setup where promised, guided onboarding, examples, search/filter/export, short contextual help.
15. **Operable business:** diagnostic logs with redaction, health checks, safe updates, feature flags, support handoff, SLA boundaries, terms, invoices/receipts where legally applicable.
16. **No ungrounded certification:** do not imply tax, medical, payments, ISO or legal compliance without independent scope-specific checks and approval.
17. **Test, not theatrical reports:** passing tests must be executed on exact source/artifact; skipped tests stay skipped; verify release and customer acceptance separately.
18. **Reusable versioned core:** product customization via manifest/plugins and product-specific modules; no duplicating security/licensing/admin engines across apps; breaking core changes require compatibility test matrix.
19. **Modular monolith, tier-ready data:** one deployable app per product built from modules with versioned contracts ([ADR-0001](docs/decisions/ADR-0001-architecture-and-connectivity-tiers.md)). Every record has org (and branch) scope and a globally unique client-generated ID from the first schema, so moving a customer to a higher connectivity tier never rewrites data.
20. **Honest connectivity:** the contract states what happens when the main PC, the internet or the cloud is down. Offline work is bounded (grace days), every offline change is re-authorized by the hub, rejected changes are visible, and replicas are never counted as backups ([sync spec](docs/CONNECTIVITY_AND_SYNC.md)).

21. **Free and simple first:** pick proven free/open-source tools; pay only where no free path exists (code signing, one small server, a domain). Record the reason for every paid tool. Revisit when revenue allows.
22. **Protection without hostage-taking:** copy protection is layered and honest ([ADR-0002](docs/decisions/ADR-0002-protection-updates-vendor-control.md)): signed licences with vetted crypto, compiled signed builds, traceable licences. It never deletes, hides or encrypts customer data and never hides a remote kill switch.
23. **Updates never touch customer data:** signed update manifests, data/settings outside the program folder, verified backup before migration, automatic rollback, canary first.
24. **Support through one door:** every product has a help button, self-diagnosis and customer-consented remote sessions reporting to the Vendor Control Center. AI agents work through that center with read-by-default tools, PRs for code, and allowlisted, approved, audited repairs only.

## Profiles
- **desktop:** one-device local data + trusted offline or optional online licensing; local loopback app or native UI; OS installer test.
- **lan:** one primary owner server on local subnet, many scoped accounts, safe network exposure, network outage + device recovery tests.
- **saas:** separate production tenants and billing identity, subscription webhooks, hosted secrets, tenant isolation, backups and incident response.

### Connectivity tiers (`connectivity.tier`, schema 1.1)
- **standalone** (desktop): one device, no network.
- **office_server** (lan): one office PC owns the database; when it is off, other devices cannot write (said in the contract).
- **cloud_sync** (premium; desktop/lan/saas): every device keeps a scoped replica and works offline; a cloud hub is the record authority. Activates `sync` + `saas` controls.
- **cloud_only** (saas): hosted, online browser/PWA.
- Overlays: `mobile` (installable PWA, cloud tiers only), `multi_site` (branches, cloud tiers only), `multi_owner` (owner quorum and transparency), `windows` (a shipped EXE: protection, code signing, safe updates).
- **high_risk_overlay:** optional for healthcare, financial, children's or regulated/high-impact data; extra laws, retention, consent/rights, audit, independent security review and vertical-specific approvals.

## Implementation status vocabulary
`planned` → `implemented` → `verified` → `field_accepted`. None may be skipped based on screenshots, claims or generated tests alone.

## Anti-patterns
- Shared static admin credentials; vendor hidden admin login; "developer mode" discoverable in customer build.
- One giant "do everything" master service or copy-pasting a repo's DB to every product.
- Storing passwords/API keys in client code; UI-only access checks.
- Free-form deletion of money events; hidden retroactive repricing.
- Expiring a license by deleting or encrypting customer records.
- Building 70 screens before one customer completes one paid workflow.
- Autoincrement integers as record identity, or global document numbers generated offline, in anything that may ever sync.
- Several PCs opening one SQLite file over a network share.
- Treating synced replicas as backups; letting a device stay offline-authoritative forever; silently dropping a rejected offline change.
- Storing mutable money balances instead of deriving them from append-only events.
- Promising "free cloud" for a paid tier, or promising iPhone PWA features that Safari does not provide.
- Hand-written cryptography, signing keys in a repository/CI/customer build, or one key for both licences and updates.
- Customer databases inside the program folder; an installer or uninstaller that can delete customer data.
- Permanent unattended remote passwords by default; AI agents with shell or SQL access to customer machines.
- Claiming unsupported compliance/security certifications.
