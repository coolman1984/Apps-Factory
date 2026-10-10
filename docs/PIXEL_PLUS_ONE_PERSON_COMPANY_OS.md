# Pixel Plus: The One-Person Company Operating System
**Research snapshot:** 2026-10-10 · **Status:** architected / phased proposal. A small **local-only prototype** has been exercised separately, but is NOT committed to this branch and is NOT a deployed autonomous company. An actual integration needs a separate implementation PR.

## Executive thesis
One accountable human owns Pixel Plus. A network of bounded AI roles performs research, engineering, QA, product design, marketing preparation, sales follow-up preparation, customer support classification, finance analysis and operational reporting. **The company is a collection of proven workflows and records, NOT six unsupervised chat windows.**

### Honest ambition / the “90%” number
- 90% is a **target for clearly defined, repeatable eligible work steps**, not an audited current result and NOT autonomy on 90% of all company responsibility.
- Track separately: **A** eligible work steps completed automatically with evidence / all eligible work steps; **B** verified correct runs / attempted runs; **C** hours truly saved after human review; **D** cost per qualified lead, successful delivery and support case; **E** risky actions caught and blocked.
- Never count brainstorming, answers in chat, created PRs, partial scripts or passing tests as end-to-end field acceptance. Manually approved actions and direct customer conversations remain human-owned.
- Working aspiration subject to validation: Month 1 25–40% *eligible repetitive* steps, month 2 50–65%, month 3 65–80%, later up to 90% on carefully chosen flows. These are HYPOTHESES to measure, not vendor capabilities.

## From founder's phone to auditable work
```
OWNER: one brief, voice/text, or approve/deny
   ↓
INTAKE: task ID, intended outcome, value, budget cap, risk, permissions, deadline, evidence
   ↓
COORDINATOR: read company facts and source-linked prior decisions, assign specific role
   ↓
OPTIONAL COUNCIL: dissent, first principles, opportunity, outside view, execution
   ↓
SPECIALIST: does a bounded job, creates a reviewable artifact and tests
   ↓
INDEPENDENT REVIEWER: validates data, money, permissions, screenshots, code or claims
   ↓
ACTION GATE: safe local action automatically; external/risky action needs OWNER decision
   ↓
RESULT: audit, change log, cost, saved time, failure/retry, customer outcome, next action
```

## Departments (ROLE PROFILES, not always-running models)
| AI capability | Typical outputs | Quality gate / escalation |
| --- | --- | --- |
| Chief of staff / coordinator | morning portfolio brief, priority queue, delegated tickets, blockers | owner approves weekly priorities and external commitments |
| Product / research | interview plan, official sources, competitor gaps, product brief, experiment | show citations, confidence and why NOT to build |
| Engineering | narrow branch, tests-first code, PR, Windows installer, release notes | independent branch+reviewer, mandatory CI, clean-PC field |
| QA / security | link UI click→handler→API→role→DB→visible effect; threat model, reproducible bugs | never reviews own change as sole gate, block high severity |
| Design / films | authentic product screens, visual review, icon system, short verified demos | brand/rights/claims and owner approval before publishing |
| Marketing / sales | segmentation, offers, drafts, consented lead pipeline, objection answers | no unsolicited messages, spend/ad approval, truthful claims |
| Customer success | per-role guided demo, triage and FAQ, onboarding, backup alerts | least-privilege diagnostics, escalate payments/PII/outages |
| Finance / expansion | cash runway, forecast, price tests, COGS, Rafaa opportunities | reconcile source data, owner approves spending and contracts |
| Compliance / partner | dated ETA summaries, rule-change impact, Sanad advisory handoff | named qualified reviewer; explicit cross-company consent |

### Council of five (activate for important choices, never every minor task)
1. **المعارض**: finds likely failure/cheaper alternative.
2. **المبادئ الأولى**: strips assumptions and asks what must be true.
3. **الباحث عن الفرصة**: identifies overlooked upside with realistic evidence.
4. **العين الخارجية**: sees as an Egyptian shop owner, competitor, accountant or regulator.
5. **المنفذ**: smallest experiment, exact acceptance, cost and stop rule.
Council outputs exactly: options, evidence, disagreements, worst-case loss, 7-day experiment, recommendation, decisions requiring owner. Same LLM producing five characters does NOT constitute five independent checks. Where stakes warrant, use a separately run critic/model and external official verification.

