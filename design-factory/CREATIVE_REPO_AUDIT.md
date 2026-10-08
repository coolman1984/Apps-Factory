# Local and world creative repository review • 2026-10-08

Inspected owner repositories from the latest-repo survey, plus targeted owner repositories where product-specific creative functionality is concentrated. Reviewed source docs and current default branches. This is **source/document inspection**, NOT a runtime audit of every repository.

| Owner repository | Existing useful work | Reuse recommendation | Risk/check |
|---|---|---|---|
| [Animation](https://github.com/coolman1984/Animation) | Code-driven film studio, deterministic `renderAt(t)` / `seek`, audio cue grid, reverse-engineering reference lab, native Studio Engine JSON spec and quality gates | **Primary internal film engine**; use adapters to scene briefs and deliverable profiles, do not rewrite renderer | Project status includes browser/final-render checks that are not universally verified; re-run on exact commit |
| [The-Slide-Show](https://github.com/coolman1984/The-Slide-Show) | Slide Forge: JSON decks, 11 slide types, 10 themes, 7 transitions, layered offline self-contained HTML; agent skills and validators | Primary slide/presentation motion engine with theme token adapter | Its default branch is an agent branch; preserve source history and separate engine from specific decks |
| [promo-video-generator](https://github.com/coolman1984/promo-video-generator) | Source docs describe browser frame renderer + FFmpeg, deterministic timeline and synthetic soundtrack; appears derived from visser23 upstream | Alternative repeatable MP4 pathway and film timing reference | Validate origin/attribution, dependencies and exact owner changes before shipping or selling source |
| [3D-Modeling](https://github.com/coolman1984/3D-Modeling) | Real domain 3D editor/canvas, Space Planner design contract and templates | Reuse canvas integration patterns, not as generic animation framework | Feature branch integration risk; preserve live domain UX |
| [Personal-Web](https://github.com/coolman1984/Personal-Web) | Next.js / frontend source with portfolio presentation | Marketing frontend testbed for layer/hero recipes after explicit baseline capture | Avoid global CSS reset or changing branding unreviewed |
| [FileLogger-Landing-Page](https://github.com/coolman1984/FileLogger-Landing-Page) | Existing HTML/CSS marketing site and visual assets | Candidate test of vanilla original CSS animation preset | Assets/fonts require provenance; preserve current marketing copy |
| [Company-of-Media](https://github.com/coolman1984/Company-of-Media) | Media content business workflows and assets | Asset provenance and brand story inputs, not a shared animation runtime | Avoid importing social account tokens/real data |
| [presentation](https://github.com/coolman1984/presentation) | Existing executive deck/theme artifacts | Visual consistency references for Slide Forge | Verify branding rights and presentation-specific licensed assets |

## External sources
See machine-readable `creative-sources.lock.json` for 17 exact SHAs, categories, per-source policies and licensing exceptions. Not every cloned source must be installed in customer products.

**Safest default combination:** original factory CSS + native browser APIs + selected Lucide icons. Add Motion when complexity warrants it. Three/Pixi/Rive/Lottie/film tools are advanced optional lanes, not "always-on" dependencies.

**High-risk licences:** Theatre studio AGPL (core Apache), Remotion restrictions for company use and resale, Iconify icon pack licences separate from framework, Rive editor/assets separate from MIT runtimes, customer-purchased photos/fonts/motion packs. Consult competent counsel if packaging source into a paid product.
