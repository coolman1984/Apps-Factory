# Archive

Kept for history, not maintained. Read the living docs first: [README](../../README.md), [RULES](../../RULES.md), [PARTS](../../PARTS.md), [PLAYBOOK](../../PLAYBOOK.md), [DECISIONS](../../DECISIONS.md). Some numbers inside (for example "97 controls" or "6 sources") are out of date on purpose.

| File | Why archived | What replaced it |
|---|---|---|
| [ADOPTION_PLAN.md](ADOPTION_PLAN.md) | Old phased plan for introducing the factory to existing products | [PLAYBOOK.md](../../PLAYBOOK.md) (add a product) and [DECISIONS.md](../../DECISIONS.md) |
| [BUILD_PLAN.md](BUILD_PLAN.md) | Old build plan (Arabic, from "97 controls" days) | [PARTS.md](../../PARTS.md) for what exists; [DECISIONS.md](../../DECISIONS.md) for open owner choices |
| [COMMERCIAL_PLATFORM_BENCHMARK.md](COMMERCIAL_PLATFORM_BENCHMARK.md) | Research on commercial platforms, not a rule | Nothing needed; the findings fed the controls in [RULES.md](../../RULES.md) |
| [FACTORY_CONSTITUTION.md](FACTORY_CONSTITUTION.md) | 26 commitments; the checkable ones became controls, the rest overlapped the ADRs | [RULES.md](../../RULES.md) (core controls, privacy limits, workflow) and the ADRs in [DECISIONS.md](../../DECISIONS.md) |
| [HESSA_FACTORY_ALIGNMENT.md](HESSA_FACTORY_ALIGNMENT.md) | One-time comparison of the first product with the factory (2026-10-08) | The resulting controls in `factory/controls.json` and [docs/knowledge/CAPABILITY_MATRIX.md](../knowledge/CAPABILITY_MATRIX.md) |
| [MARKET_AND_STANDARDS.md](MARKET_AND_STANDARDS.md) | Market and standards research | The controls catalogue; [RULES.md](../../RULES.md) |
| [OPEN_POINTS.md](OPEN_POINTS.md) | Decided and open items, merged into one file | [DECISIONS.md](../../DECISIONS.md). A redirect stub stays at `docs/OPEN_POINTS.md` because `apps/control-center/control_center/alerts.py` and `templates/telemetry-relay/README.md` name that path |
| [PENDING_WORKFLOW_CHANGES.md](PENDING_WORKFLOW_CHANGES.md) | CI steps that were waiting for a token with workflow rights; all are now in `.github/workflows/factory-checks.yml` | The workflows themselves; [PLAYBOOK.md](../../PLAYBOOK.md) lists the commands |
| [REPOSITORY_AUDIT.md](REPOSITORY_AUDIT.md) | Review of 30 of the owner's repositories | [docs/knowledge/REPO_MAP.md](../knowledge/REPO_MAP.md) |
| [UX_DESIGN_STANDARD.md](UX_DESIGN_STANDARD.md) | Duplicated the design system | Its states, forms and RTL rules are now section 9 of [docs/DESIGN_SYSTEM.md](../DESIGN_SYSTEM.md) |
