# UI Lab ⚡ — performance + accessibility gate

Measures what a person feels on a ×4 slower CPU: FCP, LCP, CLS, TBT, INP, scroll frame p95 and dropped frames, DOM size, JS
heap and transfer, overflow, axe-core serious/critical issues and console errors, per page × screen size, against
`factory/ui-budgets.json`. Standard: [docs/PERFORMANCE_STANDARD.md](../../docs/PERFORMANCE_STANDARD.md) (PERF-01, A11Y-01).

```bash
npm install            # pinned playwright + axe-core; uses the system Chromium if PLAYWRIGHT_BROWSERS_PATH is set
node probe.mjs --config ../../../Store/ui-lab.config.json --out report/      # exit 1 when over budget
node probe.mjs --config <cfg> --quick --routes home,pos --cpu 4
```
Output: `REPORT.md`, `report.json`, screenshots. Commit the report into the product's `docs/ui-lab/` per release candidate.
axe-core is injected through DevTools (`Runtime.evaluate`) so the product's CSP is tested exactly as shipped.
