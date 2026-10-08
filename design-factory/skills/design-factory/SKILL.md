---
name: apps-factory-design
description: Build and verify beautiful, distinctive, accessible Arabic/English software interfaces using Apps Factory's design tokens and curated, pinned upstream UI references. Use whenever designing, reviewing, refactoring or building user-facing screens.
---

# Design Factory: portable agent skill

## Mandatory context
Read root `AGENTS.md` and `design-factory/AGENTS.md`, then `design-factory/DESIGN_CONSTITUTION.md`, `design-factory/WORKFLOW.md`, `design-factory/QA_CHECKLIST.md` and `design-factory/UPSTREAMS.md`.
Review current app's `DESIGN.md` and existing user flow. Existing production design choices outrank a generic gallery; preserve working behavior.

## Motion, icons, layered website and film requests
When task mentions animation, parallax, transitions, 3D, motion graphics, microinteraction, icons, cinematic sites, video or slides: read `design-factory/CREATIVE_AGENT_PLAYBOOK.md`, `design-factory/CREATIVE_ARCHITECTURE.md` and `design-factory/creative-sources.lock.json`. Choose the least-cost recipe from `creative-recipes/`, reuse local primitives or existing specialized Animation/Slide Forge engines, verify licensing and inspect rendered screenshots / final film. Do not turn admin CRUD screens into videos.

## Work mode
1. Define persona, high-stakes task, one-sentence outcome; inspect app architecture and original screens before edits.
2. Research sector-specific successful interfaces, choose one style, build an explicit design-brief and tokens. For new visual direction, propose three distinct options and make a user-centered selection. No unlicensed brand copying.
3. Prefer Apps Factory `core/tokens.css` and `core/components.css` in HTML/Python apps; select Tabler OR Web Awesome if external kit is required. React apps may choose shadcn/ui. Do not import whole vendor directories by default.
4. Implement actual flows, labels, states and data/permission checks, not static fake cards.
5. Inspect the running browser at mobile/tablet/desktop, AR/EN, dark/light, keyboard, zoom; capture real screenshot evidence. Fix issues and repeat.
6. Report actual files, tests, screenshot paths, remaining issues and release verdict. NEVER claim visual QA without browser inspection.

## Success criteria
Accessible, coherent, delightful UI specific to the domain; measurable task completion; strong information hierarchy; responsive layouts; clean typographic rhythm; no dead controls, unverified screenshots, clipped Arabic or arbitrary pill/card spam. Maintain product security, local offline support and author permissions from root Apps Factory.
