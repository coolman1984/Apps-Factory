# Pixel Plus Apps Factory — company execution roadmap
Owner direction captured: 2026-10-09 · **Source of truth for sequencing, not a claim of delivery**
Audience: owner, independent reviewer, coding agents, product/sales/support.

## Mission and market guardrails
Pixel Plus builds local-first, secure, understandable applications for **individuals, Egyptian shop owners, small and medium businesses**, with optional expansions they can afford. **Sanad Business Advisory** collaborates on consented client advisory, finance operations and business improvement (commercial agreement pending Sunday 2026-10-11). Simple modular software, tiny hosting budgets, Windows-first, Arabic-first, realistic field demos. No enterprise-server architecture, no unnecessary monthly infrastructure, no shared real/demo DB.

Business flywheel: **show authentic product → guided fake-data trial → first locally installed 14-day trial → owner-approved activation via Telegram → usable core product → optional operational tier upgrades → optional Rafaa decision add-on → optional Sanad human advisory → renewal/referrals**. Any step may be purchased separately. Never auto-charge or auto-contact prospects.

## Existing assets and truth as of 2026-10-09

| Asset | Existing evidence | NOT yet proven |
| --- | --- | --- |
| Store 1.5.0 | trial/monthly/perpetual device codes, cash register, practice shop, role guide, Windows CI install/upgrade | pilot field acceptance; cloud backup; bot-approval automatic activation |
| Factory 0.12.0 | 32 factory checks, Windows contract CI, af-license, owner-only Licence Studio, Control Center Telegram outbound implementation | live production deployment of relay/Control Center, bot inbound approvals, key custody field proof |
| Store first commercial offer | Solo PC/cash-only pilot, offline data and tested local copies | encrypted automatic off-PC cloud backup and restore for marketed Solo tier |
| Guided demo | Store practice shop and af-guide, Pixel Plus showroom roadmap | embedded role-based Demo Mode entry + isolated browser-hosted public sandbox |
| Four commercial infrastructure plans | agreed plan definitions in docs/SMB_COMMERCIAL_TIERS.md | functional tier-2/3 sync/mobile operations or tier-4 hosted service |
| **Rafaa** expansion | proposed market research and existing Accounting-sys modules (GL, AR/AP, analysis, cost centers, budget, cash forecast) | cross-product adapter, owner radar, signed tax rulebook, customer-validated paid offer |
| Pixel Plus + Sanad | owner stated collaboration and supplied page identities, Sanad business advisory focus | signed service/revenue agreement, data-sharing scopes, approved package/prices and company contact details |

Current PRs/anchors: Factory #35 (Rafaa proposal, merged), Factory #32 (public demo roadmap, merged), Store #11 (1.5.0, merged), Factory #31 (0.12.0, merged). Store #13 is an **open docs-only** demo roadmap at time of planning; inspect live PR state before doing implementation. Do not assume it merged. All implementation checks require fresh exact commit proof.

## Two independent commercial axes — DO NOT confuse them
A) **Infrastructure plans** in [SMB_COMMERCIAL_TIERS.md](SMB_COMMERCIAL_TIERS.md):
1. Solo = one offline-capable Windows PC + independent encrypted, recoverable off-device cloud backup (pending, never call it delivered yet);
2. Connected = multiple PCs synchronized via protected hub + **owner-only read-only mobile view**;
3. Mobile Operations = authorized mobile staff sales, barcodes, stock, multiple users;
4. Cloud Business = hosted-first web/app/Windows access.
B) **Optional business-value modules/services**, never an infrastructure tier:
- Rafaa Radar: free, 3 explainable metrics/alerts per applicable product when underlying records permit, role-limited;
- Rafaa Full: paid monthly OR perpetual local licence, actionable budgeting, close, taxes, receivables/payables, purchasing, costs, 13-week cash forecasting and what-if;
- Sanad Advisory: independent human finance, management, tax-review or growth service under a separate consented agreement.
Client can have e.g. Solo + Rafaa Full with no Sanad advisory; can upgrade one axis without forcing upgrades in the other.

## Prioritized phases (one small PR each; no parallel conflicting edits)

| Order | Deliverable | Measurable acceptance | Stop/go |
| --- | --- | --- | --- |
| P0 NOW | Freeze & verify Store 1.5 pilot, resolve review findings | Windows installer green on PR + main; no licence/data regression; first second-PC restore, physical receipt printer and keyboard/cashier trial still explicitly pending | Never mark paid-sale-ready before field proof |
| P1 | **Telegram-approved, near-instant activation end to end** using current af-license, Licence Studio, Control Center and small relay | One Store click → owner's private Telegram approve/deny → trusted unlocked Studio generates signed device-bound 14-day code → Store fetches and verifies and activates → both see result; negative and offline/manual tests green | Needs approved bot/owner chat, secret placement, operator online/unlock, safe new-install enrolment; no public deployment before consent/cost/security |
| P2 | Solo resilient off-PC **encrypted backup**, before advertised Solo sale | real SQLite-safe snapshot; encrypted versioned separate storage; retry queue/overdue alarm; key recovery; clean second-PC restore; test corruption/offline/rotation | Storage provider/region/budget/key recovery require owner approval |
| P3 | App-wide **click → code → server → permission → DB → visible result** quality audit & regression suite | exhaustive route/button coverage inventory; screenshots/DOM/HTTP/DB evidence for critical journeys; independence from implementing agent; PC/mobile layouts, AR/EN and roles; every bug reproduced then repaired; no false skipped-green | Release checks + human Windows field steps |
| P4 | Store **Demo Mode inside Guide** | isolated practice DB, genuine sale/stock/returns challenge + reset; no writes or messages to production, free exploration/role guide, tests | Reuse af-guide/practice; public full web demo later |
| P5 | Pixel Plus static **product showroom** | site pages with real brand, genuine screen media, clear available vs planned tiers, consented quote/lead funnel; approved domain/contact | No fake “try live” until sandbox exists; keep host cost minimal |
| P6 | **Rafaa Radar** in Store, then one more product | 3 explainable real-data alerts, role gated, links to source events, safe decision simulation in practice; no duplicate GL | Accounting-sys ledger authoritative for financial statements |
| P7 | **Rafaa Full** and Sanad advisory referrals | first forecasting/closing/purchasing/AR-AP features with checked numbers, signed/licensed module, accountant test cases, source-dated Egypt tax guidance with expert review | Pricing, legal validation/maintenance terms and owner sign-off |
| P8 | infrastructure tier 2→3→4 and public isolated demo | only proven features, load/security tests, tenant isolation, unit economics, real customer demand | No premature server per customer or giant platform |

