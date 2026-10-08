# Platform architecture and capability contracts

Decision record: [ADR-0001](decisions/ADR-0001-architecture-and-connectivity-tiers.md) — modular monolith, default stack, connectivity tiers.

## Layers (no fake code reuse)
```text
Apps Factory (governance/manifest/gates/standards)
   ├─ Versioned Shell/UI + i18n + permissions-aware navigation
   ├─ Identity / authentication / organization / permissions
   ├─ Billing entitlement port OR signed offline license verification
   ├─ Audit, backups, migration, diagnostics, support-consent
   ├─ Sync port (cloud_sync tier only): outbox, hub client, device enrollment, sync status
   ├─ Connector ports: email, SMS, payment, Excel/Word, AI (optional)
   └─ Product-owned domain modules
       ├─ Hessa: centre, attendance, school-year fees
       ├─ Trip Orders: driver, trip, kilometre, tariffs
       ├─ Space Planner: canvas, geometry, logistics
       └─ Business Template: generic business engines + recipes
```

**Important:** these ports are **contracts to implement**. This repository does not yet contain a production identity/entitlement/audit engine.

## Default interface contracts (versioned, typed)
- **Identity** `currentActor() -> {userId, orgId, roles, abilities, sessionId}`; server derives from verified session. Never accept role/org from browser as authority.
- **Permission** `authorize(actor, action, resource) -> allow|deny`; default deny; owner/user/tenant/record/field scopes. Denials leave an audit-safe event.
- **Audit** `record({actor, action, objectId, orgId, correlationId, timestampUtc, result})`; append-only, secrets redacted; critical domain events reverse rather than mutate.
- **Entitlement** `isAllowed(orgId, capability, atTime) -> {allowed, reason, limit}`; cached short-lived; payment status from verified signed event, not raw client flag.
- **Offline license** `verifySignedLicense({claims, signature}, publicKey) -> {valid, entitlement, expiry, devicePolicy}`; signing key exists only on vendor-side; prefer Ed25519 where supported, test clock-skew/offline-grace/machine replace.
- **Data recovery** `backup() -> verifiedSnapshot`; `restore(snapshot, emptyTarget) -> integrityEvidence`; backup must be truly restorable, including roles, indexes and config.
- **Support session** `authorizeSupport(customerApprover, scopes, expiresAt, ticket) -> oneTimeGrant`; deny when revoked/expired, separate vendor identity, visible customer indicator.
- **Sync (cloud_sync)** `enqueue(change) -> changeId` in the same local transaction as the write; `push(batch) -> {accepted, quarantined, hubSeq}`; `pull(sinceHubSeq, scope) -> changes`; `status() -> {pending, lastSyncAt, conflicts, epoch}`. Envelope: [`factory/contracts/sync-envelope.schema.json`](../factory/contracts/sync-envelope.schema.json); rules: [CONNECTIVITY_AND_SYNC.md](CONNECTIVITY_AND_SYNC.md).
- **Module rule:** a module owns its tables and exposes only its contract; tests run per module without booting the whole app (`ARCH-01`).

## Admin areas
**Settings:** personal profile, locale, appearance, notifications, preferences.
**Customer Administration:** company, users, role matrix, sites, data retention, backups, business setup, billing plan and device/seat counts.
**Vendor Support (NOT ordinary admin):** status diagnostics, signed release channel, temporary consent-based access. Customer can see/revoke every support request.
**Demo-only owner helper:** one-click synthetic setup and quick login, no production keys or shared default password.

## Subscription state machine
`trialing -> active -> past_due -> grace -> restricted -> cancelled` (transitions verified by gateway provider AND idempotent reconciliation; states are product policy, not a direct copy of any one provider).
- Billing provider is source of invoice/payment truth, app stores reconciled entitlement snapshot.
- Verify webhook signature and event ID; handle duplicate/out-of-order events by checking authoritative subscription state.
- Show expiry, renewal, invoice history, grace and limitations in Arabic/English.
- Read/export/backup and legal data access remain available after restriction. No destructive disabling.
- No software-based license is unbreakable; measure abuse pragmatically rather than punish customers.

## Implementation boundaries
- Start with feature flags and explicit policy to avoid pulling AI/internet/complex tenancy into offline desktop.
- Generate a product-specific manifest and code adapters. Never silently overwrite core code from another repo.
- For commercial deployments choose one of desktop/lan/saas **before** selecting libraries.
- Only put versioned shared code into a central library after 2 independent products consume it with cross-product tests.
- Compatible upgrades: snapshot, rehearsal, schema forward migration, detect downgrade, rollback binaries, preserve data.
- Minimum integration gates: permissions with forced denied actions; duplicates/retries; simulated offline/disconnect; export/backup/restore; installer and actual browser journey.

## Migration plan
1. Freeze current product behavior and capture smoke tests/screenshots/data fixtures on an **isolated** instance.
2. Compare existing capabilities with the factory manifest. Add missing contracts as adapters, not direct copy.
3. Migrate one harmless shared component (design tokens or help/error states); prove behavior unchanged.
4. Migrate identity/licensing only with account/data migration plan and explicit rollback.
5. Upgrade existing products one by one. Never force-merge all repository branches or rewrite live DBs.
