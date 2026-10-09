# Market benchmarks for repeatable commercial capabilities • checked 2026-10-08

**Purpose:** benchmark the platform behaviors that buyers expect. These are not competing products for one specific sector and do not establish market size/prices. Sources are vendor first-party documentation. Recheck before quoting.

| Product/platform | Verified behavior from vendor | What Apps Factory should standardize | What NOT to copy blindly |
|---|---|---|---|
| [Odoo 19 — users/rights](https://www.odoo.com/documentation/19.0/applications/general/users.html) | Admin invites users, grants per-app access, company membership, recorded signed-in devices / revocation; seat changes affect subscription | Modular access matrices, active session revocation, multi-organization option, seat entitlement warnings | Overwhelming ERP menu in a 1-person SME app |
| [Odoo — multi company](https://www.odoo.com/documentation/19.0/applications/general/companies/multi_company.html) | Company selector and shared vs restricted records, multi-company plan gating | Branch/company scope at record/report level | Assume multi-company needed in each product |
| [Zoho Creator — plans/features](https://www.zoho.com/creator/pricing.html) | Portals with permission sets, roles, MFA, audit trails, backups and developer environments documented by plan | Separate internal users vs outside portal, clear feature tiers, audit and backup | Treat a feature's premium-plan presence as proof every customer needs it |
| [Daftra — getting started](https://docs.daftra.com/en/tutorial/how-daftra-works-and-where-to-start/) | Guided setup for company, logo, currency, language/timezone, app manager, branches and user roles | Localization, setup wizard and activatable activity modules for Arabic-first SMEs | Import Daftra's domain billing/accounting complexity into a non-finance tool |
| [Daftra — branch permissions](https://docs.daftra.com/en/tutorial/configuring-and-setting-up-branch-settings/) | Company branches, branch-specific records, shared catalog options, authorized employee branch selection | Org/branch data and export isolation; opt-in sharing controls | Copy their exact branch permission model without local customer testing |
| [Daftra — role granularity](https://docs.daftra.com/en/tutorial/%D8%B6%D8%A8%D8%B7-%D9%88%D8%AA%D9%87%D9%8A%D8%A6%D8%A9-%D8%A5%D8%AF%D8%A7%D8%B1%D8%A9-%D8%A3%D8%AF%D9%88%D8%A7%D8%B1-%D8%A7%D9%84%D9%85%D9%88%D8%B8%D9%81%D9%8A%D9%86/) | Role restrictions by app and selected resources, branch and separate own/all patterns | Explicit per-object/server permission tests | Copy marketing claims as security proof |
| [Odoo — portal](https://www.odoo.com/documentation/19.0/applications/general/users/user_portals.html) | External customer/supplier portal with limited document/payment access | Separate customer portal roles from admin users | Ship portal in offline one-PC apps unless customer requires |
| [Daftra — sectors/modules](https://www.daftra.com/en/features/all_features/) | Activatable sales/accounting/inventory/HR/CRM/industry workflows | Modular business recipes chosen after real buyer research | Build whole ERP before confirming a paid vertical slice |

## What this means for our product factory
A solid commercial **platform baseline** is users and scopes, core settings, feature entitlements, export/backup/recovery, audit/support, app modules and localization. The universal shell is a quality expectation; domain pages remain researched per buyer. Regional accounting/tax/e-invoicing/healthcare/schools are extensions requiring qualified domain/legal validation.

## Market research discipline for each *new* product
1. Find at least five relevant alternatives (including Excel/manual workflows) in the chosen **sector**, not five generic platforms.
2. Document actual feature + current price + currency + billing unit + date + terms, or `UNKNOWN` when vendor hides prices.
3. Interview real users; prioritize the shortest valuable paid workflow.
4. Distinguish **market feature parity** (needed) from **competitive differentiation** (why buy from us).
5. Record sales/onboarding/support cost, time and risk rather than racing to max screen count.

This benchmark is distinct from the repository audit and does not certify implementation.
