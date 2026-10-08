# End-to-end design production line

Each stage has an observable artifact. Agent must never claim stage completed if evidence missing.

**D0: Inspect.** Identify existing source and route, take screenshots of current desktop and mobile screens, list interactions and user journey. If app cannot run or screen is unavailable, record BLOCKED and do not hallucinate screenshots.

**D1: Research.** Inspect 3–5 strong product-specific UX references, reputable admin UI patterns and support/accessibility expectations. Record source URLs, date, layout, workflow and "do not copy" trademarks. Distinguish customer interview results from a model's hypothesis.

**D2: Design brief.** Create `design-brief.md` using the template. Define operator, purpose, primary action, information hierarchy, screen density, AR/EN, target offline deployment, logo/assets and desired identity. Pick one approved framework.

**D3: Three directions, one choice.** When establishing a brand-new visual system, create exactly three distinct visual directions: restrained editorial, operational high-density and expressive premium (or justified alternatives). Prefer mockups or runnable reference snapshots. Choose based on persona/job; no product rewrite before selection. For existing locked design, modify only intended components.

**D4: Systemize.** Name semantic color/spacing/typography/motion tokens and shared components. Ensure permission and business data remain sourced from existing backend contracts. No CDN dependencies if the sold product is offline.

**D5: Implement one slice.** Start with first screen + table/form + one full operator task, including loading/empty/error/success/offline states. Show real data only if customer-approved; demo seeded synthetic.

**D6: Verify in browser.** Viewport matrix: 1440x900 and 390x844 minimum, plus 768x1024. AR/EN and light/dark. Mouse, keyboard, touch where relevant, 200% zoom, low-contrast controls, reduced motion. Compare to chosen reference pixel-level for unwanted regressions; qualitative design QA for spacing/composition. Fix then reshoot.

**D7: Release.** Attach screenshot evidence and functional tests to PR. Run accessibility and security/role tests. Label remaining defects. Do not approve a customer-facing product if design evidence absent; no "perfect" claims.

## Source roles
- UI UX Pro Max: visual inspiration search, never silent runtime dependency.
- Tabler: vanilla/Bootstrap route; preserve MIT license and third-party licensing.
- Anthropic frontend-design skill: style guidance only; only relevant Apache 2.0 subset.
- Vercel guidelines: UX/performance/code review; fetch reviewed rules from upstream (upstream contents not automatically a dependency).
- shadcn/ui: React/TypeScript existing products only.
- Web Awesome: Web Components route, if selected instead of Tabler.

## Evidence record for each PR
```
Product / screen / before commit / after commit
Reference inspiration URLs and licenses
Chosen foundation, token version, accessibility target
Screenshots: desktop/mobile/tablet × AR/EN × light/dark
Interactions: loading, errors, user tasks, denied access
Tools/tests run and output
Visual defects detected and fixed
Actual browser review by whom
Unverified cases and reasons
Decision: PASS | NO-GO
```
