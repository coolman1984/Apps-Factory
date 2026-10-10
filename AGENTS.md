# Mandatory instructions for every AI coding agent

## Read order
1. [README.md](README.md): what the factory is and the commands.
2. [RULES.md](RULES.md): the 32 core controls, the firm privacy limits, the agent workflow.
3. [PARTS.md](PARTS.md): the shared parts, their versions and how products take them.

For cross-product Pixel Plus/Store work, begin with [the unified owner execution roadmap](docs/PIXEL_PLUS_EXECUTION_ROADMAP_2026.md); do not mistake its planned features for shipped code. For Telegram owner approvals, Rafaa or Sanad use only the linked scope specs, and preserve privacy/payment approval boundaries.

Then read only the spec for the part you touch (linked from PARTS.md). Read [DECISIONS.md](DECISIONS.md) when a business choice is involved (price, sensitive data, anything paid). Look up a control or an old id with `python3 scripts/factory.py controls <ID>`. Day-to-day commands (tests, releases, drift checks) are in [PLAYBOOK.md](PLAYBOOK.md).

## Company-level agent handoffs
For CEO/marketing/research/council/portfolio tasks, consult [Pixel Plus's one-person company strategy](docs/PIXEL_PLUS_ONE_PERSON_COMPANY_OS.md) and [operations playbook](docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md). The coordinator must assign a bounded task with source references, spend cap, allowed tools, exact definition of done, independent reviewer and owner decision gates. A new chat session must reconstruct state from main, current PRs and the approved roadmap, not stale chat claims. Do not infer permission for spending, customer outreach, data-sharing, licensing or deploys.

## Visual/UI work
Any UI, UX, page, dashboard, RTL, accessibility or CSS task: read `design-factory/AGENTS.md` first and follow it.

## Creative motion, icons, layers, video
Read `design-factory/CREATIVE_AGENT_PLAYBOOK.md` and pick a `design-factory/creative-recipes/*.json` profile before writing code.

## Task classification
- **New product:** cited market research, customer and risk discovery, one paid core journey, deferred features cut. Get recorded owner approval for assumptions that change price, risk or sensitive-data handling.
- **Existing product:** audit before changing. Preserve working design, real records, backwards compatibility and migrations. Do not overwrite main or paste older shared code into it.
- **Platform improvement:** build it once in a versioned, separately tested shared part with example consumer tests. A Markdown requirement is not working software.

## Rules that never change
- The workflow in RULES.md section 3 applies to every task. Use a PR with CI and a small safe merge; never force-push or mass-merge divergent branches.
- Products get shared parts by `scripts/vendor_*.py`. Never edit a vendored copy; change the factory part, bump its version, vendor again.
- Never publish `admin/123` or any static production credential, never create a developer backdoor, never enable a demo shortcut in production (demo logins only in isolated synthetic builds tagged DEMO).
- Private keys never enter a repository, CI secret or build. No credentials or personal data in source, logs, screenshots, public issues or fixtures.
- Never automate WhatsApp messages to customers (MSG-01).
- Do not claim "ready to sell" because CI passed. Clean install, recovery drill and the first paying customer's acceptance are separate gates.
- Report honestly: what changed, the exact commit or PR, the tests actually run, the checks skipped, the field checks still pending. Never claim to have looked at a screenshot you did not view.
