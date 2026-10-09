# ADR-0006 • Guided onboarding engine (af-guide) and the «العربية الميسّرة» register

- **Date:** 2026-10-09
- **Status:** ACCEPTED by owner (approval of the parity plan, 2026-10-09).

## Context
Each product grew its own help:
- Hessa has a coach plus 31 guides.
- Al-Store has numbered steps.
- Trip Orders and BAMS have a few Q&A.

None of them follows a person through a first-day path, keeps progress on the server, notices when a step is done, or proves in a browser that every guide still finds its buttons. HELP-04 asked for "polished Egyptian" Arabic, while the owner wants simple formal Arabic.

## Decisions
1. **One shared engine, `packages/af-guide`.** It is vendored like `af-access` and holds:
   - a checker plus style lint (`af_guide.py`, standard library only);
   - a browser runtime (`af-guide.js` + `af-guide.css`, no dependencies, `textContent` only, works under a strict CSP);
   - a browser walker (`testing/walk_guides.py`).

   Products describe guides as data: `guide/catalogue.json` + `guide/<lang>.json`.
2. **Role courses.** Every role has an ordered path of short guides (1–15 minutes). A guide is done when the person finishes it, **or** when the data already shows it is done (`done.state`, like Hessa's overview checklist).
3. **Progress per person, on the server.**
   - Routes: `GET /api/guide/state` and `POST /api/guide/progress`.
   - Table: `guide_progress`.
   - `localStorage` is only a cache, so a person continues on any PC.
4. **The coach moves on by itself.**
   - Conditions: `until`: `route`, `target`, `gone`, `filled`, `dialog`, or an `event` the product signals after the server confirms an action.
   - An unfinished guide offers **Resume** after reload.
5. **Guide language is separate from the app language.**
   - Each person can switch the guide language.
   - Button names keep the screen's language.
   - The coach direction follows the guide language (BAMS: English UI, Arabic and English guides).
6. **Errors link to problems.** Every server error code maps to a problem entry (HELP-09). `AFGuide.explain(code)` opens it.
7. **Register: «العربية الميسّرة»** replaces "polished Egyptian" (HELP-04):
   - Modern Standard Arabic order without case endings, plus everyday words;
   - one action per step;
   - digits 0-9;
   - no colloquial function words or technical words.

   The lint enforces what a machine can check, and lint warnings block a release (HELP-11). A reading pass by a non-developer stays mandatory.
8. **Controls:** HELP-07 courses + server progress, HELP-08 auto-advance + resume, HELP-09 error links, HELP-10 language switch, HELP-11 style lint, HELP-12 browser walk.

## Consequences
- Products move their existing help into `guide/` files one role at a time. Hessa's coach is the reference behaviour, and its step kinds are kept (`go/click/type/choose/check/tip/warn/done`).
- Existing Egyptian help text must be rewritten to the new register before a product claims HELP-04/HELP-11.
- Product adoption is a separate change per product repository. This ADR does not change any product.
