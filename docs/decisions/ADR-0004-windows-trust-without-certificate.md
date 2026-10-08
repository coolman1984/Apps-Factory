# ADR-0004 • Shipping on Windows before buying a code-signing certificate

- **Date:** 2026-10-08
- **Status:** ACCEPTED by owner (session decision): start without an Authenticode certificate; buy one when revenue allows.
- **Replaces** the "unsigned = automatic NO-GO" rule for the first stage only. (ADR-0003 is reserved for the sync-engine spike.)

## Facts that shape the decision (sources in §5)
- SmartScreen checks **reputation** of files that carry the "downloaded from the internet" mark (Mark of the Web). An unsigned new file shows "Windows protected your PC" → *More info* → *Run anyway*. It is a reputation warning, not a virus verdict.
- Files that never got that mark (installed by us from a USB stick, or downloaded by **our own updater**) are not checked by SmartScreen on launch. Microsoft Defender antivirus still scans them.
- **Smart App Control** (Windows 11 clean installs) blocks unknown unsigned apps with **no "Run anyway"**. Newer Windows 11 builds let the owner switch it off without reinstalling.
- A self-signed certificate does not help with SmartScreen and installing our own root certificate on customer PCs is a security risk.
- Free routes that exist: Microsoft Store (free individual registration; Microsoft signs MSIX packages) — but individual accounts are for non-business distribution; SignPath Foundation — open-source projects only. Neither fits our closed commercial apps today without checks.

## Decision: three trust stages
| Stage | When | How customers get and trust the app |
|---|---|---|
| **A — no certificate (now)** | first customers | We install it ourselves (on site from a clean USB stick, or during a consented remote session). The installer and every update are signed with **our own Ed25519 key** (`af-license` `update` purpose) and verified by our updater, so authenticity does not depend on Windows. SHA-256 of every release published on our download page. Customer guide explains the SmartScreen screen. |
| **B — free Microsoft path (spike)** | when a customer needs self-install from the web | Evaluate Microsoft Store/MSIX packaging (Microsoft-signed): account type allowed for commercial sale, MSIX fit with a local server + data folder, update flow. Decision recorded before use. |
| **C — certificate** | trigger: ~10 paying installs, **or** first customer blocked by Smart App Control / IT policy, **or** public web downloads | Buy an OV code-signing certificate (e.g. Certum cloud) and sign every build in CI; keep our Ed25519 update signature as a second layer. |

## Rules during stage A (enforced in controls `REL-01`, `REL-05`)
- Never ask a customer to disable Microsoft Defender, add whole-disk exclusions, or install our root certificate.
- If Defender flags our build: submit it to Microsoft as a false positive, rebuild cleanly (version info set, no UPX, one-folder build), and allow at most the specific file from Protection history with the customer's consent.
- Smart App Control: check during installation. If on and blocking, explain, and with the customer owner's consent switch it off only where Windows offers that setting; otherwise move that customer to stage C or B first.
- The download page and every update manifest carry the SHA-256; the updater refuses anything whose Ed25519 signature or hash fails.
- Keep the same product name, publisher text and version metadata on every build so the move to stage C keeps continuity.

## Sources (checked 2026-10-08)
- SmartScreen explanation for unsigned apps: https://open-bart.readthedocs.io/en/latest/standalone/SMARTSCREEN.html • https://blog.betterbird.eu/2026/01/whats-the-story-with-windows-smartscreen • https://www.emeditor.com/tag/smartscreen/
- EV certificates no longer give instant reputation: https://www.todesktop.com/blog/posts/windows-apps-psa-ev-certs-do-not-grant-immediate-reputation-anymore
- Smart App Control behaviour and toggle: https://windowslatest.com/2025/12/16/microsoft-confirms-you-can-soon-disable-smart-app-control-without-reinstalling-windows-11 • https://blog.devgenius.io/smart-app-control-may-blocked-your-app-the-fix-was-to-stop-rebuilding-it-5676f69ec3bc
- Mark of the Web mechanics: https://www.zerodayinitiative.com/blog/2024/8/14/cve-2024-38213-copy2pwn-exploit-evades-windows-web-protections
- Microsoft Store free registration and signing: https://blogs.windows.com/windowsdeveloper/2025/09/10/free-developer-registration-for-individual-developers-on-microsoft-store/ • https://learn.microsoft.com/en-us/windows/apps/publish/get-started
- SignPath Foundation terms: https://signpath.org/terms
