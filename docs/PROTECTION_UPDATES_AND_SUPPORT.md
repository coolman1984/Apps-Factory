> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Copy protection, safe updates, vendor control center and AI-assisted support

Decision: [ADR-0002](decisions/ADR-0002-protection-updates-vendor-control.md). Controls: `PROT-*`, `REL-*`, `SUP-*`, `AI-04` (+ existing `BIZ-04`, `IAM-05`, `OPS-01`).
**Rule of this factory:** free, proven tools first; pay only where no free path exists (code signing, a small server). Sources checked 2026-10-08; re-check prices before buying.

## 1. Copy protection that fits our budget (honest)
No software protection is unbreakable. The goal is to make copying **inconvenient, traceable and not worth it**, never to punish paying customers.

| Layer | What we do | Cost | Stops |
|---|---|---|---|
| L1 Signed licence | `packages/af-license`: Ed25519 signed file per customer (product, customer name, edition, features, seats, devices, expiry, grace). Private key offline; the app holds only public keys | free | editing dates/features, fake licence files, copying to an unlisted PC (when device-bound) |
| L2 Activation | Offline: app shows a request code (device fingerprint) → vendor returns a signed licence via WhatsApp/e-mail. Online (cloud tiers): activation and seat count on the hub | free | one licence on many PCs |
| L3 Compiled build | Commercial builds compiled with **Nuitka** (Apache-2.0, free core) instead of shipping Python bytecode; no `.py` sources, debug off, no secrets inside the binary | free | casual one-line patching of Python files |
| L4 Tamper evidence | Signed hash list of our own files checked at start; clock-rollback guard (latest time seen stored in the DB) | free | clumsy patching, turning the PC clock back to stay in trial |
| L5 Code signing | Stage A (now): our own Ed25519 signature on installer and updates + published SHA-256, installed by us; stage C: Authenticode certificate ([ADR-0004](decisions/ADR-0004-windows-trust-without-certificate.md)) | free now, ~€ per year later | tampered installers/updates (now); "unknown publisher" warnings (later) |
| L6 Business | Customer name shown in the header and on receipts; updates and support only for valid licences; fair price; cloud features live on the hub | free | silent resale; a cracked copy gets no updates/support/cloud |

**Never:** hand-written crypto; trusting the algorithm field in a file; a hidden kill switch; deleting, hiding or encrypting customer data when a licence fails (expiry = read/export/backup mode, BIZ-03 in RULES.md); spyware; claiming "uncrackable".
**Avoid for now:** PyArmor free tier for commercial products (its terms restrict commercial use and changed between versions); paid obfuscators sold as "irreversible" — they raise effort, not certainty.
The current hand-written signing file in the existing apps is replaced by `af-license` (or proven equivalent) before any sale.

## 2. Patches and new versions without touching customer data
```text
AI agent / developer → PR → CI (unit + upgrade test on a real-shaped synthetic DB) → human merge → tag
   → GitHub Actions builds (Nuitka/PyInstaller) → Authenticode sign → signed update manifest (af-license "update" key)
   → publish to the download channel → canary customer → everyone
App: checks channel → verifies manifest signature + file hash → verified backup → closes → installs → migrates DB → health check → or rolls back
```
- **Data lives outside the program folder** (e.g. `C:\ProgramData\<Vendor>\<Product>\data` and `...\settings`). The installer never writes, replaces or deletes that folder. Uninstall asks, defaulting to *keep data*.
- Installer (Inno Setup, free): stable `AppId`, seed files `onlyifdoesntexist`, data dirs `uninsneveruninstall`, `CloseApplications` so the DB is not locked.
- **Before every migration:** verified backup; schema version stored; forward-only migrations; on failure restore the backup and the previous binaries.
- **Update channel trust:** the e-mail/WhatsApp message is only a notification. The app trusts nothing until the manifest signature (separate `update` key) and file hash match. A link sent by an attacker therefore cannot install anything.
- **Updater engine (spike, pick one with evidence):** `tufup` (built on python-tuf, works with PyInstaller bundles, patches + full archives) or **Velopack** (installer + delta updates, Python package available; replaces the install folder, so data must live outside it). Both free.
- **Download hosting:** source repos stay private. Binaries go to a separate public "releases" location the customer can reach without a GitHub account: a public releases repository containing only signed binaries, or Cloudflare R2 (free tier 10 GB-month, no egress fees).
- **Staged rollout:** one canary customer first, pause/rollback switch, then all. Security fixes are delivered even to expired licences (customer safety beats licence enforcement).
- GitHub artifact attestations are free only for **public** repositories; for private repos we rely on our own signatures + recorded SHA-256 in `OPS-01` evidence.