For faster cashflow P0 field pilot can proceed in parallel with design-only work, but never share production source branches with an unreviewed agent.

## Product discovery and packaging
- First paid core Store journey stays **cash-only**, easy installation, no internet needed for POS. All advanced payments are opt-in at shop settings; nothing destroys historical stock/financial rows.
- Public product page: clear pain + real demo/screenshots + role use cases + truthful four plans + optional Rafaa + optional Sanad; accessible Egyptian Arabic, mobile-first.
- Demo/Guide: buyer experiments on synthetic records, creates/edits/reverses transactions, solves realistic seeded problems, safely resets, may request trial. Data must be truly isolated and sessions bounded; no real outbound actions.
- Pricing: not approved yet. Rafaa EGP 690/mo and EGP 14,900 one-time are **interview hypotheses**, not offers. Perpetual grants purchased local functionality forever; evolving tax guides/cloud/support are separately described maintenance or subscription with clear update policy.
- Only publish verified claims. All new product capabilities use **planned → implemented → verified → field_accepted**. A document is always `planned`.

## Egypt-specific compliance
Rafaa tax/legal reference uses official ETA sources, cites exact law/decision/article, effective period, eligibility/exception and review date; local tax/accountant review before publishing any new binding rule. AI explains facts and estimates, **never asserts filing success**, tax eligibility, or professional replacement. Customer export/backup always works after licence expiry. No secret customer records or raw payroll to public AI/marketing.

## Pixel Plus × Sanad service bridge
- Pixel Plus owns code/IP/licensing/install/update/security, technical support, product analytics under consent, and its own product promises.
- Sanad contributes separately ordered **human** operational/business advisory: process reviews, monthly close guidance, finance planning, purchases, HR, tax coordination and growth coaching, with clear assigned professional responsibility.
- No default sharing of a client’s sales, payroll, supplier, tax or contact data across firms. Customer explicitly chooses whether to request Sanad support; disclosure is scoped, revocable, time-limited, audited, and ideally summary/report-only. Use least privileged human access, separate org roles and written terms.
- Show opt-in service request within suitable product pages and client application; never auto-create paying subscriptions; track leads as new/contacted/demo/quote/pilot/paid with consent.
- **Open until owner explains on Sunday 2026-10-11:** packages/tiers, which company invoices whom, referral percentages, data controller roles, professional accountability, legal contract, brand usage, refund/SLA and whether advisers can see live data. Do not invent or implement these terms.

## Agent execution and verification
1. Fresh independent review agent on a clean main-derived audit branch across relevant repos; implementation agent on **another** short-lived branch. Reviewer neither signs off its own fixes nor skips conflicts.
2. Inspect source map and actual browser application, compare each clickable control to request, server permission and mutation; record screen before/after, network status, row/state delta and error cases. Test with synthetic records, log no private data.
3. Write narrowly scoped acceptance criteria and failing tests first, use pinned dependencies, run both languages/roles and real hosted Windows build; do not waive pending/failed checks or auto-merge without green PR validation.
4. Shared package changed in Factory first, bump version and vendor via official script, then product PR with drift check. No modifying vendored parts by hand.
5. Stage output: PR/commit IDs, evidence, pass/fail/skipped, screenshots, real hardware/customer blockers, privacy/cost and decisions required.
6. Only after no conflicts + all expected checks green can changes be merged. Update this living roadmap after each launch milestone; no uncontrolled cross-repository mass merge.

## Critical references
- [Telegram activation protocol proposal](TELEGRAM_APPROVED_ACTIVATION.md)
- [Partner/service boundary](PIXEL_PLUS_SANAD_PARTNER_OPERATING_MODEL.md)
- [Rafaa market-backed proposal](RAFAA_GROWTH_DECISION_ADDON_PROPOSAL.md)
- [Pixel Plus public demo roadmap](PIXEL_PLUS_EXPERIENCE_ROADMAP.md)
- [SMB sales tiers](SMB_COMMERCIAL_TIERS.md)
- [Existing Control Center and patch/Telegram design](CUSTOMER_PATCH_PIPELINE.md)
- [Factory 32 controls](../RULES.md) and [Factory execution playbook](../PLAYBOOK.md)
