> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Performance department — UI Lab ⚡

**Status:** `implemented` (`tools/ui-lab`), first run on Al-Store 1.0.1: all pages within budget. Controls `PERF-01`, `PERF-02`, `A11Y-01`.

## Why
Our customers' PCs are old and their phones mid-range. "It works on my laptop" hides 300 ms freezes, janky scrolling and
unreadable grey text. The UI Lab measures what a person feels, with the CPU slowed ×4, on a cold load of each page.

## What it measures (per page × screen size)
| Measure | Meaning for the user | Budget (`factory/ui-budgets.json`) |
|---|---|---|
| FCP / LCP | "Something shows" / "the main thing shows" | ≤ 1.8 s / ≤ 2.5 s |
| CLS | Things jump while I read | ≤ 0.1 |
| TBT (×4 CPU) | The page ignores my clicks while loading | ≤ 300 ms |
| INP | A click answers | ≤ 200 ms |
| Frame p95 + dropped frames while scrolling | Smoothness | ≥ 30 fps for 95 % of frames, ≥ 65 % of frames at 60 fps |
| DOM nodes, JS heap | Memory on old PCs | ≤ 3000, ≤ 60 MB |
| JS transfer per page | Download on a weak link | ≤ 300 kB |
| Overflow | Page wider than the screen / element off-screen | 0 |
| axe-core serious + critical | Usable by everyone | 0 |
| Console errors | Hidden breakage | 0 |

## How to run
```bash
cd tools/ui-lab && npm install                      # playwright + axe-core (pinned)
node probe.mjs --config ../../../Store/ui-lab.config.json --out report/   # exit 1 when over budget
node probe.mjs --config … --quick --routes home,pos # one screen size, faster
```
The product keeps a `ui-lab.config.json` (base URL, sign-in steps, routes, screen sizes, one interaction per page) and commits
`docs/ui-lab/REPORT.md` for each release candidate. axe-core is injected through DevTools so the product's CSP stays as shipped.

## Lessons from the first run (Al-Store)
- Backdrop blur on sticky surfaces: ~20 ms/frame on the slowed CPU → removed (PERF-02).
- A results grid that grows above the receipt on phones: CLS 0.57 → 0 by scrolling inside its own area and reserving skeletons.
- Frame times are vsync-quantised (16.7 / 33.4 ms) and noisy by ±5 fps between runs; a budget is tightened only after two passes.
- Grey hint text at 3.9:1 failed contrast on 100+ nodes; one token fix (`--ink-3`) solved all of them.

## Optimisation checklist (before blaming the PC)
No framework, no build step, ES modules split per page (lazy `import()`), gzip + ETag on static files, fonts subset and
preloaded, JSON gzip above 2 kB, list pages capped (search, not 10 000 rows), skeletons of the final shape, transitions only on
`transform`/`opacity`, no layout thrash in `requestAnimationFrame`, no decorative effect without a UI Lab number.
