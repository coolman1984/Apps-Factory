# Small-business commercial tiers: owner decision 2026-10-09

**Status: accepted commercial product strategy; implementation NOT claimed.** Target customers: individuals, shops, and small/medium businesses in Egypt first. Keep the one-to-three-person maker team, one deployable modular app, no Kubernetes, microservices, permanent servers, or enterprise infrastructure by default.

## 0. Commercial plan != underlying connectivity engine

These are four CUSTOMER-FACING plans. Do NOT rename or break existing `connectivity.tier` values, schema versions or Hessa/BAMS mesh modes. Map each product's offer to its actual proven implementation. A customer can upgrade only after data migration and contract tests prove it safe.

| Plan | Windows + local DB | Remote copy | Extra PCs | Mobile | Authority |
| --- | --- | --- | --- | --- | --- |
| 1 - Solo/Essential | One PC, offline reads and writes | Encrypted, automatic, versioned **backup** if configured; NOT interactive cloud DB | No | Not included | Local PC |
| 2 - Connected/Owner | Multiple PCs, each with own DB and offline queue where supported | Cloud synchronization hub + independent encrypted backups | Yes | Owner-only, read-only KPIs, history and alerts | Cloud validates changes |
| 3 - Mobile Operations | Same as plan 2 | Same | Yes | Installed mobile web app with authorized sales, barcode, stock, corrections and staff roles | Cloud validates each write; mobile permissions distinct |
| 4 - Cloud Business | Hosted core of the product | Server-side backups and audited export; optional local replica | Optional Windows client | Full authorized web/PWA clients anywhere | Cloud primary, offline only where implemented |

Plan 1 cloud backup must NEVER be presented as multi-device synchronization, and a backup is not a live remote database. If online backup is unconfigured/unavailable, clearly say so; require tested off-device copies before claiming the plan's backup promise. Plans 2-4 require authenticated tenant-scoped server APIs, NOT direct client DB access. Plan 4 offline operation is NOT automatic.

**Feature and billing switches:** server-enforced entitlements per installation, tenant and user. Store owner mobile read-only is one owner seat for plan 2; plan 3 adds paid operational mobile seats; exact prices/seats need a separate owner-approved decision. Feature downgrade may disable writes but never obstruct export or backups. Do not retrofit remote synchronization into a live one-PC release without migration and recovery evidence.

## 1. Mandatory Windows shipping gate for every Windows-targeted paid product

- Workflow MUST run on Windows-hosted GitHub Actions on PR into main AND push to main; no skip, no success when a command exits nonzero. A green Linux job cannot substitute.
- Use a supported, preferably pinned Windows runner image; run domain + permissions + data tests there; build the actual Windows installer; install that exact artifact; start and open a real screen/API, save a record, restart, check persistence; uninstall must retain customer data.
- Test upgrades from previous supported installer, failed migration rollback, no demo passwords in production, settings/data outside Program Files, reproducible source/commit/artifact identity. Upload logs/artifact; never upload secrets/customer data.
- CI status must be REQUIRED in branch protection/ruleset (manual GitHub admin setting; a workflow alone is not enough). Never merge a red/pending run, even if Linux passes. Prevent skipped builds from reporting green.
- Before commercial release: on a **different clean Windows PC**, test install, recovery of a real-looking synthetic copy and printer/scanner if advertised. GitHub's VM does NOT replace physical-device acceptance.
- Gate evidence belongs to OPS-01, OPS-07, REL-03, DATA-05, DATA-06 and OPS-06, with run URL, exact commit, artifact digest and actual operator log. Factory's own Windows standards test validates standards only; each PRODUCT must maintain its own installer gate.

## 2. Non-negotiable customer data protection

No system can promise zero loss under every disaster. State recoverability, backup age (RPO), restore time (RTO) and last successful off-device copy in plain words, never "impossible to lose".

