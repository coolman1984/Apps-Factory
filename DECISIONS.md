# Decisions

Dated owner decisions, newest first. Only decisions recorded in the repository are listed: the old open-points file (now `docs/archive/OPEN_POINTS.md`), the ADRs and the CHANGELOG. Business choices (price, who bears risk, sensitive data, anything paid) need an entry here before code depends on them. Times are Cairo time where the source gave one.

## Decided

### 2026-10-10 — One-person Pixel Plus operating-company direction
- The owner wants one accountable human with AI-assisted engineering, marketing, research, management, Council, support, cost analysis and operational execution. **Direction approved; architecture is a staged proposal, not delegated broad credentials or permission to spend.**
- [Research and operating architecture](docs/PIXEL_PLUS_ONE_PERSON_COMPANY_OS.md) and [first 30-day workflows](docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md): bounded work queue, reviewed handoffs, evidence links, independent QA, low-cost current tools and owner approval for all customer-impacting/financial/external acts.
- "90% automation" is a **measurement objective for selected repeatable tasks**; current percentage unknown until workflow execution is instrumented. Chat subscriptions must not be assumed to cover API fees.
- Next approval required: any live connector permissions, data disclosure, Telegram workflow, spend ceilings and production automation. No new customer/deployment/sales feature is shipped by these research docs.


### 2026-10-09 — Integrated Pixel Plus execution plan, Telegram approvals and partner modules
- **Approved direction:** local-first Egyptian small-business software, modular product + four connectivity/packaging plans; no enterprise complexity or automatic cloud spending. [Execution roadmap](docs/PIXEL_PLUS_EXECUTION_ROADMAP_2026.md) gives sequence and honest delivery statuses.
- **Owner Telegram activation journey requested:** Store sends a minimal consented 14-day trial request; owner approves/denies in a private Telegram chat; local trusted Licence Studio signs device-bound code with its offline encrypted key; only requester receives/verifies code, owner receives the code for manual offline fallback. **Update 2026-10-10: approval buttons, signing on the owner's PC and delivery are implemented (Factory 0.14.0) and tested against a fake Telegram; not deployed.** No remote bot/cloud signing key and no charge/issue of paid code without verified human payment authorization. See [activation design](docs/TELEGRAM_APPROVED_ACTIVATION.md).
- **Rafaa direction:** included small factual/role-limited radar in suitable products and optional deeper monthly/perpetual growth-finance add-on. It reuses Accounting-sys, and all Egyptian tax-rule updates must cite official current sources plus qualified reviewer sign-off; no misleading promise of replacing accredited advisers. [Proposal](docs/RAFAA_GROWTH_DECISION_ADDON_PROPOSAL.md) merged for research, **no functionality or prices approved as delivered**.
- **Pixel Plus × Sanad Business Advisory direction:** optional human consulting/coaching service sold separately, with explicit customer opt-in and least-privilege data access. Exact sales/commission/support/privacy terms remain **OPEN** pending owner's Sunday 2026-10-11 briefing. [Partner plan](docs/PIXEL_PLUS_SANAD_PARTNER_OPERATING_MODEL.md).
- **Priority:** Store pilot and Windows/data field acceptance first; Telegram activation and off-device encrypted backup before broader commercial claims; demo/visual QA, Rafaa and showroom in phased PRs. Independent review agent vs implementation agent; only green tests and evidence permit merge.

### 2026-10-10 — The owner's Telegram buttons: design choices taken while building them (awaiting the owner's confirmation)
- «✅ موافق» signs a **trial** on the owner's PC even when the automatic policy is off (the owner chose that request by hand); the daily cap and the flood check, which are the owner's own limits, do not hold it back. Every hard rule still does (one trial per PC, well-formed device, key unlocked).
- For **monthly and permanent** the button records intent only. Signing still needs the payment tick and reference in the Studio: the bot never moves a paid code forward alone.
- «❌ رفض» is final; «سحب الموافقة» works until the code is signed. An approval counts for **72 hours** by default (the relay judges it).
- The owner's chat gets **a copy of every signed code** (the manual way for an offline shop). The chat must be the owner's private chat with the bot; a group is refused.
- **Proposed, not decided:** a one-use challenge for a brand-new install (today: nonce, address/device/list limits and one trial per machine tag; a determined person with a new identity can still get another trial).

