# Canonical Design Factory contract for ANY coding agent

When working on UI/UX, first read `design-factory/DESIGN_CONSTITUTION.md`, `design-factory/WORKFLOW.md`, `design-factory/QA_CHECKLIST.md`, `design-factory/UPSTREAMS.md` and existing repo-specific `DESIGN.md` if present. These instructions complement root `AGENTS.md`, which still governs security, data, test and release constraints.

## Creative Factory specialist route
When making icons, cinematic layers, animation, motion graphics, video, scroll-story, 2D/3D or interactive effects: **MUST read** `design-factory/CREATIVE_AGENT_PLAYBOOK.md`, `design-factory/CREATIVE_ARCHITECTURE.md` and `design-factory/creative-sources.lock.json`. Pick exactly one complexity tier from `design-factory/creative-recipes/`: essential / polished / cinematic / film. Inspect the running example `creative-lab/index.html`. Use original `core/creative-effects.css` and `core/creative-primitives.js` for local apps before opting in to heavyweight external engines. Explicitly test reduced motion, RTL/LTR, browser matrix, web performance and licensing. Film work routes to the pinned owner Animation Studio, not a duplicated film engine.

## A design task is NEVER "just make it pretty"
1. Identify the operator and their most important job; capture the **current** screen and its existing behavior before editing. Do not hallucinate unseen screens.
2. Inspect product constraints: existing frontend stack, AR/EN, offline Windows, roles, target screen sizes, density, typography and domain patterns. Research relevant *sector* competitors, not a generic gallery.
3. Build a small `design-brief`: target user, one-screen purpose, content hierarchy, existing flow, inspirations, selected design DNA, constraints and acceptance.
4. Select **exactly one main foundation**: vanilla core; Tabler (Bootstrap); Web Awesome (web components); or shadcn/ui (React). Optional UI UX Pro Max is research guidance, not production runtime.
5. Reuse tokens and components; keep semantic HTML and true program behavior. Avoid mixing kits, hardcoded arbitrary margins, stock dashboards, random colored cards, huge corner radii, icons used in place of clear labels.
6. Implement AR RTL and EN LTR; test logical properties, numbers/dates, table overflow, keyboard focus, 200% zoom and accessible reduced motion.
7. Run static checks AND launch actual app in browser for screenshot and workflow evidence at 1440x900, 768x1024, 390x844 in light/dark and AR/EN; compare to approved visual. If browser unavailable, record UNVERIFIED; never imply inspected.
8. Provide before/after evidence, test commands, remaining defects and screenshot paths. Changes require PR, small focused diff, no breaking permission/business logic.
9. If a user asks to "copy design", extract composition/spacing/motion principles but respect copyright, branding, and assets. Do not illegally reproduce protected assets or trademarks.

## Runtime choice
- Existing HTML/CSS/JS/Python: reuse `core/*.css` and vanilla semantic patterns. Tabler only if deliberate Bootstrap adoption; Web Awesome only if Web Components adoption is tested.
- Existing React: optional shadcn UI components and TypeScript using consistent tokens; no parallel "second theme".
- Existing 3D, editor, video canvas: shared title/controls/status/settings only, do not force admin-dashboard layout.
- Offline sales application: bundle approved assets/fonts; no fonts/CDN at runtime; check licenses.

## Design work is rejected when
Any overflow/tilt/clipping, unclear primary action, fake button, broken RTL, unreadable text/contrast, missing keyboard affordance, exposed role action, screenshot/implementation mismatch, untested dark mode, unhandled empty/loading/error states, or invented "quality passed" claims.

## Truth
`design-factory/reference` is a **synthetic visual reference**, not a reusable product backend. Any production functionality must go through appropriate Apps-Factory identity/authz/data/licence modules.