- Local SQLite is the business transaction authority only in Solo; use SQLite online backup API (or a safe database-supported snapshot), not a bare live-file copy in WAL mode.
- At least 3 independently restorable copies: production + separate local backup/disk + off-device encrypted versioned backup. Keep one copy out of the shop/PC. Synchronization replicas are NOT independent backups.
- Customer-controlled encryption keys and recovery procedure, authenticated uploads over TLS, least privilege, separate tenant authorization, limited retention, checked hashes, immutable/versioned snapshots and regular restore drills on another PC. Losing a decryption key may make recovery impossible: provide secure recovery guidance.
- Keep a persistent retry queue for offline uploads, visible last-success timestamp, "backup overdue" alert and non-silent failures. No raw personal/financial data to vendor telemetry or public logs.
- For cloud sync, use durable operation IDs, server-side transaction/permission checks, idempotency, conflict histories, explicit pending/rejected stock or payment operations. Cloud authority does not mean every offline sale can be confirmed immediately.
- Never expose a local database file on the internet; no shared SQLite network path and no open administrator port.

## 3. Installable Android/iOS web-based app

One responsive web codebase and mobile-first screens, `manifest.webmanifest`, service worker, HTTPS, icons, standalone display, install guidance; maintain a browser fallback. Android: use installable PWA first; produce an APK via supported trusted-web packaging only when needed, with site verification and signing. iOS: Add to Home Screen works without an IPA; App Store submission requires a separately approved wrapper/distribution plan and may cost money. Both still run on a browser engine even without a browser tab.

- Plan 2 mobile: only owner read with tenant-scoped API; read-only on both UI and server, separate limited credential, explicit session revoke, device loss recovery.
- Plan 3 mobile: all supported write journeys in end-to-end tests on Android and iPhone/iOS Safari, plus fallback for camera/barcode support (external Bluetooth/HID scanner or manual code). No native-only promise without real-device proof. Offline money, stock and conflict cases require explicit design/field proof before enabling.
- Plan 4 web-first: cloud reachable via HTTPS, audit, backup/export, and Windows client; do not claim offline mode without tests.
- Phone app never connects directly to a business database; it calls authenticated scoped API. Support accessibility, Arabic RTL, install, reconnect, auth, permission denial and fresh-data badge.

## 4. Cost ceiling and simplest safe path

Start with local SQLite and encrypted versioned backup storage; add a tiny authenticated sync relay only for plan 2. Prefer managed free/low-use services with monitoring and spending alarms, but FREE is conditional on quotas. Example options to evaluate, not vendor commitments: Cloudflare R2 (versioned objects/backups), Workers+D1 (small sync metadata), or Supabase Postgres for a carefully bounded multitenant sync hub. Avoid a paid VPS per shop or heavyweight always-on stack. Track monthly storage, upload traffic, daily requests, rows read/written, backups and restore labor; choose host/region and data transfer consent before handling real customers.

Sources checked 2026-10-09:
- https://docs.github.com/en/actions/reference/runners/github-hosted-runners
- https://sqlite.org/backup.html
- https://web.dev/learn/pwa/installation
- https://developer.chrome.com/docs/android/trusted-web-activity
- https://developer.mozilla.org/en-US/docs/Web/API/Barcode_Detection_API
- https://developers.cloudflare.com/r2/pricing/
- https://developers.cloudflare.com/d1/platform/pricing/
- https://supabase.com/docs/guides/platform/billing-on-supabase

## 5. Adoption plan and acceptance tests

1. **Factory + Store NOW:** codify four commercial plans, add PR-triggered mandatory Windows build/check, publish actual Store gaps. Do not silently change a customer's installed data, API, billing or permission defaults.
2. **Store plan 1 pilot:** test a Windows installer, disk corruption/process-kill recovery, safe online snapshot to a separate account/location, encryption/rotation, scheduled automatic backups, restore on clean PC, and last-backup warning. Owner chooses storage/region and encryption key recovery before real data leaves premises. No plan-1 "cloud protected" marketing until this works.
3. **Plan 2 prototype:** two Windows PCs with separate databases, automatic cloud sync with offline catch-up, concurrent stock and returns tests, owner mobile read-only. No production rollout until conflicts and permissions are proven on physical devices.
4. **Plan 3 prototype:** phone mobile write tests, barcode fallbacks and role-denial tests, stock conflicts, working checkout and printer strategy.
5. **Plan 4 only after customers justify it:** cloud-hosted service, managed backups, per-tenant isolation and Windows/browser PWA parity; measure costs with one small customer.

Every status uses `planned → implemented → verified → field_accepted`. A document, green Linux suite or a mobile-looking browser screen is never evidence of a delivered tier.