## Shared brain / memory (not “unlimited context”)
- **Truth layer 1:** GitHub main + PRs + CI + product manifests for source and release truth. Never let a stale chat override the latest main.
- **Truth layer 2:** existing `DECISIONS.md` and `docs/PIXEL_PLUS_EXECUTION_ROADMAP_2026.md` for approved choices, exceptions and sequencing.
- **Truth layer 3:** a tiny local SQLite **work ledger** (task states, evidence links, reviewer, approval log, real cost, errors). Keep customer identifiers and secrets out of public repositories.
- **Truth layer 4:** source-linked market research and dated official tax/legal references; expire/recheck stale claims.
- Every new agent session starts from a **generated handoff bundle**: product version, last PR, task state, approved scope, tests, known failures, next action. This survives account changes and session limits.
- Use one source of truth per fact, not mirrored editable spreadsheets across tools.

## Workflow catalogue, ordered for revenue
### W1. Finish and sell Store safely (FIRST)
1. Pull latest Store and Factory release, identify actual blockers.
2. Engineer investigates one bug → adds reproduction → fixes on branch → independent reviewer tests exact commit.
3. CI builds Windows installer and verifies seeded shop, upgrade, access, audit and backup. Human still tests clean other PC, receipt printers, keyboard cashier, 14-day shop pilot and signs acceptance.
4. Trial activation uses existing factory licence mailbox/Studio on trusted owner PC with least privilege; never put signer key in a bot or a remote agent. Approve paid licences only after payment proof. Store release readiness and sales tier readiness are DIFFERENT.
5. Next: encrypted versioned off-device restore with owner-approved host, recovery key and Egypt data decision. No one-PC cloud-backup sales promise before second-PC recovery proof.

### W2. Leads to paid trials
- Consented lead via Pixel Plus page/real product demo → sanitize/minimize → record source/product/plan/contact opt-in.
- AI suggests follow-up, offer and demo script in Egyptian Arabic using verified feature evidence. A human approves and sends; neither bot nor website auto-messages prospective clients.
- Trial activation and onboarding → measured activation delay → acceptance → quote → monthly/perpetual decision → after-sale FAQ. Avoid false urgency, invented testimonials or fabricated prices.
- At customer's REQUEST, show Sanad consultation referral with separate permission and engagement scope; never auto-transfer client's finance/payroll information.

### W3. Product video and marketing
- Read real released version and verified user journey → auto-run synthetic shop → capture real browser frames → produce short product video/design from the real app and source-backed claims → visual/accessibility/brand review → owner approve → publish via permitted app/channel.
- Measure inquiries and qualified trials, not vanity impressions alone. AI-generated content must have real value and expertise; avoid mass keyword posts.

### W4. Customer support / incident
- Support asks permission to receive minimal redacted diagnostics → classify issue & severity → use demo/synthetic repro → engineer PR → independent QA + CI → owner approves risky deployment → versioned patch, rollback and customer update.
- Never allow one agent to read all customer databases or deploy ad-hoc code directly onto devices.

### W5. Weekly research & investment council
- Collect official updates, new small-business needs, adjacent successful software, low-cost free tools, ETA changes; score source credibility/datedness and estimated benefit.
- Shortlist no more than **three** experiments. Run council on one high-value decision. Close / postpone ideas that cannot improve revenue, retention or delivery.

### W6. Rafaa / finance / Sanad advisory
- Free Rafaa Radar from available data with honest completeness indicator; paid Rafaa Full as optional module reusing Accounting-sys.
- Human accountant/tax expert signs off reviewed rule updates; citations and effective date mandatory. Sanad sees customer records only after explicit scoped, revocable consent.
- A perpetual local licence never loses already-purchased local features; future human-reviewed legal content and cloud use have explicitly priced maintenance terms.

## Approval & least-privilege matrix
| Action | AI may prepare | Automatic execution? |
| --- | --- | --- |
| Read public sources / synthetic tests / draft and internal branch | yes | yes, with limits |
| Open PR / update internal backlog / run tests | yes | yes, in allowed repo scope |
| Merge into main | yes | ONLY if owner-approved policy, independent review, all required CI green; owner controls exceptions |
| Change customer production data, real backups or secrets | propose only | NO without explicit scoped customer and owner authorization |
| Issue monthly/perpetual licence / confirm payment / refund | prepare/request | NO; owner/payment proof |
| Send customer promotional messages / post ads / pay or sign | draft | NO; prior owner approval and consent |
| Publish tax advice or binding rule | prepare with official sources | NO; qualified review plus owner acceptance |
| Give Sanad employee access to customer details | prepare consent form | NO; customer grants, scope and audit |
| Initiate autonomous trial within previously approved published policy | yes | conditional only after hardened production rollout and caps |

