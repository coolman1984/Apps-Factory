# af-guide v0.1.0 • guides, learning paths, problems and simple Arabic gate

**Status:** `implemented` (unit-tested here; Hessa's full help passes). Standard:
[docs/HELP_AND_GUIDANCE_STANDARD.md](../../docs/HELP_AND_GUIDANCE_STANDARD.md). Controls `HELP-01`…`HELP-08`.

One file, standard library only, copied into each product (`python scripts/vendor_guide.py <product repo>` → `server/afguide.py`).

```bash
python af_guide.py check catalogue.json     # exit 1 on any error
python -m unittest discover -s tests
```

## Catalogue format
A product builds it from its real guide list and both dictionaries (Hessa: `tests/guide_catalogue.js`), adds the facts its
server reports and its menu pages, then asserts `afguide.errors(cat) == []` in a unit test (Hessa: `tests/test_guide_gate.py`).
```json
{
  "product": "al-store", "languages": ["ar", "en"],
  "facts": ["shopNamed", "shiftOpened", "saleMade"],
  "pages": ["settings", "cash", "pos"],
  "roles": ["owner", "cashier"],
  "setup_guides": ["setup"],
  "guides": [{"id": "openShift", "steps": 3, "pages": ["cash"],
              "texts": {"ar": ["title", "what you get", "step 1", "step 2", "step 3", "how you know it worked"], "en": ["..."]}}],
  "paths": [{"id": "owner", "admin": true, "roles": ["owner"], "texts": {"ar": ["name", "who it is for"], "en": ["..."]},
             "lessons": [{"guide": "setup", "fact": "shopNamed"}, {"guide": "openShift", "fact": "shiftOpened"}, {"guide": "sell"}]}],
  "situations": [{"id": "drawerShort", "guide": "openShift", "texts": {"ar": ["question", "answer"], "en": ["..."]}}],
  "other_ar": {"help.intro": "every other Arabic help text, only for the register check"}
}
```
* `facts`: what the server can say about the person asking, computed from the real rows (never a stored tick), e.g.
  `myShiftOpened`, `saleMade`. A lesson with a fact is done when the fact is true; a lesson without one is done when the person
  finished its guide.
* `roles`: the ready-made profiles (`af-access`); each must be on a path.
* `setup_guides`: the guides the administrator's path may start with.

## Rules (`check`)
Errors: `words-missing`, `register`, `guide-id`, `guide-short`, `page-without-guide`, `no-paths`, `no-admin-path`,
`path-duplicate`, `path-short`, `lesson-unknown-guide`, `lesson-unknown-fact`, `admin-path-order`, `role-without-path`,
`problem-unknown-guide`, `no-guides`.
Warnings: `path-unchecked` (fewer than half the lessons have a fact), `problem-without-guide`.

## Helpers
* `register(text)` → the words that break *simple formal Arabic* (العربية المبسطة): street Egyptian (`ده`, `مش`, `عشان`,
  `إزاي`, `زرار`, `اللي`…) or stiff office Arabic (`يُرجى`, `نظرًا`, `بموجب`, `حيث إن`…).
* `progress(lessons, facts, done_guides)` → `(index of "you are here", [done flags])`, the same rule the screen uses.
