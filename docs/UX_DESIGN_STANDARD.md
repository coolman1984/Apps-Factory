# Common UX design system, without identical apps

**Goal:** All products feel related to the same quality brand, but their expert workflow is shaped by their user. Standardize tokens, semantics, states, forms and controls, not every business dashboard.

## Visual tokens (recommended foundation, customize by brand)
```css
:root {
  --ui-bg:#f5f6f8; --ui-surface:#fff; --ui-border:#e2e5eb;
  --ui-text:#111827; --ui-muted:#556070; --ui-accent:#2f53ee;
  --ui-success:#14633f; --ui-warning:#865a00; --ui-danger:#a52121;
  --ui-radius-sm:4px; --ui-radius-md:8px; --ui-radius-panel:12px;
  --ui-space-1:4px; --ui-space-2:8px; --ui-space-3:12px;
  --ui-space-4:16px; --ui-space-6:24px; --ui-space-8:32px;
}
```
Use semantic tokens in dark theme and high-contrast mode; product-level brand colors may change within contrast requirements. No one-shot copy of a screenshot; components should be accessible and consistent.

## Shared shell
- Sidebar / nav rail on desktop; phone menu or bottom navigation when task flow warrants it; active item and recent breadcrumbs.
- Topbar with organization/context, global search/quick action, role, language, user menu and connection state.
- Optional right inspector for details without leaving context. For 3D/canvas/editor, minimize shell and give canvas priority.
- Page header: human title, what the user can do here, clear primary action and optional contextual help.
- Data tables: sticky/readable headers, explicit count, search, sort, filters, server pagination, clear export semantics, keyboard navigation.
- Forms: visible labels, grouped related fields, required/optional, inline validation, save state, disable double-submit, confirm high-risk actions, undo/reverse where appropriate.
- Dashboards: only decision-driving measures with data date/filters and source; never decorative random charts.
- Empty states: explain why empty and one next action. Connection error shows retry; permission denied explains role, never leaks restricted records.
- Responsive: check narrow mobile, tablet and desktop, browser zoom at 200%, touch target, keyboard-only and screen reader basics.

## Arabic/English correctness
- Proper RTL mirroring, **not** rotating charts, numeric codes or brand logos.
- Arabic line-height/typography built for legibility; independent date/currency/number formatting (Egypt vs Saudi vs UAE) and 12/24-hour preferences.
- Strings from message catalogs, not scattered hardcoded UI labels; tests cover parity and truncation.
- Contrast and consistent focus indication, appropriate live region updates for save/load/error messages.

## Motion and progressive disclosure
- Motion should communicate navigation/state, never hide data loading or draw attention without reason; honor reduced motion.
- Hide advanced admin/setup until relevant, but security controls are server-side and must exist even when the menu is hidden.
- Help must be contextual and plain language. Domain terminology verified with actual operators.
- Onboard with isolated demo data and one 3-step goal, not a tour of 60 buttons.

## Component contract
For every shared component: behavior, properties/tokens, error and empty states, RTL/dark behavior, keyboard semantics, accessibility test, sample screenshot, owner and version. Changes are reviewed across **two** example apps before publication as shared.
