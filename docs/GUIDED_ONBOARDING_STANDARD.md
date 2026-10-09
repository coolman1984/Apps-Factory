# Guided onboarding standard: role courses, coach, per-page help (af-guide)

- **Decision:** [ADR-0006](decisions/ADR-0006-guided-onboarding-and-arabic-register.md).
- **Controls:** `HELP-04`, `HELP-07` … `HELP-12`.
- **Package:** [`packages/af-guide`](../packages/af-guide/README.md).
- **Parent standard:** [HELP_AND_GUIDANCE_STANDARD.md](HELP_AND_GUIDANCE_STANDARD.md) (what help must contain and the language rules).

## 1. What the person sees
- **«الدليل» button** (bottom corner, every page) with a progress badge (`2/5`). It opens a side panel with:
  - **This page:** the guides that use this page, with Start / Do it again.
  - **Problems on this page:** what you see → why → what to do → if that did not work, with "Open the lesson" and "Go to the page".
  - **Your path:** the role's course, with a progress bar. Locked items wait for an earlier lesson, and items already done in the data are ticked.
  - **Report a problem:** hands the page and guide to the product's feedback form.
  - **Language switch** (when the product has more than one guide language).
- **"?" on every page header** (`guide.helpButton()`) and **F1** open the same panel for the current page.
- **The coach:** a docked card showing step *i of n*, a progress bar, the sentence, Back / Take me there / Next, and Finish on the last step.
  - The control it names is outlined.
  - The card moves on by itself when the step is done.
- **Resume:** after a reload, or on another PC, the coach offers «أكمل الدرس» at the saved step.
- **Error messages** with a known code get a «ماذا أفعل؟» button (`guide.errorButton(code)`) that opens the problem entry.

## 2. What the product adds
| Piece | Where | Notes |
|---|---|---|
| Engine copies | `python scripts/vendor_guide.py <repo>` | `server/afguide.py`, `<js>/vendor/af-guide.js`, `<css>/af-guide.css` |
| Guide data | `guide/catalogue.json`, `guide/ar.json`, `guide/en.json` | format in the package README |
| Stable hooks | `data-guide="<target id>"` on every control a step names | never select by text or position |
| Two routes | `GET /api/guide/state`, `POST /api/guide/progress` | `afguide.state(...)`, `afguide.apply(...)`, `afguide.load/save` on the person's id; 400 on `ValueError` |
| Table | `afguide.SQL` (`guide_progress`) | forward-only migration |
| Live states | names in `catalogue.states` that are already true (shift open, first sale…) | computed by the server, like Hessa's overview checklist |
| Signals | `guide.signal('<event>')` after the server confirms an action | drives `until: {"event": …}` steps |
| Error codes | a list of every error code the server returns | `--errors` for HELP-09 |
| Tests | `afguide.errors(cat, texts, ui=…, access=auth.catalogue(), error_codes=…)` in unit tests; `walk_guides.walk(page, cat)` in browser tests | HELP-07…12 |

Wiring (about 10 lines):
```js
const guide = AFGuide.init({catalogue, texts: {ar, en}, role: me.role, person: me.id,
  ui: (key, lang) => t(key, lang), uiLang: () => currentLang, route: () => currentPage, go: navigate,
  can: perm => me.perms.includes(perm), track: (type, data) => telemetry.track(type, data), onReport: openFeedback});
window.__afguide = guide;                 // used by walk_guides.py
header.append(guide.helpButton());
onRouteChange(() => guide.routeChanged());
```

## 3. Authoring rules
1. **One role, one path.** Order guides by the first day of that role: open the shift before the first sale.
   - A guide that `requires` another must come after it in every path that contains both (`path-order`).
2. **Short guides:** 1–15 minutes and one job each. Split longer ones.
3. **One action per step:** `go` (open a page), `click`, `type`, `choose`, `check`, `tip`, `warn`. The last step is always `done`.
4. **Every action step auto-advances** with `until`, or the checker warns (`no-auto-advance`). Pick the one that fits:

   | What finishes the step | `until` |
   |---|---|
   | A page opens | `route` |
   | A control appears | `target` |
   | A form closes | `gone` |
   | A field has a value | `filled` |
   | A dialog is open | `dialog` |
   | The server confirmed the action | `event` |
5. **Button names** are `[[ui.key]]`: the guide shows the real label in «».
6. **Problems:** every error the server can return links to one problem entry (`error-unexplained`).
   - Every problem links to a page or a guide.
   - Every page has at least one guide or problem, so "?" is never empty (`page-unguided`; list real exceptions in `unguided`).
7. **Wording:** «العربية الميسّرة» (HELP-04). Run `python scripts/factory.py guide guide/ --release` before a release.

## 4. Checks (all automatic unless marked)
| Control | Check |
|---|---|
| HELP-07 | `role-without-path`, `path-order`, `role-perm`, `unknown-perm`, `unknown-guide`, `requires-cycle`, `coverage-checklist`; browser test: progress follows the person to a second browser |
| HELP-08 | `until`, `no-auto-advance`; browser test: guides finish with no Next on action steps; Resume after reload |
| HELP-09 | `error-unexplained`, `problem-without-link`, `problem-shape`, `page-unguided` |
| HELP-10 | `text-missing` for every guide language, `ui-key-missing`; browser test: language switch flips the coach direction and is saved |
| HELP-11 | `sentence-long`, `banned-word`, `eastern-digits`, `quoted-ui`, `one-action` (errors with `--release`) |
| HELP-12 | `testing/walk_guides.py` returns no failures for every guide |
| HELP-04 | lint clean **and** a reading pass by a non-developer, named in the release evidence (manual) |

## 5. Rollout per product
Teachers (Hessa) → Al-Store → Trip Orders → BAMS (bilingual guides on an English UI). This happens one product per pull request, after this factory change is merged. Nothing in this standard changes a product by itself.
