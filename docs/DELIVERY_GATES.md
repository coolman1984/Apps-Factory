> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Evidence gates • NO-GO defaults

**What `scripts/factory.py check --release` enforces (0.10.0):** every applicable `core` control needs verified proof, plus two evidence items: `clean_device_restore` and `core_user_acceptance`. `reference` controls are advice and never block a release. The gates below describe the full working method; the later docs rewrite will trim them to match.

A product is not ready merely because a plan says "done." Each gate produces auditable paths, responsible reviewer, timestamp and result. `unknown` and `skipped` are NOT passes.

| Gate | Required output | Pass criteria |
|---|---|---|
| G0 Market | 5 competitors/alternatives where available, priced offer, buyer pain, discovery/interview notes | Paid journey and distinct value are clear; unsupported claims marked unknown |
| G1 Scope | Product brief, deployment mode, sensitive-data flags, data map, acceptance criteria | 1 core paid journey bounded; optional work explicitly deferred |
| G2 Threat/design | Access matrix, design tokens, UI flow, threat model, data ownership | Production demo/privilege shortcuts impossible; risk owners named |
| G3 Core capability | Installed/shared packages or isolated implementation with contract tests | **Actual executable** login, roles, admin, audit, subscription OR licence, recovery, help and core workflow |
| G4 Tests | CI artifact: unit/integration/browser/perms/negative/tenant/retry/backup, static and dependency checks | Exact commit green, no critical/high data/security defects, skips documented |
| G5 Distribution | Reproducible installer/deployment, upgrade/rollback, config/secrets, version/SBOM | Install and upgrade on clean TARGET OS or target hosting; no reliance on developer machine |
| G6 Field acceptance | Real hardware/printer/network, realistic synthetic or approved data, timed core journey, independent restore | Customer/operator performs without engineering help; signed acceptance and remaining limitations |
| G7 Commercial release | Terms, pricing, invoices/payment handling, privacy notice, support/incident process, user help | Named scope/customer/region, correct local checks, receipt/activation/support work end to end |

## Automatic fail
- No login or UI-only permissions where sold as multi-user.
- Shared `admin/123` / hidden vendor bypass in shipped build.
- Payment or subscription can be spoofed by browser variable/client event.
- One tenant can read/write another's records through IDs, exports or attachments.
- Money overwritten/duplicated silently on retry; expiry destroys customer access to data.
- Backups cannot be restored on another clean instance.
- Claims of "all tests passed" without test command/artifact, or ignoring failed browser runs.
- Customer data/production credentials in public repo, screenshots, logs, CI artifacts.
- Any certification claimed without scope-specific independent evidence.
- Sync tier: a duplicated/replayed change applied twice, a revoked user's offline change accepted, a rejected change dropped silently, or a hub restore that resurrects deleted data.
- Several PCs writing one SQLite file over a network share.
- Phone PWA holding unsynced records with no visible pending count.
- Unsigned installer/EXE outside ADR-0004 stage A rules (vendor-installed or verified-updater only, Ed25519-signed, SHA-256 published); update applied without verifying the signed manifest and file hash.
- Asking a customer to disable antivirus or trust a vendor root certificate.
- An upgrade or uninstall that can overwrite or delete the customer database or settings.
- Licence failure that hides, deletes or encrypts customer data; a signing private key inside the shipped build.
- Remote/AI support action on a customer install without a live customer grant and audit entry.

## Evidence record (copy for each gate)
```
product:
gate:
commit:
artifact_id_or_hash:
test_commands_and_results:
clean_device_or_environment:
critical_negative_cases:
field_acceptance:
unknown_or_skipped:
reviewer:
date:
decision: PASS | NO-GO | CONDITIONAL (cannot ship)
```
