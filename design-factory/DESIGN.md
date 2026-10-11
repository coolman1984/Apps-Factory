# DESIGN.md — Global Product Design Standard v2 (2026-10-08)

## Mission
A design factory must deliver a visibly excellent, measurable, accessible product experience, not merely copied CSS. Every product consumes the factory's versioned tokens, component rules, icon grammar and visual quality gates.

## Mandatory workflow
1. Inspect live desktop, tablet and mobile UI; capture baseline and critical user journey.
2. Review 3–5 best-in-class sector-specific interfaces; extract hierarchy, spacing, density, interaction and typography principles without copying trademarks.
3. Produce three visual directions and choose one against operator needs.
4. Build a complete design system before changing all pages: tokens, fonts, icon sizes, spacing, components, states, responsive patterns and motion.
5. Implement one complete working slice, review actual screenshots, then roll out consistently.
6. Run functional, accessibility, visual-regression, offline and performance checks; attach before/after screenshots and a defect list to PR. No visual approval based only on automated test scores.

## Measurable default geometry (CSS px, adjust only with documented reason)
- Base spacing rhythm: 4; use 4, 8, 12, 16, 24, 32, 48, 64. No arbitrary 5/11/19px spacing without rationale.
- Body font 16px / line-height 1.5; dense data 14px / 1.5 minimum; supporting text 14px. Page heading 28–32px, section heading 20–24px; preserve typographic hierarchy.
- Arabic: choose a professionally licensed and locally bundled Arabic UI font with full numerals and weight coverage, or a verified readable system fallback. English typography must align in perceived size. Never load fonts from CDN in offline apps.
- Icons: 20px standard, 24px navigation emphasis, 16px inline; consistent stroke, optical alignment and icon-to-label gap 8–12px. Icon-only buttons require accessible names.
- Buttons: 44px preferred minimum height, 48px for touch-primary actions; interactive targets at least 24x24 CSS px with sufficient separation, preferably 44x44.
- Inputs: 44–48px high; labels visible; error/help states; focus ring ≥2px; controls aligned to the same baseline.
- Cards: padding 16–24px, inter-card gap 16–24px, section gap 32–48px; avoid nested-card clutter.
- Content: responsive grid with 16–24px gutters, deliberate max width where appropriate, and compact transaction-specific layouts.
- Contrast: WCAG 2.2 AA, normal text ≥4.5:1 and large text ≥3:1; do not rely on color alone.
- Motion: functional 120–200ms, no obstructive effects on cashier/critical operations, honor reduced-motion.
- Support RTL Arabic and LTR English, dark/light, 320px minimum, 200% zoom, keyboard navigation, and the empty/loading/error/success/permission-denied states. What «no internet» means depends on the product's connectivity tier (next section): a product is never asked to work offline when its tier says it cannot, and never allowed to fail silently when it can.

## What «no network» looks like, by connectivity tier
The tier is `connectivity.tier` in the product manifest (see `docs/CONNECTIVITY_AND_SYNC.md`). The gate is the control **UX-04**: the states below are tried in a real browser with the failure injected, and the result is attached.

| Tier | The product must show and test |
|---|---|
| `standalone` | Works fully with the network unplugged; nothing waits on the internet (updates, telemetry, licence relay fail quietly and retry later) |
| `office_server` | On the main PC: everything works. On another PC: a plain «the main PC is off» state, reads that are cached are labelled as such, writes are refused with the way out (no half-saved screen) |
| `office_mesh` | Every PC works alone; a visible «will merge when connected» state; no silent loss |
| `cloud_sync` | Every device works alone and queues; the queue's size and age are visible; a rejected change is shown, never dropped |
| `cloud_only` | Not asked to work offline. It shows an actionable disconnected state: what happened, that nothing was lost, what the person can do (retry, keep the form), and it keeps typed input |

## Quality gates by class
The class is the product's profile (`desktop`, `lan`, `saas`) and its tier. Every gate below is a **core** control, so `factory.py check --release` fails when its proof is missing; a screenshot is evidence only when it was taken from the running product and looked at by a person.

| Gate | Control | Applies to | How it is enforced |
|---|---|---|---|
| Tokens only, contrast and base sizes | UX-09 | desktop, lan, saas | `design-factory/qa/token_gate.py`, or a test of the product's own with the same thresholds (Store: `tests/test_frontend.py::DesignSystem`) |
| No text outside its box, at 3 widths, in every language | UX-08 | desktop, lan, saas | the product's measured layout sweep, shown failing on a known overflow |
| Speed on a slow CPU | PERF-01 | desktop, lan, saas | `tools/ui-lab` against `factory/ui-budgets.json` |
| Accessibility | A11Y-01 | desktop, lan, saas | axe-core zero serious or critical, plus a manual keyboard journey |
| The network-failure states above | UX-04 | desktop, lan, saas (by tier) | failure injected in a real browser |

## Quality gates
- **Enforced by code:** `python design-factory/qa/token_gate.py <product>/tokens.css --pairs … --min fs=16 --min tap=44 --min icon=20`
  fails the build when a text/background token pair is below 4.5:1 in any theme or a base size is below the standard.
  Each product runs it from its own tests (Store: `tests/test_frontend.py::DesignSystem`).
- Pixel-level alignment checks for buttons, icons, card edges, tables and text baselines.
- Browser matrix: 1440x900, 768x1024, 390x844, 320px narrow; Arabic/English × light/dark.
- No accidental page overflow, clipped labels, overlapping icons, inaccessible dialogs, fake controls, lost focus or unreadable content.
- Test real business journey before and after changes; money, stock, audit and permissions must remain unchanged.
- Design review records visual coherence and human sign-off separately from performance/accessibility pass.
- Any failed gate blocks merge; missing browser proof is UNVERIFIED, never PASS.

## Reuse architecture
Factory owns the canonical tokens and reusable components. Each app owns its brand identity and task-specific layout. Prefer a single versioned foundation, never blend unrelated UI kits. Record factory version in each product's DESIGN.md and upgrade via reviewed PR. Creative effects are optional, budgeted by context and tested for performance.

## Store launch direction
**Implemented 2026-10-08** in Store (design system v2, see `Store/docs/DESIGN.md`): navy rail, ivory canvas, copper only for
the one action that matters; 16px body, 14px data, 20px icons, 44px controls; 3D tilt/spotlight/blur removed; logo files and
Windows icon from one mark geometry. **Name (decision 2026-10-10):** the product is **Al-Store · الستور**. The working name «Mizan | ميزان» proposed here is **withdrawn**: `Accounting-sys` is the owner's accounting product and is already called Mizan, so one name for two products would confuse customers, licences and support. Any new brand name is the owner's decision after a trademark and domain check (EG, SA, AE); until then nothing is renamed beyond الستور.
Identity (kept, independent of any name): balanced geometric storefront mark, deep midnight navy, warm ivory, restrained copper accent. Design for trusted multi-branch retail operations, not a playful consumer shop. Keep the cash register dense and fast, with restrained animation and unmistakable payment hierarchy.