**Never confuse a stored human approval note with authentication.** Any live action adapter must separately verify owner identity, exact action ID, approved payload hash, expiration, least-privilege token, amount limit and consumed-once status at execution time. A chat reply is not an auditable authorization token. Refuse silently inferred approvals.

## Low-budget architecture: reuse before adding
- **Now:** GitHub issues/PRs/Projects and Actions as project tracking and test engine (public standard hosted runners free, subject to storage; private included-minute allowance). Existing Factory + Store + Installer are already the QA engine. Do not run a continuously paid CI runner or buy a VPS. Docs: https://docs.github.com/en/billing/concepts/product-billing/github-actions and https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/quickstart-for-projects
- **Small public edge:** existing Cloudflare Worker + D1 for minimal Telegram notices/approved lead relay, NOT for intensive AI inference or long jobs. Current Workers Free 100,000 requests/day, 10ms CPU/request; D1 Free 5M rows read/day, 100k written/day and 5GB storage. Free has hard limits and can stop until reset: monitor alerts and fail closed for sensitive actions. Docs: https://developers.cloudflare.com/workers/platform/limits/ ; https://developers.cloudflare.com/d1/platform/pricing/
- **Orchestration:** start with static deterministic workflows and one model coordinator using existing Claude Code, Codex or ChatGPT account when available. A future runtime may use OpenAI Agents SDK with tool handoffs, guardrails, resumable human gates/traces: https://openai.github.io/openai-agents-python/ . Model subscriptions do NOT necessarily pay for API calls: https://help.openai.com/en/articles/9039756-managing-billing-settings-on-the-chatgpt-web-and-api-platform
- **Optional:** n8n Community self-hosted on a Windows spare PC for a small internal workflow backlog, only if uptime and security can be maintained. Its free license permits operating workflows for customers but not giving them workflow-editor/configuration access or rebranding n8n as an embedded workflow engine: https://support.n8n.io/article/can-i-use-your-license-for-my-use-case . No operational need to add it initially.
- **Secrets:** owner PC key vault for licensing, GitHub short-lived tokens with minimal permissions for code, protected edge secrets, no secrets in PR/reports/demos/screenshots. Actions secrets are NOT a reason to run untrusted PR code with powerful tokens: https://docs.github.com/en/actions/reference/security/secure-use

## Architecture decision: do not launch a many-agent platform first
1. **Stage A, week 1:** Agree on work ledger, handoff format, departments and human gates. Build a standard-library, LOCAL Windows executable/script prototype, not a hosted company control plane.
2. **Stage B, weeks 2–3:** Wire **read-only** GitHub repository/CI/PR status to morning brief; create and triage issues with separately limited token only after tests. Preserve session-to-session handoff so Claude account limits do not lose progress.
3. **Stage C, weeks 4–6:** product QA pipeline triggers real browser screenshots and Windows checks, critic agent re-checks builder; Telegram sends owner short exception notices. No deploy by bot.
4. **Stage D, weeks 7–10:** consented lead → quote draft → owner-send workflow; 2–3 released product demo walkthroughs; read-only finance dashboard from verified data.
5. **Stage E, weeks 11–13:** scenario Council, ROI experiment weekly, owner dashboard with completion metrics, update one process at a time.
6. **Stage F, later:** context-aware multiple-agent handoffs, separate Sanad service workflows and more products only when clear recurring revenue covers running cost.

### 30 / 60 / 90 day observable acceptance
- Day 30: all active work has owner, due date, status, safe stored handoff, PR/test link; 3 full handoffs verified across separate Claude sessions. One actual customer pilot journey mapped.
- Day 60: 5 critical repeatable workflows have passing synthetic runs and independently reviewed exception handling; weekly briefing shows blocked tasks and wasted AI spend.
- Day 90: first paid pilot (subject to real field acceptance), consented qualified-lead funnel, 10+ measured workflows, a truthful automated-work ratio, no unresolved critical data-loss bug. Measure cost per delivered customer.
- If a metric isn't instrumented, show “unknown”, NEVER estimate “90% today”.

