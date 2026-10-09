# Pixel Plus website: requirements (not built, not hosted)
Requirements for the owner • 9 October 2026
Status: **REQUIREMENTS ONLY.** No site, domain, hosting, form, CRM or live demo exists, and none is started by this document. It extends [PIXEL_PLUS_EXPERIENCE_ROADMAP.md](PIXEL_PLUS_EXPERIENCE_ROADMAP.md) (the why and the phases) with what a builder and a tester need: pages, rules, intake, limits and acceptance checks.

## 1. What the site is for
A small-shop owner in Egypt lands on the site, sees what a product does in their own words, **tries it without risk**, sees which plan fits, and asks for an offer or a Windows trial. The site sells nothing by itself: no payment, no account, no licence signing.

Three visitors to design for:
1. **The shop owner** (phone, Arabic first, little patience): "Is this for my shop? What does it cost? Can I try it?"
2. **The cashier / storekeeper** sent by the owner: "Show me how to do my job" (the practice exercises).
3. **The owner's accountant or relative** checking trust: "Who are they? Where is my data? Who do I call?"

## 2. Pages and what each must contain
| Page | Must contain | Must not contain |
|---|---|---|
| Home | the problem in one sentence, product list, three real use cases, how a trial works, contact | invented numbers of customers, awards, certifications |
| Product (one per released product) | who it is for, a 60–90 s real walk-through (screen recording of the latest version), what it does and **what it does not**, real screenshots, «جرّب» (see §4), «حمّل تجربة ويندوز» (only when a build exists), plans, «اطلب عرض سعر» | screenshots of an older or mocked-up screen; features of unreleased tiers |
| Plans | the four commercial plans as the owner approved them (`docs/SMB_COMMERCIAL_TIERS.md`), what each includes today, what is not available yet and marked as such | prices unless the owner approves publishing them; any tier that is not released |
| Try it | the routes in §4 | a simulator presented as the real program |
| Help | the same plain-words answers as the program's Help, searchable | support promises the owner has not staffed |
| Contact / offer | the form in §5 and the owner's approved phone, WhatsApp number and e-mail | a phone number or address nobody confirmed |
| Privacy and terms | what the form collects, why, how long, how to delete; what the programs send (nothing by default) | legal text copied from another company |

Every page: Arabic first (RTL), English one click away, same address structure in both; the brand is the owner's original Pixel Plus identity (logo, colours, type): **not invented and not substituted** (open item, §9).

## 3. Honesty rules (these are release checks, not style)
- Nothing on the site claims more than the product's evidence file (`examples/*-product.json`): a control that is only `implemented` is not advertised as proven.
- A screenshot or video must come from a build that exists; its version is written in the page's source and checked by a test against the product's `version.py`.
- No fake reviews, counters, "last purchase" pop-ups or countdowns. No urgency tricks.
- A feature that needs a second PC, a phone app or a cloud copy is labelled with the plan that has it, and "not yet available" when it is not released.

## 4. "Try it": three routes, in this order of readiness
1. **Local practice (exists):** Al-Store 1.7.0 opens a made-up practice shop beside the real one from Help, with three exercises checked from the books. The site tells the visitor to download the trial and open Help. Nothing hosted.
2. **Short walk-throughs (cheap):** recorded from the real program, subtitled in Arabic and English. Allowed on a static site.
3. **Public live sandbox (only after approval):** a hosted copy of the real program with made-up data. Not started. It needs, before any code: a measured cost per session and a monthly ceiling from the owner; one isolated database per session, deleted on expiry (15–30 min idle); a cap on sessions, CPU, memory and disk; rate limits; no outbound mail, messages, payments, printing, telemetry or backups (every adapter a no-op, with a test); no real keys, admin access or shared volume; Arabic and English; a visible "demo" banner and a reset button.
   A static site cannot run Al-Store's Python server, so route 3 means a separately hosted back end. Until it exists the site must **not** show a "Try live" button.

