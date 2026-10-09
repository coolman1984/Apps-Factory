# Rules

The only rules that block a release, plus the limits and the agent workflow that never change.
Source of truth for the controls: `factory/controls.json` (catalogue 1.10.1). `python3 scripts/factory.py check <manifest> --release` fails when an **applicable core control** has no verified proof, or when one of the two evidence items is missing: `clean_device_restore` (restore on a clean device) and `core_user_acceptance` (first customer accepts the core journey). All other controls are `reference` advice and never block.

**Owner decision (2026-10-09):** Windows-targeted products must run their actual installer acceptance on a Windows GitHub Actions runner for every PR and main push. Require the job in GitHub's branch protection. Commercial packages Solo / Connected / Mobile Operations / Cloud Business are separate from technical connectivity modes and have sale-blocking cloud-backup/mobile evidence. See [SMB commercial tiers](docs/SMB_COMMERCIAL_TIERS.md). No remote backup, phone, zero-loss or server mode is claimed from a plan name alone.

## 1. The 32 core controls
"Checked by" is the acceptance evidence written in the catalogue.

### Identity and access
| Control | Rule | Checked by |
|---|---|---|
| IAM-01 | A unique admin is created at first run, with a safe recovery | first-run and replay tests |
| IAM-02 | Salted adaptive password storage, login throttling, session revocation | auth negative tests |
| IAM-03 | Deny by default on endpoints, objects, fields and exports | forced wrong-role API tests |
| IAM-06 | Production rejects static demo credentials and shortcuts | production-mode negative test |
| IAM-08 | One permission per page, per data-changing action and per sensitive field, in plain words | `packages/af-access` check in the product's unit tests |
| IAM-10 | The server refuses changes that leave nobody able to manage people | `af_access.admin_safety` cases mirrored as API negative tests |
| IAM-11 | Menu, palette and direct URL follow page permissions; the server sends no data of a page the person cannot open | role-denial tests per page and per sensitive field |

### Data
| Control | Rule | Checked by |
|---|---|---|
| DATA-02 | Every write records who, when and the correction; financial history is never silently deleted | audit and reverse-operation checks |
| DATA-03 | Create, payment, import and retry are idempotent; concurrent edits are safe | duplicate/race scenario |
| DATA-05 | Verified backup and a restore on a different clean machine | backup + different-PC restore proof |
| DATA-06 | Schema or version change is rehearsed; no silent data loss | downgrade and rollback test |
| OPS-06 | Power loss or a killed process during write, sync, backup or upgrade leaves data consistent | kill-process and power-cut drill log on the target device |

### Security
| Control | Rule | Checked by |
|---|---|---|
| SEC-02 | No secrets in the repository, browser or logs; safe rotation | scan + secret-handling tests |
| SEC-03 | Input validation, output escaping, prepared queries, file-path control, CSRF where relevant | targeted negative tests |
| SEC-04 | Right TLS, loopback or LAN trust; secure cookies or tokens; session timeout | deployment-mode attack checks |
| SEC-07 | Strict CSP, Origin and Host checks, proxy headers never mean "this PC", spreadsheet formulas neutralised | negative tests per item |

### Licensing
| Control | Rule | Checked by |
|---|---|---|
| LIC-01 (paid products) | Trial and paid licences are Ed25519 codes tied to the device, verified offline with public keys only | product test: wrong PC, expired code and clock-back are refused; read, export and backup still work |
| BIZ-03 (paid products) | A licence failure or expiry never deletes, hides or encrypts customer data; no hidden kill switch; expired means read, export and backup | expired and invalid licence drills |

### Release and delivery
| Control | Rule | Checked by |
|---|---|---|
| OPS-01 | Exact source-to-artifact SHA, changelog and rollback | release proof |
| REL-03 (Windows) | Data and settings live outside the program folder; the installer never deletes them; verified backup before migration; automatic rollback | upgrade N-1 to N on a realistic synthetic database, failed-migration rollback, uninstall keeps data |
| OPS-07 | The Windows installer is built on a real Windows runner and the installed program serves its pages | a green workflow run id in the release notes (the clean-PC install by a person is a separate gate) |
| QA-02 | Every write route survives junk input with a calm answer | a junk-input suite green on the release commit; each crash becomes a regression test |

### Experience
| Control | Rule | Checked by |
|---|---|---|
| UX-08 | A browser sweep opens every page with large realistic data at phone, laptop and desktop widths in every language and fails on overflowing text | sweep run on the release commit, and proof it fails on a known overflow |
| PERF-01 | Every main page stays within `factory/ui-budgets.json` on a throttled CPU | `tools/ui-lab` REPORT.md with "All pages within budget" |
| A11Y-01 | Zero serious or critical axe findings in both languages; contrast 4.5:1; keyboard reachable | ui-lab accessibility column = 0, plus a manual keyboard journey |