### 2026-10-09 — Telegram is the owner's channel for licence requests; trials go out automatically only by a policy the owner switches on
- The owner's decision: the notification channel is **Telegram**, not WhatsApp. The shop's request reaches the owner's phone through the relay (kind, product, short request id, device code only); the owner's trusted PC signs; the shop checks and activates by itself. **The signing key exists only on the owner's trusted PC**: never in the bot, the relay, a CI job or a repository. WhatsApp to customers stays manual, one at a time (MSG-01).
- **Automatic trials are OFF until the owner turns them on.** When on, the defaults recorded in the Licence Studio are: 14 days at most, bound to the device code, one trial per PC (an append-only ledger that survives a reinstall), at most 10 automatic trials a day, more than 5 a day from one address is held for the owner (never refused: shops share addresses). These numbers are **proposals awaiting the owner's confirmation**, not business decisions.
- Monthly and permanent codes are never automatic: the server refuses to sign without a ticked payment confirmation and a payment reference (payment itself is still by hand, see "How customers pay for their licence" below).
- Evidence: `docs/LICENCE_ACTIVATION.md`, the chain test with the real shop program, the real relay Worker and the real Studio (`apps/licence-studio/tests/test_store_chain.py`).

### 2026-10-09 — The practice shop is the demo; the Pixel Plus website is documented, not built
- The in-product demo is the existing practice shop, opened from Help and kept apart from the real shop (own folder beside it, own port on 127.0.0.1, never opened as the other kind, never sends anything), with three exercises checked from the shop's own books (Al-Store 1.7.0).
- The website, a hosted sandbox and the lead form are **requirements only** (`docs/PIXEL_PLUS_WEBSITE_REQUIREMENTS.md`); hosting, domain and spending need the owner's written approval.

### 2026-10-09 — Al-Store activation kinds
- The owner asked for three kinds of activation code: a **14-day trial**, a **monthly subscription** and a **permanent activation**. A permanent code is device-bound and never ends. The Studio defaults for a monthly code are 30 days + 3 grace days. The owner can change both in the Studio.
- Prices are **not** decided here (still open below).

### 2026-10-09 — Four lean commercial plans and Windows release evidence
- Egypt-first individuals, shops and small/medium firms. Plans: Solo (one offline-capable Windows PC with independent encrypted/versioned cloud backup); Connected (multiple synchronized PCs plus **owner read-only** installed mobile app); Mobile Operations (role-limited mobile sales, barcode and updates); Cloud Business (hosted primary service plus mobile/Windows clients).
- Sales packaging is **not** `connectivity.tier`. Existing one-PC releases do not magically gain remote backups, mobile apps or cloud sync. Cloud data handling, provider, region, recovery keys and cost ceiling are open customer/owner decisions before implementation.
- Windows CI for every PR and main push is mandatory for Windows products; actual clean-PC and restore acceptance remain separate. Existing factory OPS-07 stays core and optional manifest commercial evidence blocks unsupported plans. Source: [commercial contract](docs/SMB_COMMERCIAL_TIERS.md).
- Zero-data-loss guarantees are rejected: offer transparent backup frequency, copies outside the PC, integrity tests and verified restoration.

### 2026-10-09 — Al-Store owner recovery is a paper code
- At setup the program shows a one-time recovery code to print; «نسيت كلمة السر؟» uses it to set a new password and then shows a new code. Only its hash is kept; there is no vendor master password. Store 1.4.0 (IAM-01 verified).

### 2026-10-09 — Al-Store sells with cash only at first
- Every Al-Store shop, new or updated, takes **cash only**. Card, mobile wallet, InstaPay, finance companies, on account and shop instalments stay built and tested, hidden and refused by the server until the shop owner ticks them in Settings. They are shown only when a customer asks for them. Store 1.3.0.
- The road to the first paying shop is `docs/03-ready-to-sell.md` in coolman1984/Store; the per-control status is `control_evidence` in `examples/al-store-product.json`.

