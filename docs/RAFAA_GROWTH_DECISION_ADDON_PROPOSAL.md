# رَافِعة | Pixel Plus growth and readiness add-on (Egypt-first)
**Status: PRODUCT PROPOSAL, not implemented or cleared for commercial branding.** Owner request 2026-10-09. Working name is **رَافِعة** (“Grow your business on a solid foundation”). No trademark/domain clearance. No final prices, tax accuracy certification, automated government filing or perpetual maintenance commitment has been approved.

## What problem we solve
A one-to-three-person shop/small company cannot afford a CFO, dedicated FP&A analyst, purchasing team and continuous manual reporting, and doesn't need an enterprise ERP. Provide **owner-facing warning → traceable explanation → safe what-if → accountable action** powered by existing transactions, with role-specific accounting depth. Avoid promising to replace a licensed accountant or lawyer, predicting disasters with certainty, or that the app guarantees tax compliance.

## Product packaging: independent of Windows/cloud transport tiers
- **رادار رافعة**: a small INCLUDED experience in every applicable product, subject to real data availability: three explainable operational/financial alerts or metrics, data-quality warning, one non-destructive scenario using a synthetic company, entry inside Guide/Practice and a non-intrusive upgrade offer. Do NOT hide existing paid-core reports or essential safety warnings.
- **رافعة الكاملة**: an **optional expansion add-on**, bought either by monthly subscription or perpetual device/installation licence. Seven panels: Owner command room; accountant & month/quarter/year close; tax/compliance handbook; suppliers/procurement; cost & product margin; customers/receivables and payables; budgets/forecast/scenario planning.
- **Perpetual means perpetual access to purchased local functionality**, not free unlimited future content reviews, online services, support or regulatory updates. One year of maintenance/rules updates is a possible offer, then optional transparent renewal (subject to approved price). If legal rules are outdated, indicate dated references/staleness and avoid definitive recommendations. Expired subscriptions never block customer read, export or backups.
- Pricing is not approved: a market hypothesis for interviews is EGP 690/month or EGP 14,900 one-time for the full module. Validate with actual Egyptian SMEs, shop owners and accountants first. Base Store tiers Solo/Connected/Mobile Operations/Cloud Business remain separate.

## Competitive findings, October 2026 (NOT a unique feature claim)
- Wafeq Egypt officially displays Starter EGP 966, Plus EGP 1,386, Premium EGP 2,490 per month on monthly billing, with discounts for annual payment: https://www.wafeq.com/ar-eg/pricing
- Daftra advertises three US$20/35/50 monthly plans in one public regional offer, accounting/stock/purchasing/COGS/aging/tax forms: https://www.daftra.me/plans
- Odoo advertises one app free; Standard starts US$24.90/user/month on annual billing, all-app bundles: https://www.odoo.com/ar/pricing
These products already cover accounting and purchase workflows. DIFFERENTIATION must be proved in **predictive but transparent risk alerts, explainable what-if decisions, scenario-to-action, Egyptian legal rule sources, and easy offline shop-first UX**, not inflated feature-count claims. Verify regional prices, limits and effective dates again before quoting to customers.

## Egypt tax and compliance rulebook
Official references, NOT automated legal rulings:
- Law 6/2025: simplified regime for eligible entities with annual turnover not exceeding EGP 20m, income-tax turnover bands 0.4–1.5%; eligibility also depends on joining and satisfying conditions. https://www.eta.gov.eg/sites/default/files/2025-02/law_no.6.of_.2025.pdf
- Decision 420/2025: simplified sales/purchase daily journals, tax summary, fixed-assets and raw-material-stock registers, electronic invoices/receipts as applicable. https://www.eta.gov.eg/ar/news/qrar-wzyr-almalyt-rqm-420-lsnt-2025
- VAT general registration threshold EGP 500k with activity-specific exceptions; NEVER use turnover alone to assert registration obligation: https://www.eta.gov.eg/ar/node/1379
- VAT/income/procedure changes 149, 150, 151/2026 are listed by ETA and have separate scopes/validity dates: https://www.eta.gov.eg/ar/content/qwanyn-aldrybt-ly-alqymt-almdaft and https://www.eta.gov.eg/ar/content/qwanyn-aldrybt-ly-aldkhl
- E-invoice vs e-receipt requirements vary by customer type and enrollment: https://www.eta.gov.eg/ar/taxonomy/term/111
- Simplified regime benefits may require actual e-invoice/e-receipt compliance: https://eta.gov.eg/en/node/1344