## 3. Vendor Control Center (our own internal product)
Manifest: [`examples/vendor-control-center.json`](../examples/vendor-control-center.json). One small hosted app (cloud_only) + self-hosted open-source parts:

| Module | What it does | Free building block |
|---|---|---|
| Customer & install registry | every customer, product, version, tier, licence state, last heartbeat, contact | own module (FastAPI + PostgreSQL/SQLite) |
| Licence desk | issue / renew / transfer / revoke signed licences; private key on an offline machine | `af-license` |
| Health board | heartbeats from installs and cloud hubs: version, last backup, last sync, error counts, disk space | own heartbeat endpoint; Uptime Kuma (MIT) for hub uptime; Healthchecks (BSD-3) style "missed backup" alerts |
| Crash & error inbox | grouped exceptions with stack traces from all installs | GlitchTip (open-source, Sentry SDK compatible) or Bugsink; Sentry SDK in the apps |
| Support tickets | "اطلب مساعدة" button in every app creates a ticket + redacted diagnostic bundle the customer previews before sending; vendor gets a Telegram/e-mail alert; status shown back in the app | own module |
| Remote session | customer-initiated, time-boxed, visible, revocable, audited support grant (`IAM-05`); screen help through **RustDesk** (AGPL-3.0, free self-hosted relay) in attended mode with the customer's one-time code | RustDesk server; MeshCentral (Apache-2.0) as alternative |
| Release desk | versions, canary list, rollout %, rollback | GitHub Actions + download channel |

Not chosen now: Tactical RMM (source-available, signed agents need a monthly sponsorship), Keygen CE (free self-host but source-available FCL, API-only; reconsider when licence volume grows), commercial remote tools (paid per seat).
**Privacy:** heartbeats carry no personal data; diagnostic bundles are redacted and previewed; telemetry fields are listed in the customer contract and can be switched off except what a cloud tier needs to run (`SUP-04`).

## 4. Built-in self-diagnosis in every product (`SUP-02`)
A "فحص البرنامج" page and CLI: database integrity check, free disk space, last verified backup age, licence state, sync status/pending count (cloud tiers), printer reachability, version + update channel, last 50 error codes. Every error has a code, a plain Arabic message, the next step for the customer, and a technical detail for the vendor. The same checks feed the diagnostic bundle and the heartbeat.

## 5. AI agent in the support loop (MCP, `AI-04`)
The AI agent (Claude or any strong agent) connects to the **Vendor Control Center**, never directly to a customer's database.

| Tool exposed through our MCP server | Access | Needs |
|---|---|---|
| list/read tickets, read redacted diagnostic bundles, error groups, heartbeats | read | vendor login |
| search code, docs, past fixes; reproduce on a synthetic copy | read | — |
| propose a fix → open a PR → run CI | write to **our** repo only | human merge |
| draft a customer reply | draft | human sends |
| run a predefined repair action on a customer install (re-index, rebuild cache, re-run failed migration from backup) | write to customer | **live support grant + vendor approval per action + visible to customer + audit** |

