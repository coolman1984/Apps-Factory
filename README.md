# Apps Factory | مصنع التطبيقات 🏭

**Version:** 0.16.0 — the trial length is a per-product setting (14 by default; Licence Studio 1.3.0; Al-Store 1.9.1); 0.15.1 — the Telegram chat id, stale approvals, unknown relay requests, stale copies and the Studio's click no longer waits for the network; 0.15.0 — design gates are core (UX-04 states by connectivity tier, UX-09 tokens; 34 core controls), the Store is no longer named after Mizan, the Licence Studio counts the agent's trial limits under the write lock and recovers half-made decisions safely; 0.14.1 — af-guide 0.1.3 and af-consent 0.1.1: the word «null» no longer appears in the guide's coach or in Settings → Privacy; the Licence Studio recovers a request left half-decided by a shut-down PC; 0.14.0 — the owner's «✅ موافق / ❌ رفض» buttons on Telegram (relay webhook; Licence Studio 1.2.0 signs on the owner's PC and sends the owner a copy of the code; tested against a fake Telegram, not deployed); 0.13.0 — licence mailbox on the telemetry relay with a Telegram alert to the owner, Licence Studio 1.1.0 (owner-controlled trial policy, defaults unconfirmed and off, payment gate), Pixel Plus website requirements, Al-Store 1.6.0 / 1.7.0 evidence; 0.12.0 — af-license 0.3.0 (permanent codes) and the Studio's three code kinds, Al-Store 1.5.0 evidence; 0.11.3 — mandatory Windows CI contract + four lean business plans (roadmap, not sync implementation); 0.11.2 — af-guide 0.1.2 (no «null» on the guide button), Al-Store IAM-01 verified; 0.11.1 recorded Al-Store evidence per core control; 0.11.0 was the docs diet: 5 living docs, archive; 0.10.1 was help docs fitted to the new catalogue; 0.10.0 was the rules cleanup (32 core controls are the only release gate, the rest is advice); 0.9.0 was telemetry hardening; see [CHANGELOG](CHANGELOG.md) • **Status:** standards, specs and tested shared pieces; first product built on them: [الستور](https://github.com/coolman1984/Store). Nothing here is field-verified yet.

مستودع القواعد الموحدة اللي كل تطبيق تجاري جديد عندك يبدأ منه: بحث السوق، تصميم ثابت، إدارة وصلاحيات، اشتراكات وتراخيص، خصوصية، أمان، بيانات، نسخ احتياطي، اختبار، تشغيل ودعم. **التخصص فقط بيتغير، القاعدة لا تُنسخ عشوائيًا.**

## What it is
One repeatable process for building and selling small commercial apps (desktop, office network, or cloud), run by a 1–3 person team:
a catalogue of controls and a manifest schema (`factory/`), a CLI that checks them (`scripts/factory.py`), and tested shared parts that products copy in.
A feature has one status: `planned` → `implemented` → `verified` → `field_accepted`. A written rule is not a working feature.

## Pixel Plus one-person company operating system (research 2026-10-10)

**New strategy:** [one-person company architecture, Council, agent roles, security and measured automation](docs/PIXEL_PLUS_ONE_PERSON_COMPANY_OS.md) and [practical workflow/30-day operating playbook](docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md). **Status: proposed operating architecture, not a running autonomous dispatcher.** A small separate offline Python/SQLite demonstration exists outside the repository; production agent connectors, Telegram approvals, spending, and publishing are NOT live through it. The founder remains the final authority for risky/external actions. No additional factory core controls or product dependencies are added.

## Pixel Plus company execution map (owner direction 2026-10-09)

**Start with [the single prioritized execution roadmap](docs/PIXEL_PLUS_EXECUTION_ROADMAP_2026.md).** It connects the latest customer-sales strategy, Store's first paid-shop gate, Telegram owner-approved activation, guided Demo Mode / public product showroom, the four distinct infrastructure plans, **Rafaa** (included small radar vs optional paid finance/growth module) and the Pixel Plus × Sanad Business Advisory consented service model.

- [Owner-approved Telegram activation](docs/TELEGRAM_APPROVED_ACTIVATION.md): consented 14-day request → Telegram **✅ موافق / ❌ رفض** buttons → a **trusted local Licence Studio signs** → only requesting Store receives and locally verifies the signed code; the owner gets a copy for the phone readout. **Implemented (0.14.0) and tested against a fake Telegram; not deployed, not field-verified.**
- [Rafaa financial-growth add-on proposal](docs/RAFAA_GROWTH_DECISION_ADDON_PROPOSAL.md): accounting, purchasing, taxes, closing, cost/FP&A and decision simulation on top of Accounting-sys, *not* a duplicate Store ledger. Name/price/claims require validation.
- [Pixel Plus × Sanad partner/service plan](docs/PIXEL_PLUS_SANAD_PARTNER_OPERATING_MODEL.md): two independent companies, opt-in advisory, no automatic customer-data sharing. Pricing, roles and commissions await owner briefing 2026-10-11.
- [Interactive practice and public showroom](docs/PIXEL_PLUS_EXPERIENCE_ROADMAP.md): safe synthetic demo inside Guide, later authentic isolated website trials; **planned**, not launched.

These are **strategic reference specifications**, NOT executable features, a paid cloud deployment or evidence of any customer acceptance. Factory's five living operational docs below remain unchanged.

## The five living docs
| Doc | Read it for |
|---|---|
| [README.md](README.md) | What the factory is and the commands (this file) |
| [RULES.md](RULES.md) | The 34 core controls and how each is checked, the firm privacy limits, the agent workflow, the Arabic standard |
| [PARTS.md](PARTS.md) | Each shared part: version, how a product copies it, its spec, who uses it |
| [PLAYBOOK.md](PLAYBOOK.md) | Run the tests, check vendored copies, release, add a control or a product, alerts |
| [DECISIONS.md](DECISIONS.md) | Dated owner decisions, the ADR index, what is still open |

Agents start at [AGENTS.md](AGENTS.md). Detailed specs stay in [docs/](docs/) as reference specs (linked from PARTS.md); research and old plans are in [docs/archive/](docs/archive/README.md); reusable lessons and the capability map are in [docs/knowledge/](docs/knowledge/README.md).

## Commands
```bash
python3 scripts/factory.py doctor                                   # catalogue and schema are consistent
python3 scripts/factory.py new --id my-app --name "اسم البرنامج" --mode lan --market EG --output my-app.json
python3 scripts/factory.py check my-app.json                        # validate a draft manifest
python3 scripts/factory.py check my-app.json --release              # sale-readiness gate: fails drafts on purpose
python3 scripts/factory.py controls HELP-03                         # look up a control or an old id
python3 scripts/factory.py guide <product>/guide --release          # check a product's guide (af-guide)
python3 -m unittest discover -s tests -v                            # factory tests
```
Higher tier example: add `--tier cloud_sync --sites multi --clients windows_desktop,browser,mobile_pwa --multi-owner`.
The release gate is the applicable **core** controls plus two proofs: restore on a clean device, and first-customer acceptance. Reference controls are advice.
There is also a local page that builds a manifest: [CONTROL_CENTER.html](CONTROL_CENTER.html) (it sends nothing anywhere).

## Packages and tools
| Part | What | Details |
|---|---|---|
| [af-access](packages/af-access/README.md) | People, profiles, pages, permissions gate | [PARTS.md](PARTS.md) |
| [af-license](packages/af-license/README.md) | Signed licences and device-bound codes | [PARTS.md](PARTS.md) |
| [af-guide](packages/af-guide/README.md) | Guided onboarding in simple formal Arabic | [PARTS.md](PARTS.md) |
| [af-consent](packages/af-consent/README.md) | Two-level consent | [PARTS.md](PARTS.md) |
| [af-telemetry](packages/af-telemetry/README.md) | Ids-and-counts telemetry and problem reports | [PARTS.md](PARTS.md) |
| [af-ui](packages/af-ui/README.md) | The Showroom design system | [PARTS.md](PARTS.md) |
| [apps/control-center](apps/control-center/README.md) | Vendor Control Center (برج المراقبة) | [PARTS.md](PARTS.md) |
| [apps/licence-studio](apps/licence-studio/README.md) | The owner's licence-code program | [PARTS.md](PARTS.md) |
| [tools/ui-lab](tools/ui-lab/README.md) | Performance and accessibility gate | [PARTS.md](PARTS.md) |
| [design-factory](design-factory/README.md) | المصنع البصري: tokens, labs, creative lab and visual QA | [design-factory/AGENTS.md](design-factory/AGENTS.md) |

## Customer-facing plans (commercial, NOT proof of implementation)
**Four business plans:** 1 Solo (one Windows PC + local and off-device encrypted cloud backup); 2 Connected (multi-PC sync + owner read-only installed mobile view); 3 Mobile Operations (phone sales/barcodes and staff permissions); 4 Cloud Business (hosted-first + Windows/mobile clients). See [four-plan commercial contract](docs/SMB_COMMERCIAL_TIERS.md). The plans are independent of the internal connectivity modes listed below; existing products do not become cloud-ready by adding a label.

**Every Windows-targeted paid release must have a green PR + main Windows installer/check and independent clean-PC restore proof.** See [Windows gate](docs/SMB_COMMERCIAL_TIERS.md#1-mandatory-windows-shipping-gate-for-every-windows-targeted-paid-product) and [PLAYBOOK](PLAYBOOK.md).

## Operating tiers (`connectivity.tier`)
| Tier | If the main PC is off |
|---|---|
| `standalone` | The program stops (one PC) |
| `office_server` | Other PCs cannot write |
| `office_mesh` | Every PC keeps working alone and syncs later (like حصّة) |
| `cloud_sync` | Every device works offline and syncs later; mobile, branches, several owners |
| `cloud_only` | Not relevant, but needs internet |

Rationale: [ADR-0001](docs/decisions/ADR-0001-architecture-and-connectivity-tiers.md) and [docs/CONNECTIVITY_AND_SYNC.md](docs/CONNECTIVITY_AND_SYNC.md). Windows without a signing certificate: [ADR-0004](docs/decisions/ADR-0004-windows-trust-without-certificate.md) and [the customer install guide](templates/CUSTOMER_INSTALL_GUIDE_AR.md).

## Start a product
1. Read [AGENTS.md](AGENTS.md), then [RULES.md](RULES.md) and [PARTS.md](PARTS.md).
2. Copy [the product brief](templates/PRODUCT_BRIEF.md) and [the competitor study](templates/MARKET_RESEARCH.md); choose `desktop`, `lan` or `saas`.
3. Create and check the manifest ([schema](factory/product.schema.json), [controls](factory/controls.json)); see [PLAYBOOK.md](PLAYBOOK.md) for the steps.
4. Do not write customer features before the buyer, the scope and the risks are agreed. A product is not ready to sell until it passes the release gate ([docs/DELIVERY_GATES.md](docs/DELIVERY_GATES.md) has the full working method).
