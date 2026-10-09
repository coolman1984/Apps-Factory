# Apps Factory | مصنع التطبيقات 🏭

**Version:** 0.12.0 — three activation types (14-day trial, 30-day subscription, and perpetual code); 0.11.0 was the docs diet: 5 living docs, archive; 0.10.1 was help docs fitted to the new catalogue; 0.10.0 was the rules cleanup (32 core controls are the only release gate, the rest is advice); 0.9.0 was telemetry hardening; see [CHANGELOG](CHANGELOG.md) • **Status:** standards, specs and tested shared pieces; first product built on them: [الستور](https://github.com/coolman1984/Store). Nothing here is field-verified yet.

مستودع القواعد الموحدة اللي كل تطبيق تجاري جديد عندك يبدأ منه: بحث السوق، تصميم ثابت، إدارة وصلاحيات، اشتراكات وتراخيص، خصوصية، أمان، بيانات، نسخ احتياطي، اختبار، تشغيل ودعم. **التخصص فقط بيتغير، القاعدة لا تُنسخ عشوائيًا.**

## What it is
One repeatable process for building and selling small commercial apps (desktop, office network, or cloud), run by a 1–3 person team:
a catalogue of controls and a manifest schema (`factory/`), a CLI that checks them (`scripts/factory.py`), and tested shared parts that products copy in.
A feature has one status: `planned` → `implemented` → `verified` → `field_accepted`. A written rule is not a working feature.

## The five living docs
| Doc | Read it for |
|---|---|
| [README.md](README.md) | What the factory is and the commands (this file) |
| [RULES.md](RULES.md) | The 32 core controls and how each is checked, the firm privacy limits, the agent workflow, the Arabic standard |
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