### 2026-10-09 (factory 0.11.0)
- **Docs diet.** Five living docs: `README.md`, `RULES.md`, `PARTS.md`, `PLAYBOOK.md`, `DECISIONS.md`. Agents read three: README → RULES → PARTS. Research and old plans moved to `docs/archive/`. Detailed specs that code, tests or products link to stay in `docs/` as reference specs. (Review item A12.)

### 2026-10-09 (factory 0.10.1)
- **Help is written in simple formal Arabic** («العربية الميسّرة»), with a learning path per role; HELP-08 is folded into HELP-07. See ADR-0006.

### 2026-10-09 (factory 0.10.0, "rules cleanup")
- **Only 32 core controls block a release.** The other 75 are `reference` advice. 24 ids were merged into survivors and 7 were retired; old ids still resolve with `factory.py controls <ID>`.
- **Release evidence is two items:** `clean_device_restore` and `core_user_acceptance`. The market, privacy and security review items left the gate.
- **Competitor count is advice.** Fewer than 5 competitor rows prints a note and no longer fails `--release`.
- **No outside-review framing.** The gate has no outside-review step and controls state practical outcomes only. What is enforced is consent (PRIV-01) and the never-collect limits (PRIV-03). REG-01 and REG-02 were retired for this reason.
- **Paperwork controls retired.** Where GitHub branch protection or an existing check already enforces the point, the control was dropped (OPS-05, OPS-03).

### 2026-10-09 (factory 0.9.0, telemetry hardening)
- **Product rollout of telemetry waited for the hardening.** It is now in: protocol 2 sends batches over HTTPS with the install token (no signature, nonce or time window), a bad event never sinks the batch, and the relay stays inside Cloudflare D1 free limits.
- **New PCs wait for the owner's approval** («أجهزة جديدة مستنية موافقتك») instead of being dropped; alerts are sent outside the database lock.