### Help
| Control | Rule | Checked by |
|---|---|---|
| HELP-07 | Every role has an ordered first-day course; the administrator's starts with setup; progress is saved on the server; every guide is walked in a real browser | `af_guide check`, `packages/af-guide/testing/walk_guides.py`, and a browser resume test |
| HELP-09 | Every error code the server can return links to a problem entry | `af_guide check --errors` has no `error-unexplained` finding |
| HELP-11 | Help is written in simple formal Arabic (see section 4) | `af_guide check --release` is clean and a browser test of the language switch |

### Privacy and support
| Control | Rule | Checked by |
|---|---|---|
| PRIV-01 | Two recorded agreements (installation, then each person); withdrawable any time | consent records in the product DB; first-sign-in browser test; tracking is off until both agree and withdrawing purges the person's rows |
| PRIV-03 | Events carry only allowlisted ids, counts, durations and booleans (see section 2) | `packages/af-telemetry` firm-limit tests with the vendored taxonomy, which must be byte-identical to the factory copy |
| TEL-01 | Events wait in a bounded offline outbox; telemetry never slows or fails the program | outbox tests; the program works with the network unplugged |
| FB-01 | Every page offers «أبلغ عن مشكلة» with a full preview of what will be sent | browser test of preview then send; a text changed after preview is refused; redaction tests |

**Looking up a control or an old id:** `python3 scripts/factory.py controls <ID>`. A merged id prints "merged into …" and a dropped one prints "retired: …". Old ids are also accepted in manifests.

## 2. Firm privacy limits
These are enforced in code and tests, not by habit.
- **Consent first.** Nothing about a person is recorded until the installation owner and then that person agree. A decline means zero events. A problem report works without consent.
- **Never collected:** passwords, keystrokes or typed text, screenshots, names, phones, national ids, e-mails, addresses, amounts, or full customer, student or money records.
- **Only ids and counts:** short machine ids (page, action, guide, error code, fingerprint), counts, durations and true/false values, from the one taxonomy in `packages/af-telemetry/events.json`. Any other field raises `PrivacyError`. A product that needs a new event type adds it to the factory taxonomy, never to its own copy.
- Credentials and personal data never go into source, logs, screenshots, public issues or fixtures.
- Vendor support is not an admin backdoor: it is customer-approved, scoped, time-bound, audited, revocable and off by default. Never publish `admin/123` or any static production credential.

## 3. The agent workflow (non-negotiable)
1. State the customer, the core pain and acceptance criteria that can be checked. Label unknowns **UNKNOWN**.
2. Inventory what exists before building (`docs/knowledge/README.md`). Reuse a versioned shared part; product-specific code stays in the product.
3. Get cited market evidence and a product manifest. Business choices that change price, sensitive data or who bears risk need recorded owner approval (see `DECISIONS.md`).
4. Pick one commercial package if for sale (Solo, Connected, Mobile Operations, Cloud Business), independently from the deployment and connectivity tier (`standalone`, `office_server`, `office_mesh`, `cloud_sync`, `cloud_only`). Use globally unique ids and org/branch scope from the first schema. Turn on only the controls that apply.
5. Deliver one thin customer workflow end to end: permissions, save and retry, errors, audit, report, recovery.
6. Test: unit, integration, role-denial, rollback, backup and restore, browser UI in Arabic and English (RTL), keyboard use, the target OS installer where it applies.
7. Work through a PR with CI and a small safe merge. Never force-push or mass-merge divergent branches. Preserve existing customer data and working design; audit an existing product before changing it.
8. Report honestly: what changed, the commit or PR, the tests actually run, the checks skipped, the field checks still pending. Status words are `planned` → `implemented` → `verified` → `field_accepted`; none may be skipped. Passing CI is not "ready to sell".
9. Claim no certification (tax, medical, payments, ISO) without independent evidence for that scope.

## 4. Arabic standard in brief (HELP-11)
Write help in **simple formal Arabic**, «العربية الميسّرة»: correct Arabic between Modern Standard and polite Egyptian, a 12-year-old understands it. Everyday words, one action per step, 0-9 digits, no technical words, and button names exactly as the screen shows them. Guides exist in every product language with a per-person switch that does not change the app language. The factory style lint runs in `af_guide check --release` and its warnings block a release; a non-developer does a reading pass each release. Details: `docs/HELP_AND_GUIDANCE_STANDARD.md`.

## 5. Never
Hand-written cryptography; signing keys in a repository, CI or customer build; customer data inside the program folder; an installer or uninstaller that deletes customer data; several PCs writing one SQLite file over a network share; synced replicas treated as backups; asking customers to disable antivirus or install our root certificate; AI agents with shell or SQL access to customer machines.