## AI council's critical objections
1. **Autonomy trap:** 20 agents drafting without selling = wasted tokens. Start with one coordinator and event-triggered workers; prove end-to-end output.
2. **Approval theater:** A Telegram “موافق” without cryptographic/session scoping isn't safe for payment/deploy; verify and log exact action before execute.
3. **False automation numbers:** a PR open ≠ accepted, test green ≠ field ready, screenshot generated ≠ actual product run.
4. **Data exposure:** accountants, Sanad and marketing must never share unrestricted real client databases.
5. **Cloud free-tier cliff:** if the free quota runs out, customer local sales must continue; edge relay needs retries, storage quota alarms, and failure status.
6. **Licensing/legal lock-in:** third-party orchestration licenses and Egypt tax sources need dated verification. Never resell a restricted component as your own white-label without rights.
7. **Founder bottleneck:** prioritize three decisions per day in owner's inbox; never require human review of every harmless step. Escalate real exceptions.

## Task object: contract all agents must use
The **canonical** machine-readable contract is [`company-os/task.schema.json`](../company-os/task.schema.json). Every handoff MUST pass `python3 company-os/validate_task.py <task-file.json>`. Every cross-account handoff carries `branch`, `current_commit`, `open_prs`, `known_errors`, `tests_run`, `tests_skipped`, `next_action` and `decision_ref` (use explicit `null` or an empty list when not applicable, never fabricate evidence). The local checker also enforces **different reviewer and assignee identities**, which portable JSON Schema cannot compare by itself. A valid handoff is NEVER permission to deploy, contact customers, charge money or approve expenses.

```json
{
  "task_id": "PX-001",
  "goal": "Review Al-Store 1.7 end-to-end cash-sale and installer acceptance, with independent proof",
  "project": "Store",
  "department": "qa-security",
  "assignee": "reviewer-session-A",
  "reviewer": "reviewer-session-B",
  "risk": "medium",
  "status": "ready",
  "budget_usd": 0,
  "time_cap_minutes": 120,
  "allowed_actions": [
    "read_repo",
    "run_synthetic_tests",
    "draft_report"
  ],
  "requires_owner_approval": [
    "merge_main",
    "production_deploy"
  ],
  "acceptance": [
    "All required CI on exact commit green",
    "Store UI actual click-to-db traces captured",
    "No skipped browser tests counted as green"
  ],
  "evidence": [],
  "customer_data_policy": "synthetic_only",
  "decision_ref": "docs/PIXEL_PLUS_EXECUTION_ROADMAP_2026.md",
  "blocker": null,
  "next_action": "inspect latest main, reproduce 1 sale and produce review bundle",
  "current_commit": null,
  "branch": null,
  "open_prs": [],
  "known_errors": [],
  "tests_run": [],
  "tests_skipped": []
}
```

Allowed statuses (same in contract, playbook and CLI): `backlog → ready → working → review → owner_gate → done`, or `blocked` at any step. Here `review` is always independent; `owner_gate` means an owner decision is **requested**, not granted. No task is `done` until it has at least one referenceable evidence item with a timezone-aware `verified_at`; metadata cannot prove the linked external artifact is genuine, so an independent reviewer must inspect it and production/field acceptance remains separate. Never claim a customer field test was performed based on CI.

A cross-account AI session handoff must include current commit, branch, open PR, known errors, tests actually run/skipped, next safe action and decision source. The validation script fails closed for missing sources, unsupported statuses, invalid JSON and same-person self-reviews. No parallel signing or production deployment based on this metadata.

## Next immediate implementation ticket (most important)
Create **Pixel Plus Company OS Lite**: stdlib Python + SQLite local task queue, event log, safe synthetic fixture, reviewer/evidence requirement, recorded owner approvals, per-task cost ceiling, read-only HTML status. This is a scheduling/control **prototype**, NOT an authentication layer or production agent dispatcher. Then test on Windows and hand a real Store review across two fresh agent sessions. Only after proof add GitHub read-only status, then authenticated owner approval and bot notifications.

## References / further research (official)
- Anthropic, Building effective agents: https://www.anthropic.com/engineering/building-effective-agents
- Anthropic, Demystifying evals for AI agents (Jan 2026): https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents
- Anthropic, Multi-agent research architecture: https://www.anthropic.com/engineering/multi-agent-research-system
- OpenAI Agents SDK, handoffs, tracing, human-in-loop: https://openai.github.io/openai-agents-python/
- GitHub Projects and Actions: https://docs.github.com/en/issues/planning-and-tracking-with-projects/learning-about-projects/quickstart-for-projects
- Cloudflare Worker and D1 pricing/limits: https://developers.cloudflare.com/workers/platform/limits/ , https://developers.cloudflare.com/d1/platform/pricing/
- Google people-first marketing (first-hand expertise required, no mass-content shortcuts): https://developers.google.com/search/docs/fundamentals/creating-helpful-content
- n8n Community licensing: https://support.n8n.io/article/can-i-use-your-license-for-my-use-case