Every legal rule must carry: official source URL, issuer, exact law/decision/article, publication date, effective dates, entity type, turnover/sector applicability, exceptions, rules-engine version, human reviewer, test examples, last verification date. **Rule updates go through expert review and signed/versioned tested release**; NEVER train/prompt an agent and silently deploy a new binding tax rule. Make drafts, checklists and evidence bundles; never claim actual declaration filed or approved without authenticated official receipt. Complicated disputes, filings and certified advice require an accredited specialist, and the product must make this boundary clear.

## Reuse existing code; do not duplicate accounts
- Accounting-sys / Mizan already has double entry, year/period close, statements, AR/AP, Treasury/Bank, Tax, Inventory, Cost Centers, Budgets, variance analysis, 13-week cash forecast, analysis and purchasing. It is the FINANCIAL source of truth for posted GL, period lock and tax reconciliations.
- Store remains the OPERATIONAL source of truth for receipts, serials, cash drawer, returns, sales and inventory movements. It must not start a second independent accounting ledger or delete posted money/stock.
- RAfaa is a **read-first decision/analysis layer** with explicit source links, formula and completeness metadata. Integrate Store and Mizan through a versioned local data contract/import/verified event stream with stable idempotency IDs, careful account mapping and no repeated posting on retries. Python and Node engines must reconcile against common hand-worked synthetic accounting fixtures, not duplicated hidden logic.
- HR supplies only aggregated approved payroll costs with role-scoped access, never a full employee-payroll dataset to all managers.
- A Store-only customer sees operating margins and alerts with a “not a complete accounting statement” label, not a fabricated balance sheet.
- Local/Windows offline computations are first; never mandate a permanent paid server just to show financial alerts.

## User-facing minimum core, experiment in practice/demo first
1. **Owner:** 3 cards (cash-runway, collectible overdue amount, slow/under-margin stock) based on real available data. Clear “not enough data” when necessary.
2. **Manager/accountant:** click underlying business event, see cause, source, period, assumptions; restricted permissions server-side.
3. **What if:** simulate a 10-day collection change, 5% price decrease or new purchase without posting ANY money/order, with base/pessimistic/optimistic scenario.
4. **Guide:** three isolated practice challenges: avoid cash crunch, explain profitable-vs-cash mismatch, close a synthetic month. Never touch production data or send external notifications; deterministic scenario success checked against real sandbox records.
5. **Upgrade:** honest comparison of INCLUDED vs full. No false scarcity and no paid plans advertised as active until release accepted.

## Full panels with acceptance boundaries
- **Financial close:** reconciliation list, missing-docs tracker, journals/tax period preview, permissioned approval, immutable posted entries with reversing entries; real monthly/quarter/year checks and rerun reproducibility.
- **Taxes:** eligibility question flow, effective-date-aware annotated source, electronic document checklist, preflight warning; no automatic tax filing or legal advice.
- **Purchasing:** landed cost, supplier due, real price/quantity terms, stock lead time, impact on expected liquidity; explicit approval before any purchase.
- **Finance planning:** cash forecast 13 weeks, annual budget, price/volume/mix/variance, break-even and scenarios with a confidence/assumption display; no hallucinated forecasts with little data.
- **Debts:** AR/AP aging, history, forecast vs due dates, alerts to manager, no automatic outbound collection communications.
- **Owner dashboard:** actionable prioritized warning list that links directly to records and does not allow write-by-AI.
- **Costs:** per-product/customer/channel profitability and cost centers, separations of cashflow, gross margin, contribution margin and net profit. Do not collapse them.

## Delivery in narrow PRs, never delay Store's first paid shop
P0: product-brief, source mapping and customer interviews (10 shop owners + 5 accountants + 3 purchasing/small-firm decision-makers). Pilot priority is genuine improvement, not promising all features.
P1: reusable FREE alert contract + test data + three cards in Store without changing cash-only selling; role checks and browser/Windows evidence.
P2: two-way source reconciliation research, implement minimal deterministic read-only analytical adapter from Store to Mizan where appropriate; clean-PC regression and no duplicate accounting post.
P3: Full RAfaa first paid differentiator: cashflow/receivable/purchases scenario, owner/accountant modes and month-close checklist.
P4: signed legally reviewed Egyptian rules module and period/record scope, assessed by competent tax professional; business-owner approval for price and ongoing reviews.
P5: adopt in other products only where underlying data support truthful claims.

Each stage must show recorded source-to-screen mappings, actual browser clicks and before/after screenshots, server role enforcement, cross-ledger balance test, negative tests, backup/restore, mandatory Windows installer CI and field proof. No fabricated test pass, no deployment/payment without owner approval.

**Decision gate:** owner must approve brand/legal clearance, paid tiers, rules-review owner, hosting/storage budgets and sector launch. This file documents a proposed strategy; it is NOT a release-complete product.
