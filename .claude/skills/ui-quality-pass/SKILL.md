---
name: ui-quality-pass
description: Measure and fix a product's UI speed, smoothness, layout and accessibility with the factory UI Lab and the layout sweep. Use before any release candidate or after UI changes.
---
# UI quality pass
1. Start the product in practice/demo mode on a free port (synthetic data only).
2. `cd tools/ui-lab && npm install && node probe.mjs --config <product>/ui-lab.config.json --out <product>/docs/ui-lab` (exit 1 = over budget).
3. Read REPORT.md. Fix in this order: console errors → axe serious/critical → overflow → CLS → TBT/INP → frames. Look at every screenshot.
4. Run the product's browser sweep (360 / 390 XL text / 820 dark / 1366 English).
5. Apply docs/DESIGN_SYSTEM.md §7 non-negotiables; check the Showroom rubric in docs/QUALITY_SYSTEM.md.
6. Re-run until "All pages within budget". Changing a budget needs two passing runs and a written reason in `factory/ui-budgets.json`.
7. Record before/after numbers in the product's DEVELOPMENT_HISTORY and add a lesson to docs/knowledge/LESSONS.md if new.
