# Mandatory instructions for every AI coding agent

## Read order
1. README.md → FACTORY_CONSTITUTION.md → docs/PLATFORM_ARCHITECTURE.md
2. docs/MARKET_AND_STANDARDS.md → docs/REPOSITORY_AUDIT.md
3. factory/controls.json → factory/product.schema.json → templates/*
4. docs/DELIVERY_GATES.md and docs/ADOPTION_PLAN.md

## Task classification
- **New product:** perform cited market research, jurisdiction/customer/risk discovery, define the single paid core journey and cut deferred features; get owner approval for business assumptions that materially change price, liability or sensitive-data handling.
- **Existing product:** audit before altering. Preserve working design, real records, backwards compatibility and migrations. Don't overwrite main or copy older shared code into it.
- **Platform improvement:** implement once in a versioned, separately tested shared package, with example consumer tests. A Markdown requirement does not equal working software.

## Non-negotiable agent workflow
1. State customer/persona, core pain and objectively checkable acceptance criteria.
2. Inventory existing modules and trustworthy evidence. Label unknowns **UNKNOWN**.
3. Produce a product manifest and market/competitor evidence; distinguish facts from ideas and marketing promises.
4. Pick deployment and data/financial sensitivity. Activate **applicable** factory controls, not all features for all products.
5. Reuse a versioned shared capability; feature-specific code stays in product-owned folders.
6. Deliver one thin customer workflow **end-to-end**: correct permissions, save/retry, errors, audit, report and recovery.
7. Tests: unit, integration, role-denial, tenant/scope, rollback, backups/restoration, browser UI including AR/EN/RTL, accessible keyboard use; target OS installer where relevant.
8. Record evidence at every release gate; unresolved security/financial/data-integrity issues are NO-GO.
9. Use a PR, review, CI and small safe merge; do not force-push or mass-merge unrelated divergent branches.
10. Return: what changed, exact commit/PR, tests actually run, checks skipped, field checks pending, and next commercial decision.

## Credentials and owner support
- Never publish `admin/123` or any static production credential, never silently create a developer backdoor, never enable an insecure demo shortcut in production.
- Demo quick login is allowed only for isolated synthetic fixture builds, explicitly tagged DEMO, with no real customer data, remote access, payments or production keys; CI proves production flags reject it.
- Customer admin and vendor support are different roles. Support is user-approved, scoped, time-bound, audited, revocable and defaults off.
- No credentials or personal data in source, logs, screenshots, public issues or fixtures.

## Release gate
Do not claim "ready to sell" because CI passed. Clean install, actual peripheral, recovery drill, scoped terms and first paying user's acceptance are distinct gates.
