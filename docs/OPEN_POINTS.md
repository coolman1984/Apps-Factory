# Decided items and open cost/verification points

Recorded 2026-10-09 (Cairo). Nothing in the open list is decided, bought or signed up for. Adapters that depend on an open item ship **disabled**.

## Decided
- **Repository visibility** (decided 2026-10-09 09:04): all 5 repos stay **public**:
  - Teachers
  - Yousef-Transportation
  - Store
  - Apps-Factory
  - Mr.Ayman-HR

  None of them will be converted to private.
- **Licensing with public source:** because the code is public, licence protection relies on **server-side and signed checks**, not on code secrecy:
  - licence codes are Ed25519-signed and device-bound (`packages/af-license`);
  - products verify them with the public key only;
  - the private key never enters a repository, CI secret or build.
- **Alert delivery:** every alert fans out to **all enabled channels** at the same time:
  - there is no priority order and no fallback;
  - a failure in one channel never blocks the others;
  - delivery is logged per channel.

- **Customer patch delivery stays free** (decided 2026-10-09 09:12). See [CUSTOMER_PATCH_PIPELINE.md](CUSTOMER_PATCH_PIPELINE.md):
  - the in-app «تحديث متاح» notice is primary;
  - email goes through the Resend free tier or SMTP;
  - WhatsApp is a wa.me link the owner sends by hand;
  - the optional customer Telegram bot is free.
- **Rejected (no payment):** WhatsApp Cloud API utility templates for **customer** delivery. They cost about $0.0036 per
  message plus 14% VAT and need a Meta business account and a payment method. No automated WhatsApp goes to customers (MSG-01).
- **Telegram is a core channel** (decided 2026-10-09 09:26). It is free: a BotFather bot plus the Cloudflare Worker relay.
  - **Owner alerts** (customer problems, crashes, licence) go to **Telegram + email + dashboard**. The Telegram owner
    channel is **on by default**: it is active as soon as `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` are set, and
    it has no separate switch (implemented in the Control Center).
  - **Customer Telegram bot:** an optional channel next to the in-app notice and email (design in
    [CUSTOMER_PATCH_PIPELINE.md](CUSTOMER_PATCH_PIPELINE.md) §5).
  - **Patch approvals:** when a fix PR is waiting for approval, Telegram sends the owner the PR link (design §7).
  - **Owner commands:** `/status` and `/incidents`, answered from the dashboard data through the relay webhook, and
    accepted only from the owner's chat id (design §7).
  - The **WhatsApp owner-alert** open point is **superseded by Telegram** (see the table).

## Open points (the owner decides; no payment has started)
| Item | Why it is open | Note |
|---|---|---|
| WhatsApp Business / Cloud API (owner alerts) | **Superseded by Telegram** (decided 2026-10-09 09:26). The adapter stays in the code, unconfigured; nothing is bought. | superseded; no open point |
| E-mail sending provider (alerts) | A provider plan may be needed; the sending domain must be verified (SPF/DKIM) | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| LinkedIn (alerts) | Official DMs are partner-only, and automated sends are prohibited. The free self-serve API only posts publicly on your own profile, which does not suit alerts. The adapter stays disabled while the owner researches the options. | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Cloudflare Workers + D1 (telemetry relay) | The free plan limits requests, storage and rows; fleet traffic may exceed them | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Windows code-signing certificate | The certificate is paid and needs organisation validation (see ADR-0004) | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Paymob / Fawry / InstaPay | Merchant onboarding needs company documents; transactions carry fees | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Telegram bot (owner alerts, owner commands, customer bot) | Free (BotFather token, no company verification); webhook on the Cloudflare relay. A core owner channel, on as soon as it is configured. | free; decided |
| GitHub paid features for private repos | Closed: the repos stay public (see Decided) | decided |
