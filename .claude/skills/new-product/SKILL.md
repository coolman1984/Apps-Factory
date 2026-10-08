---
name: new-product
description: Start a new commercial product with the Apps Factory — research, manifest, controls, first end-to-end journey. Use when the owner asks for a new program/app.
---
# New product
1. Read AGENTS.md, FACTORY_CONSTITUTION.md, docs/knowledge/README.md (repo map, capability map, lessons).
2. Research with cited sources (law, tax, competitors, prices, the customer's city) → `docs/01-research.md` in the product repo. Label unknowns UNKNOWN.
3. Write acceptance criteria (A1…An), each mapped to a test → `docs/02-product-spec.md`.
4. `python scripts/factory.py new …` → edit → `python scripts/factory.py check <manifest>`; copy into `examples/` (see `examples/al-store-product.json`).
5. Reuse: af-license codes (`scripts/vendor_licence.py <product>`), af-ui (copy css/fonts/img/js), UI Lab config, Hessa/Al-Store server patterns (ledger tables, computed balances, idempotency keys, approvals before tx).
6. Build ONE paid journey end to end with tests (domain, API + role denial, frontend static, real browser + layout sweep), both dictionaries, help pages.
7. Run the `ui-quality-pass` skill; fill docs/QUALITY_SYSTEM.md Q1–Q8; Q9–Q11 stay PENDING until field work.
8. Report: what changed, commits, tests actually run, what is pending in the field.