- No raw shell, no arbitrary SQL, no file download from customer machines through the agent. Repair actions are a short allowlist written and tested by us.
- Tickets, logs and bundles are **untrusted text**: they can contain instructions aimed at the agent (prompt injection). The agent treats them as data, and tool permissions are enforced by the server, not by the prompt.
- Follow the MCP security best practices: no token passthrough, per-client consent, least-privilege scopes, every tool call logged with actor and ticket.
- Customer personal data is redacted before it reaches any AI provider; full data only with the customer's explicit consent recorded on the ticket.

## 6. What still costs money (the honest minimum)
| Item | Why no free path | Indicative cost (verify) |
|---|---|---|
| Authenticode code-signing certificate (**deferred**, ADR-0004 stage C) | Windows/SmartScreen trust; Azure Artifact Signing (~$9.99/month) accepts individuals only in the US/Canada and organizations in the EU/UK | Certum Standard Code Signing in the cloud listed around €189 (validity now ≤ 460 days per certificate); check Egyptian eligibility and identity verification route |
| Small server for the Control Center, GlitchTip, RustDesk relay | they must be reachable 24/7 | a small VPS, roughly $5–10/month class; free tiers are fine for trials only |
| Domain name | HTTPS origin for PWA, updates and support | small yearly fee |
Even signed builds can trigger SmartScreen until reputation builds: sign every release with the same identity, keep version info, avoid UPX packing, prefer one-folder builds, and submit false positives to Microsoft.

## 7. Sources (checked 2026-10-08)
- Nuitka licence and commercial add-on: https://nuitka.net/doc/commercial-license.html • https://nuitka.net/commercial.html
- PyArmor licence types: https://pyarmor.readthedocs.io/en/stable/licenses.html
- Ed25519 in Python: https://pynacl.readthedocs.io • `cryptography` Ed25519 API (pyca)
- Licensing patterns (signing, fingerprints, grace): https://infosecwriteups.com/asymmetric-signing-machine-fingerprinting-and-offline-grace-periods-building-a-license-system-d8dd5678e1cb • https://bugnet.io/blog/what-to-do-about-piracy-as-an-indie-dev
- Keygen CE self-hosting: https://keygen.sh/docs/self-hosting/ • https://keygen.sh/
- tufup: https://pypi.org/project/tufup/ • Velopack Python: https://docs.velopack.io/reference/py
- Inno Setup data preservation discussion: https://learn.microsoft.com/en-us/answers/questions/506643/where-to-persist-application-data-between-versions
- Azure Artifact Signing: https://azure.microsoft.com/pricing/details/artifact-signing/ • https://devclass.com/2026/01/14/code-signing-windows-apps-may-be-easier-and-more-secure-with-new-azure-artifact-service/
- Certum code signing: https://shop.certum.eu/standard-code-signing-in-the-cloud.html • https://support.certum.eu/en/code-signing-required-documents/
- SmartScreen / Defender false positives: https://textslashplain.com/2026/01/27/microsoft-defender-false-positives/ • https://github.com/microsoft/apm/issues/487
- GitHub artifact attestations plans: https://docs.github.com/en/actions/how-tos/secure-your-work/use-artifact-attestations/use-artifact-attestations
- Cloudflare R2 pricing: https://developers.cloudflare.com/r2/pricing/
- GlitchTip: https://railway.com/deploy/glitchtip-sentry-alternative • Uptime Kuma vs Healthchecks: https://selfhosting.sh/compare/uptime-kuma-vs-healthchecks/ • https://healthchecks.io/about
- RustDesk self-hosting and unattended access: https://rustdesk.com/blog/rustdesk-unattended-access-setup • MeshCentral: https://en.wikipedia.org/wiki/MeshCentral • https://www.intel.com/content/www/us/en/developer/articles/technical/meshcentral2-multi-os-user-consent-feature.html
- Tactical RMM licence/sponsorship: https://license.tacticalrmm.com • https://docs.tacticalrmm.com/sponsor/
- MCP security best practices: https://modelcontextprotocol.io/specification/2025-11-25/basic/security_best_practices
- minisign (alternative file signing): https://pypi.org/project/minisign
