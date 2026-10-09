# Pixel Plus: learn-by-doing demos and product showroom
Owner-approved forward roadmap • 9 October 2026
Status: PLANNED. No website, hosted sandbox, or role-based challenge engine is claimed to exist.

## Why
Small-business buyers in Egypt need to **try before buying**, not read software manuals. Every product should teach each user their own job by using the real product's flows, with realistic synthetic mistakes and guided corrections. Pixel Plus's website should let a buyer experience the product, choose the right of four commercial plans, and contact the company with minimal friction.

**Non-goal:** Building a large SaaS platform, maintaining servers per visitor, creating a fake marketing UI that does not match the product, or delaying Al-Store's first paying shop.

## Product experience: two distinct demo routes

### A. Demo Mode inside Help / Guide (customer application)
- Permanent visible **Demo Mode / وضع التجربة** action on the Guide screen, available to all relevant roles (including a user who lost access to advanced actions), with a clear demo watermark and a return-to-real-app control.
- Use the same shipped UI, business rules, role enforcement and server routes on an **independent synthetic sandbox**. Never share a production SQLite file, real environment credentials, printer, payment terminal or backup target.
- On Windows one-PC applications, opening Demo Mode launches a separate *demo configuration and data directory/process*, not a flag that replaces the currently loaded shop's DB. The real app keeps serving its real records throughout; close demo without changing customer configuration.
- Two paths: (1) **Learn with a guide** and (2) **Explore freely**. Learner can create, edit, "delete", refund, fail validation, recover, and reset. Nothing they do changes real stock, payroll, customer records or balances.
- Tutorial progression: **Beginner** → **Practitioner** → **Advanced**. Roles: Owner, cashier/seller, stock clerk, supervisor, accountant, employee; display only roles a product actually supports. Steps start with a real task: 1) scenario, 2) user acts, 3) result explained, 4) a mistake to diagnose, 5) optional hint/show-me, 6) retry, 7) completion, 8) next task.
- Guides must observe *actual application state* to mark completion; do not give success for clicking Next. Provide optional skip/explain, safe reset of one exercise and full reset, with separate progress retained only when the customer enables it.
- Synthetic seeded businesses per sector with transparent amounts and business stories (never customer production data); support role change by issuing a new **demo-only** session with least permissions, not a hidden elevated production account.
- Keep Guide, Demo Mode, and training resources always reachable after license expiry, while protected business writes remain locked as existing licensing rules require.
- Never send emails, payment requests, WhatsApp, external notifications, printer jobs or real backup uploads from demo; all integration adapters must be no-op/fake in sandbox, with tests proving it.

### B. Public Pixel Plus website product showroom
Customer path: **Discover product → real guided demo → compare plans → request quote / installation**.
- Lightweight, fast, bilingual Arabic/English, responsive marketing website. Use Pixel Plus identity from the owner's verified original presentation/logo assets; do not invent or quietly replace logo, typography, colors or official domains. Reference: `Pixel_Plus_Arabic_Flagship.pptx` in owner's prior materials. Site/domain requires owner confirmation before deployment.
- Home: clear problem solved, trust without inflated claims, product catalogue, representative use cases, demos, 4 plan explanation, help articles/videos, contact.
- One page per product: who it is for, 60–90 sec genuine product walk-through, key capabilities/limitations, screenshots from the *actual* latest version, **Try live**, **Download Windows trial** (when released), **Compare plans**, **Ask for a quote**. No pretended certification, customer numbers or fabricated reviews.
- Share deep links to specific roles/lessons after genuine public sandbox is deployed; let curious buyers play without compulsory phone/email collection. Ask contact details voluntarily only when requesting an offer, callback or quote; double-check consent and privacy.
- Plans reflect existing Solo/Connected/Mobile Operations/Cloud Business evidence; never sell an unreleased tier, label future items "coming later". Each product may support only a subset.
- Sales lead intake: interest/product, plan, shop size, city, customer-supplied contact details, preferred follow-up and consent; avoid unsolicited WhatsApp automation. Show status (new → contacted → demo → quote → pilot → sale) in a lean CRM or spreadsheet, only on approved vendor side.
- Simple site hosting first: static assets / inexpensive metered functions, no cloud servers until necessary. A static site cannot execute Al-Store's Python server; public FULL live Al-Store demo needs a legitimately hosted isolated backend, with measured cost before approval. Do not falsely portray a screenshot simulator as a live demo.
- Session expiry 15–30 min after inactivity, cap sessions, CPU and storage, throttling, rate-limiting, auto-reset, kill/cleanup, per-session synthetic DB namespace; costs metered and budget alerts. Customer data, real vendor private keys, admin credentials and system network resources absent.

