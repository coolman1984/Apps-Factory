# Decisions

Dated owner decisions, newest first. Only decisions recorded in the repository are listed: the old open-points file (now `docs/archive/OPEN_POINTS.md`), the ADRs and the CHANGELOG. Business choices (price, who bears risk, sensitive data, anything paid) need an entry here before code depends on them. Times are Cairo time where the source gave one.

## Decided

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
| Cloud provider, hosting region, monthly ceiling per customer | ADR-0001 open decision 1. |
| Price of each tier | ADR-0001 open decision 2. |
| Which mobile actions work offline in version 1 | ADR-0001 open decision 3. |
| Multi-owner rule: quorum or vendor-mediated dispute | ADR-0001 open decision 4. |
| Sync engine choice after the spike (ADR-0003) | ADR-0001 open decision 5. |