## 5. Offers, trials and leads
- **Form fields (all optional except one way to reach the person):** name, shop type, city, which product, which plan, number of PCs, the person's own phone or e-mail, preferred time to be contacted, consent tick (unticked by default), free text (limited, stripped of markup).
- **Where it goes:** a small relay service of the same kind as the licence mailbox (`templates/telemetry-relay`): the page holds no secret; the request carries a nonce so a double click creates one lead; per-address and total daily caps; a hidden honeypot field; bodies size-limited; text cleaned. The owner is alerted on **Telegram** (the owner's decision of 9 October 2026), with the product, plan and city only: never the person's phone or free text in the alert. Leads wait in the relay until the owner's side pulls them.
- **No automated WhatsApp or SMS to the visitor** (factory rule MSG-01). The owner or a person on the owner's side contacts them, once, and the visitor can say "stop".
- **Statuses on the owner's side only:** new → contacted → demo → offer → pilot → sale / closed. A spreadsheet is enough at first.
- **Trial:** the site never issues a licence. The visitor downloads the program and presses the trial button inside it (Al-Store 1.6.0: one trial per PC, owner-approved policy, signed on the owner's PC only). The site may explain this; it may not promise "instant code".
- **Retention:** a lead the owner does not act on is deleted after a period the owner sets (suggested: 12 months); anyone can ask for deletion; the privacy page says so.

## 6. Non-functional requirements
- **Performance (measured, on a mid-range Android phone, throttled 4G):** the first page weighs under 300 KB before images; images are sized for their box; no web fonts from another site; the page is readable before scripts run.
- **Static first:** pages are plain HTML/CSS with a little script; no framework needed to read a page; no third-party scripts (analytics, chat, tag managers, fonts, maps) without the owner's written approval and a privacy-page line.
- **Accessibility:** WCAG 2.2 AA for contrast, focus, keyboard, labels, reduced motion; Arabic RTL with correct mirrored icons; numbers readable in both scripts.
- **Security:** a strict Content-Security-Policy, no inline script, HTTPS only, secure headers, no secret in the page or the repository (a scan is part of the build), the form's relay refuses cross-site posts it cannot verify and never echoes input.
- **Analytics:** aggregate counts only (visits, route started, form sent), no cookie banner needed because no cookie identifies a person; if the owner wants more, it needs consent and a privacy-page line.
- **Availability:** the site down must not affect any shop; the programs never depend on it.

## 7. Acceptance checks (all must pass before anything is announced)
1. Every link works (internal and external); every page exists in both languages; no page links to a feature the product does not have.
2. Screenshot and video versions equal the shipped version (test).
3. Real-browser run at 360, 768 and 1366 px in Arabic and English: no horizontal scroll, no overlap, keyboard path to the form, focus visible, contrast measured.
4. Page weight and load time within §6 on a throttled profile.
5. Form: one click twice = one lead; empty, huge, markup, emoji, right-to-left and script-injection inputs are handled; the daily cap holds; the honeypot drops bots; the Telegram alert contains no personal data; deletion works.
6. Secret scan of the site and relay repositories is clean; no key, token or real phone number in any file.
7. For route 3 only: the negative tests listed in the roadmap (cannot read or change real data, one session cannot see another, outbound blocked, true reset returns the seeded state, expiry removes access, 100 parallel sessions obey the quotas).
8. The owner has signed off in writing on the brand assets, domain, contact details, legal text and (route 3) the monthly ceiling.

## 8. Reuse, don't rebuild
- Practice shop and exercises: Al-Store `server/practice.py`, `server/training.py` (isolation rules and tests are the pattern for a hosted sandbox).
- Relay with caps, nonces and Telegram alert: `templates/telemetry-relay` (`src/licence.js` is the model for the lead mailbox).
- Design tokens and bilingual patterns: `packages/af-ui`, `docs/DESIGN_SYSTEM.md`.
- The four plans and their evidence: `docs/SMB_COMMERCIAL_TIERS.md`, each product's manifest.

## 9. Open items for the owner (nothing is assumed)
Original Pixel Plus logo and brand files; the legal brand name and domain; the phone, WhatsApp number and e-mail to publish; whether to show exact prices; privacy-page text and the lead retention period; a monthly hosting ceiling and region if route 3 is wanted; who answers leads and how fast. Until these are answered the site stays a plan.

## 10. Order of work
Phase 1 (local practice pilot): delivered in Al-Store 1.7.0, awaiting independent review and a real cashier's use. Phase 3 (static starter site: brand-verified home, two or three real product pages, contact form on the lead relay) is the next step **only after** the first paying shop is live, as the roadmap says. Phase 4 (public live sandbox) waits for §4's approvals.
