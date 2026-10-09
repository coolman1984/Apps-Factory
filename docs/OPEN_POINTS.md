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

## Open points (the owner decides; no payment has started)
| Item | Why it is open | Note |
|---|---|---|
| WhatsApp Business / Cloud API (alerts) | Needs Meta business verification; priced per message | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| E-mail sending provider (alerts) | A provider plan may be needed; the sending domain must be verified (SPF/DKIM) | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| LinkedIn (alerts) | Official DMs are partner-only, and automated sends are prohibited. The free self-serve API only posts publicly on your own profile, which does not suit alerts. The adapter stays disabled while the owner researches the options. | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Cloudflare Workers + D1 (telemetry relay) | The free plan limits requests, storage and rows; fleet traffic may exceed them | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Windows code-signing certificate | The certificate is paid and needs organisation validation (see ADR-0004) | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Paymob / Fawry / InstaPay | Merchant onboarding needs company documents; transactions carry fees | «⚠️ نقطة مفتوحة: لسه ما بدأناش ندفع — التكلفة و/أو شرط توثيق الشركة مش واضحين» |
| Telegram bot (alerts) | The bot token is free and needs no company verification; the adapter is optional and disabled by default | free; not an open point |
| GitHub paid features for private repos | Closed: the repos stay public (see Decided) | decided |
