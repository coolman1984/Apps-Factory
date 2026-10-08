# Factory design system — "Showroom" (af-ui v0.1) 🎨

**Status:** `implemented` in one product (Al-Store 1.0) and the Licence Studio; shared as `packages/af-ui`. Control `UX-09`.
It upgrades [UX_DESIGN_STANDARD.md](UX_DESIGN_STANDARD.md) (which stays the rulebook for states, forms and RTL) with a concrete,
measured visual language. A product may re-brand the tokens; it may not drop the rules below.

## 1. The idea in one line
A calm floor, cards that sit at clear heights, one bright action per screen, and motion that always has a cause.
Users are shop owners and cashiers: the design must feel premium **and** stay fast on an old PC and readable in a noisy shop.

## 2. Layers (the "layers" trend, done responsibly)
| Layer | Token | Shadow | Used for |
|---|---|---|---|
| Floor | `--canvas` + two soft light pools (static, scrolls with the page) | — | page background |
| Surface | `--surface` | `--shadow-1/2` (+1 px inner highlight) | cards, tables, tiles |
| Raised | `--raised` | `--shadow-3` | dialogs, side panels, sheets, the counter receipt |
| Dock | dark gradient rail | `--shadow-3` | navigation (desktop rail, phone bottom dock) |

Depth comes from shadow stacks and a hairline, not heavy borders. **Measured rule (PERF-02):** no `backdrop-filter` on sticky or
large elements — the UI Lab measured ~20 ms per frame on a ×4 slower CPU; an opaque gradient gives the same look for free.

## 3. Colour
Ink (`--ink #12161b`) + **volt** (`--volt #c6f432`, the single most important action: Sell, Pay, Activate) + copper (warmth, avatars).
Trust colours mean one thing each: ok / warn / bad / info. Grey text `--ink-3` is 5.2:1 on white (AA); never lighter.
Themes: day, night, high-contrast; `prefers-color-scheme` respected; a theme is a token swap, never a view change.

## 4. Type
**Readex Pro** (UI, variable 160–700, Arabic + Latin, built for legibility) and **Alexandria** (display numbers and headings).
Both OFL, self-hosted woff2 (≤ 32 kB per subset), `font-display: swap`, unicode-range split so a page loads only what it uses.
Numbers are tabular. Money in Arabic: the number is isolated (LRI…PDI) so `1,250 ج.م` reads correctly inside RTL text.

## 5. Motion grammar (from the Animation studio, `coolman1984/Animation` QUALITY_PLAYBOOK §5)
- **Every change has a cause:** a scan pops the new line (320 ms spring), a page enters with a short rise + blur-to-sharp stagger
  (28 ms per child), a dialog pops with a soft spring, a sheet rises, a panel slides from the reading-start side.
- **Blur only while moving; exact rest state.** No looping decoration on working screens (the sign-in art may drift slowly).
- **Page swaps** use the View Transitions API when present; numbers count up (650 ms, ease-out expo) once.
- **Light 3D:** at most 3° tilt and a pointer spotlight on hero cards, only for fine pointers, never on lists.
- `prefers-reduced-motion` and the device preference "No motion" set every duration to ~0 and remove travel.

## 6. Components (in `packages/af-ui/css/base.css`)
Shell (rail, top bar with command search, banners, phone dock) · cards (flat / ink / volt / spot / tilt) · KPI · bars ·
area chart (no text inside a stretched SVG) · buttons (primary / volt / ghost / danger, busy state) · fields · segmented control ·
badges · tips · tables (sticky head, keyboard-scrollable wrapper) · empty state with one next action · skeletons of the final shape ·
dialog / side panel / bottom sheet / command palette (focus trap, Esc, return focus) · toasts (live region).

## 7. Non-negotiables that caught real bugs (Al-Store history)
1. Never use a state attribute (`data-theme`) as a JS hook: `$('[data-theme]')` matched `<html>` and replaced the page.
2. Attribute fragments inside the escaping template must be `raw()`: `'aria-current="page"'` was escaped into a broken attribute.
3. Flex/grid children that hold text need `min-width: 0`; the measured sweep found a top bar 248 px wider than a phone.
4. The CSP forbids inline styles: dynamic sizes go through `data-w` + `hydrate()` (CSSOM), never `style=""`.

## 8. How to adopt in a new product
Copy `packages/af-ui/{css,fonts,img}` (or serve it, as the Licence Studio does), re-brand tokens in `tokens.css` only, build pages
with the classes above, run `tests/test_frontend.py`-style static checks and the UI Lab. Changes to af-ui itself need two consumer
products checked before a version bump (UX_DESIGN_STANDARD "component contract").
