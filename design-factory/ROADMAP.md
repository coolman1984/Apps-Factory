# Design Factory implementation and adoption roadmap • 2026-10-08

**States:** DONE means files exist in Apps Factory, not that every downstream app is redesigned. VERIFIED means GitHub CI/actual browser proof for exact commit; accepted only with human review and field evidence.

| Stage | Outcome | Current state | Exit gate |
|---|---|---|---|
| DF0 | Choose six upstream UI/agent sources; pin SHAs, inventory licences and avoid wholesale vendor assets | DONE: six gitlinks and written provenance, **not personal forks** | File SHA, `.gitmodules`, licence and source changes checked |
| DF1 | Publish original semantic theme and component baseline | DONE: `core/tokens.css`, `core/components.css` | Static contracts, rendered light/dark, RTL/LTR reference |
| DF2 | Bilingual offline UI example with actual interactions | DONE in source: `reference/index.html` and `app.js` | Playwright screenshot matrix, full journey and human visual approval |
| DF3 | Reusable agent contract for all popular coding environments | DONE: root `AGENTS.md`, Claude, Gemini, Cursor, Cline, Copilot, portable skill | New agent enters repo and follows canonical rules; no conflicting instructions |
| DF4 | Adopt in **Hessa** pilot without breaking product | NOT STARTED | Capture existing screens, one approved design, refactor one page, AR/EN/dark/light proof, customer journey unaffected |
| DF5 | Adopt in **Trip Orders** and shared shell | NOT STARTED | Two-product visual regression and CSS API compatibility; extract reusable component package v1 |
| DF6 | React-specific adapter for Space Planner/Business Template | NOT STARTED | Adapt only where valuable, preserve existing React/editor choices, real accessibility+visual QA |
| DF7 | Commercial design acceptance per shipped app | NOT STARTED | Full product screenshot matrix + performance + keyboard + errors + customer acceptance |

## Concrete adoption order
1. Hessa: sign-in/organization admin/navigation; staff intake and dues table; critical reception workflows must not regress. Do not rewrite its Python business logic to match a CSS kit.
2. Yousef Transportation: trip list/approval/export using **the same** shell and tokens. Preserve existing rates, receipts and offline/driver-link boundaries.
3. 3D-Modeling: only shared shell, settings and forms. Canvas/editor may require a radically different spatial layout.
4. Business-Template: use adapter to its existing design system; keep existing security and tenant isolation. Do not force a second React component library unless chosen intentionally.

## Development contract
- UI quality measured by reproducible snapshots, *human* aesthetic review, actual user task success and accessibility/failure cases. Snapshots alone are not proof of beauty or UX.
- Fix token/component changes in one place; keep backwards-compatible versioned CSS variables and changelog before rolling out.
- Each product retains specialized branding while the family shares interaction principles, consistency and design QA.
- Do not deploy complete upstream forks or node_modules as part of each Windows product. Bundle only audited production assets.
- Archive version/commit and design-brief in each product to reproduce exactly which factory release was used.

## Ownership
- **Apps Factory:** canonical components, design skill and QA.
- **Upstream sources:** research/optional implementation references and original licences.
- **Individual apps:** distinct product branding, domain screens, approved client workflows and release acceptance.
