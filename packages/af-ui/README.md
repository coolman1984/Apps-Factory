# af-ui 0.1 — the "Showroom" design system 🎨

Shared look and motion for factory products. Rules and rationale: [docs/DESIGN_SYSTEM.md](../../docs/DESIGN_SYSTEM.md) (UX-09).
Consumers: Al-Store (`coolman1984/Store`), Licence Studio (served from `/af-ui/`).

| Folder | Contents |
|---|---|
| `css/tokens.css` | Colours (day / night / high contrast), type scale, radii, shadows, motion durations — **re-brand here only** |
| `css/base.css` | Shell, cards, KPI, buttons, fields, tables, dialogs, sheets, palette, toasts, skeletons, RTL-safe layout |
| `fonts/` | Readex Pro + Alexandria variable woff2 (Arabic + Latin subsets) with their OFL licences |
| `img/icons.svg` | Icon sprite (`<use href="icons.svg#name">`), `icon.svg` app icon |
| `js/motion.js` | Springs, page enter stagger, View Transitions, count-up, light tilt/spotlight; honours reduced motion |

Plain CSS + ES modules, no build step, works under a strict CSP (no inline styles). Changing af-ui requires checking two
consumer products and running the UI Lab on both before bumping the version.
