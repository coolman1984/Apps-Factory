# Design constitution v1 • calm, precise, distinctive operational software

## Visual DNA
- Premium industrial/editorial clarity, high information density where operators need it, generous whitespace *between* sections, not giant decorative KPI cards.
- Structure through thin borders, deliberate 8px spacing rhythm, crisp typography and restrained accent. No gradients/glassmorphism/shadow piles by default.
- Quiet motion (120–200ms), functional hover/focus/feedback; honor reduced-motion.
- Brand identity is configurable per app: icons, logo, color, product wording, approved typography. Never lift competitors' exact brand assets.
- Never fake real KPIs. Every number shows its context, unit, filters, source/freshness; synthetic examples clearly marked.

## Consistent component language
- `af-button` / button states: primary, secondary, destructive, disabled, busy, keyboard focus.
- `af-field`: visible label, hint/error, required marker, keyboard and proper autocomplete.
- `af-table`: readable header, no hidden columns on small screens, deliberate horizontal overflow and actions; empty/loading/error states.
- `af-sidebar` and breadcrumbs: active context, mobile drawer, logout state, accessible navigation.
- `af-alert`/toast: clear action required, type, dismissal where safe; no toast-only error reporting.
- Dialog: purpose, Escape, focus trap/focus return, irreversible confirmation, permissions.
- `af-status`: offline/online/saving/failed/success semantics + visible text, not just color.
- Specific domain components (3D canvas, medical workflows, schedule, finance ledger) remain independent.

## Visual acceptance tests
- No horizontal page scrolling at 390px unless an individual table/canvas declares its own scroller.
- AR RTL and EN LTR both readable; physical device visuals not reversed (e.g. serial numbers, player timeline).
- Text not truncated at 200% zoom, 320px width, and browser font scaling without a conscious documented alternative.
- Keyboard: visible focus for all controls; Enter/Space operate buttons; tab ordering matches logic; Escape closes navigation/dialog.
- Correct contrast and labels in both themes; check WCAG 2.2 AA with automated tools + keyboard/screen-reader inspection.
- Empty, loading, error, success, permission denied and offline UX tested for each data-intensive screen.
- Input saving state and duplicate submit prevention; 3-click "happy path" only when user testing validates it.

## Layout tokens
Source of truth `core/tokens.css` and `core/components.css`; typography is system-font by default so Windows offline package is self-contained. Product can ship licensed local font files instead.

## Brand evolution
Modify tokens through one versioned package; emit screenshot comparison and compatibility notes across two reference apps; track tokens as semver. Never fork dozens of subtly different theme variables in products.