## Security boundaries and tests (mandatory before ANY public trial)
- Separate sandbox identity, DB/storage, encryption keys, backups and outbound integrations from real data; no shared production data volume or runtime privileged tokens; no demo user access to any real tenant.
- Restrict network egress and file uploads, validation, SQL paths and admin operations; prevent direct DB or system access; temporary demo data deletes on expiry.
- Negative test: demo cannot read/mutate production, demo A cannot read/mutate demo B, invalid role cannot issue refunds, blocked outbound side effects, true reset returns identical seeded state, expiring a session removes access, 100 parallel sessions obey quotas, unauthenticated uploads blocked.
- Mobile, Arabic RTL, desktop keyboard, browser crash recovery, help links, guide resume and real Windows launcher tested. The sample demo cannot contain real names, phones, salaries, addresses or customer/employee records.
- Consent-aware, aggregate analytics only: demo started, role chosen, exercise completed, abandon step, quote requested. No typed text or individual financial/customer records sent as telemetry.

## Pragmatic reuse (inventory first)
- Factory already has `af-guide` role guidance and browser walk-through tests; extend its spec, not copy its code.
- Al-Store already ships `--practice` and `practice.bat`: separate synthetic shop. Investigate whether existing Demo Mode UI can safely open it before adding one.
- `complete-company` has synthetic ceramic showreel; HR has demo onboarding; Atrium has example packs. Reuse patterns and authentic product screens, NEVER cross-copy databases.
- Shared **reference template** of scenarios and interface contract first; extract a versioned shared component only after TWO products adopt and pass regression tests. This is a post-pilot enhancement, not a new universal core release gate.

## Phased delivery and objective exit criteria
0. **Do not block current launch:** finish Store #11 and factory #31/release proof, existing clean-PC and cashier acceptance.
1. **Local Store guided practice pilot:** Demo Mode from Help opens independent existing practice shop; owner/cashier/stockholder lesson packs with at least 3 real problems; all CRUD actions and reset; a demo fails a real-data write automatically. Test all, include users' permission and Arabic/English.
2. **General factory recipe:** formalize scenario JSON contract, progress/checkpoint, reset/role switch, negative tests, plug into next product (Teachers/Hessa or Atrium) before making a new factory reusable package.
3. **Pixel Plus starter site:** static brand-verified page, 2–3 real product pages, catalog and contact/quote. Only real photos and videos initially; links to local demo download while public backend isn't ready. No online database, paid server or live-demos falsely advertised.
4. **One public live demo:** launch Store sandbox only after costs, deployment, limits, security and acceptance tests pass; add Try Live on Store page, track completion and opt-in leads. Existing Python business server needs a suitable low-cost runtime or a separately verified faithful execution strategy.
5. **Scale only on demand:** second/third product and progressive guides, role-specific challenges, more plans and CRM metrics if real shop interest proves value.

## KPIs without fabricated forecasts
Demo starts; percent who complete first real action; problem resolved without support; demo→quote requests; quote→trial; trial→paid customer; support calls per active customer; average isolated demo cost per qualified lead. Monitor per week, decide expansion only from real demand and costs.

## Owner approvals and blockers
- Original Pixel Plus logo/brand asset and legal brand/domain; preferred WhatsApp contact, email and business phone; whether to list exact prices publicly; hosting budget ceiling per month for public live demo; cloud region and consent text.
- Contact details and payment integrations must not be invented or embedded before owner approval.
- All four commercial tiers are a packaging strategy; demos do not make cloud syncing available automatically.

References inspected:
- https://cheatsheetseries.owasp.org/cheatsheets/Multi_Tenant_Security_Cheat_Sheet.html
- https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Regression_Testing_Cheat_Sheet.html
- https://developers.cloudflare.com/pages/functions/pricing/
- https://developers.cloudflare.com/workers/platform/pricing/