### 2026-10-09 09:26 — Telegram is a core owner channel
- Free (a BotFather bot plus the Cloudflare Worker relay). Owner alerts go to **Telegram + e-mail + dashboard**. The Telegram owner channel is on as soon as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` are set and has no separate switch.
- Optional customer Telegram bot beside the in-app notice and e-mail; patch-approval notices with the PR link; owner commands `/status` and `/incidents`, accepted only from the owner's chat id (design: `docs/CUSTOMER_PATCH_PIPELINE.md`).
- This supersedes the WhatsApp owner-alert open point. The WhatsApp adapter stays in the code, unconfigured; nothing is bought.

### 2026-10-09 09:12 — Customer patch delivery stays free
- The in-app «تحديث متاح» notice is primary; e-mail through the Resend free tier or SMTP; WhatsApp is a `wa.me` link the owner sends by hand; the optional customer Telegram bot is free.
- **Rejected (no payment):** WhatsApp Cloud API templates for customers (about $0.0036 per message plus 14% VAT, needs a Meta business account and a payment method). No automated WhatsApp goes to customers (MSG-01).

### 2026-10-09 09:04 — All five repositories stay public
Apps-Factory, Store, Teachers, Yousef-Transportation and Mr.Ayman-HR. None will be made private. Because the code is public, licence protection rests on signed, server-side checks, not on secrecy: licence codes are Ed25519-signed and device-bound, products hold the public key only, and the private key never enters a repository, CI secret or build.

### 2026-10-09 — Alerts fan out to every enabled channel at once
No priority order and no fallback; one failing channel never blocks the others; delivery is logged per channel (ADR-0007 item 6).

### 2026-10-09 — Consent-gated telemetry (ADR-0007, approved with the plan)
Two consent levels (installation, then person), usage visible per person through a pseudonym, only allowlisted ids and counts, problem reports allowed without consent, practice data before installations (ROLL-01).

### 2026-10-09 — Guided onboarding engine and the Arabic register (ADR-0006, approved with the parity plan)
One shared engine, `packages/af-guide`, vendored like `af-access`; help in «العربية الميسّرة».

### 2026-10-08 — Earlier ADRs, all accepted by the owner
Architecture, protection and updates, unsigned Windows start, help and diagnostics: see the index below. The Windows code-signing certificate waits until about 10 paying installs, or a customer blocked by Smart App Control or IT policy, or public web downloads (ADR-0004).

## ADR index (`docs/decisions/`)
| ADR | Date | One line |
|---|---|---|
| [ADR-0001](docs/decisions/ADR-0001-architecture-and-connectivity-tiers.md) | 2026-10-08 | Modular monolith, default stack, connectivity tiers (`standalone`, `office_server`, `cloud_sync`, `cloud_only`; `office_mesh` was added later from Hessa). |
| [ADR-0002](docs/decisions/ADR-0002-protection-updates-vendor-control.md) | 2026-10-08 | Layered, honest copy protection; signed updates; Vendor Control Center; AI-assisted support through it. Free and simple first. |
| ADR-0003 | — | Reserved for the sync-engine spike. Not written. |
| [ADR-0004](docs/decisions/ADR-0004-windows-trust-without-certificate.md) | 2026-10-08 | Ship on Windows without a code-signing certificate at first; three trust stages. |
| [ADR-0005](docs/decisions/ADR-0005-help-diagnostics-remote.md) | 2026-10-08 | Help is core; no welcome slideshow; hidden diagnostics probe under an open support window. |
| [ADR-0006](docs/decisions/ADR-0006-guided-onboarding-and-arabic-register.md) | 2026-10-09 | `af-guide` engine and the «العربية الميسّرة» register. |
| [ADR-0007](docs/decisions/ADR-0007-consent-telemetry-feedback.md) | 2026-10-09 | Consented telemetry, per-person usage, problem reports. |

## Open
Nothing below is decided, bought or signed up for. Anything that depends on an open item ships **disabled**.

| Item | Why it is open |
|---|---|
| E-mail sending provider (alerts) | A provider plan may be needed; the sending domain must be verified (SPF/DKIM). |
| LinkedIn (alerts) | Official DMs are partner-only and automated sends are prohibited; the adapter stays disabled while the owner researches. |
| Cloudflare Workers + D1 (telemetry relay) | The free plan limits requests, storage and rows; fleet traffic may exceed them. |
| Windows code-signing certificate | Paid, needs organisation validation; trigger is in ADR-0004. |
| Optional commercial features start turned off (factory-wide rule?) | Proposed after the Al-Store cash-only decision: every product would ship its optional ways (payments, credit, instalments) off and let the shop owner turn them on. Needs owner approval before it becomes a control. |
| Owner password recovery as an explicit IAM-01 acceptance item for every product | Al-Store now has a paper recovery code (1.4.0); the other products have none yet. |
| How customers pay for their licence | Manual transfer (InstaPay / wallet) plus a code by hand until about 10 customers; automated payment stays with the Paymob / Fawry item below. |
| Paymob / Fawry / InstaPay | Merchant onboarding needs company documents; transactions carry fees. |
| Deploy the licence relay and create the Telegram bot | The owner creates the bot and the Cloudflare Worker secrets; nothing is deployed. Until then only the manual way (device code out, code in) works. |
| Trial policy numbers (daily cap, per-address limit, trial days) | Recorded as defaults in the Studio; the owner confirms or changes them before switching automatic trials on. |
| Pixel Plus website: brand files, domain, published contact details, hosting ceiling | See `docs/PIXEL_PLUS_WEBSITE_REQUIREMENTS.md` §9. |
| Cloud provider, hosting region, monthly ceiling per customer | ADR-0001 open decision 1. |
| Price of each tier | ADR-0001 open decision 2. |
| Which mobile actions work offline in version 1 | ADR-0001 open decision 3. |
| Multi-owner rule: quorum or vendor-mediated dispute | ADR-0001 open decision 4. |
| Sync engine choice after the spike (ADR-0003) | ADR-0001 open decision 5. |
