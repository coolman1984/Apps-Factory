# af-guide v0.1.0: role courses, coach, per-page help and the Arabic style lint

**Status:** `implemented`. Unit-tested and browser-tested here against the demo shop; no product uses it yet.

- **Standard:** [docs/GUIDED_ONBOARDING_STANDARD.md](../../docs/GUIDED_ONBOARDING_STANDARD.md).
- **Controls:** `HELP-04`, `HELP-07` … `HELP-12`.
- **Copy into a product:** `python scripts/vendor_guide.py <product repo>`. This writes `server/afguide.py`, `<js>/vendor/af-guide.js` and `<css>/af-guide.css`.

| File | What |
|---|---|
| `af_guide.py` | Checker, style lint, per-person progress (`apply`, `course`, `state`, `SQL`, `load`, `save`), outline, CLI. Standard library only. |
| `af-guide.js` / `af-guide.css` | Browser runtime: «الدليل» button and panel, coach, per-page "?", problem entries, language switch. No dependencies, `textContent` only, strict-CSP safe. |
| `style/ar-lexicon.json` | The «العربية الميسّرة» rules: sentence length, plus banned colloquial and technical words with replacements. |
| `testing/walk_guides.py` | Walks every guide in a real browser (Playwright) and reports steps that never advance (HELP-12). |
| `demo/` | Reference integration: a tiny shop page and the two server routes (`python demo/server.py`). |
| `examples/shop/` | A complete bilingual catalogue that passes `check --release`. |

```bash
python af_guide.py check examples/shop --ui examples/shop/ui-ar.json --ui examples/shop/ui-en.json \
       --access examples/shop/access.json --errors examples/shop/errors.json --release
python af_guide.py outline examples/shop ar        # the courses as Markdown, for the reading pass
python -m unittest discover -s tests -v            # browser tests need: pip install playwright && playwright install chromium
node --test tests/core.test.mjs
```

## Catalogue (`guide/catalogue.json`)
```json
{
  "product": "al-store", "format": 1,
  "languages": ["ar", "en"], "defaultLang": "ar", "uiLanguages": ["ar", "en"],
  "pages": ["home", "sell", "shift"], "unguided": ["help"],
  "states": ["shift.open", "sale.first"],
  "checklist": ["open-shift"],
  "targets": {"shift.open": {"page": "shift", "sel": "[data-guide=\"shift.open\"]"}},
  "guides": [{"id": "open-shift", "cat": "shift", "perm": "shift.open", "minutes": 2, "requires": [],
              "done": {"state": "shift.open"},
              "steps": [{"k": "go", "page": "shift"},
                        {"k": "click", "target": "shift.open", "until": {"target": "shift.cash"}},
                        {"k": "type", "target": "shift.cash", "until": {"filled": "shift.cash"}},
                        {"k": "done"}]}],
  "roles": [{"id": "cashier", "profiles": ["cashier"], "path": ["open-shift"]}],
  "problems": [{"id": "no-shift", "cat": "sell", "page": "shift", "guide": "open-shift",
                "errors": ["sale.no_shift"], "roles": ["cashier"]}]
}
```

Field rules:
- **Step kinds (`k`):** `go`, `click`, `type`, `choose`, `check`, `tip`, `warn`, `done`.
  - Action kinds need a `target`.
  - `go` needs a `page`.
  - The last step is `done`.
- **`until`:** exactly one of `route`, `target`, `gone`, `filled`, `dialog`, `event`. A `go` step defaults to `route`.
- **`perm`:** an af-access permission id, or `"*"`.

## Texts (`guide/<lang>.json`, flat keys)
- **Required:**
  - `role.<id>.title`, `role.<id>.intro`;
  - `guide.<id>.title`, `.why`, `.ok`, plus `.1` … `.n` (one per step);
  - `problem.<id>.see`, `.why`, `.do.1` ….
- **Optional:** `guide.<id>.mistake` and `problem.<id>.still`.

`[[ui.key]]` is replaced by the product's own UI label, in the UI language, inside «».

## Server routes (the demo shows them; about 15 lines in a product)
```python
def guide_state(me):                                   # GET /api/guide/state
    return afguide.state(CAT, me.role, afguide.load(db, me.id), live_states(), can=me.can)

def guide_progress(me, body):                          # POST /api/guide/progress {"update": {...}}
    try:
        rec = afguide.apply(afguide.load(db, me.id), body.get('update'), CAT)
    except ValueError as e:
        return 400, {'error': str(e)}
    afguide.save(db, me.id, rec)
    return afguide.state(CAT, me.role, rec, live_states(), can=me.can)
```

## Browser API
`AFGuide.init(opts)` returns a controller.

**Controller methods:**
- `open(page?)`, `close()`, `start(id, step?)`, `stop()`
- `signal(event)`
- `explain(code)`, `errorButton(code)`, `helpButton(page?)`
- `setStates(list)`, `setLang(lang)`, `routeChanged()`
- `course()`, `progress()`, and `ready` (a promise)

**Options:**
- Required: `catalogue`, `texts`, `role`.
- Optional:
  - `person`, `ui(key, lang)`, `uiLang`, `route()`, `go(page)`, `can(perm)`
  - `track(type, data)`: emits `guide.start/step/done/abandon/lang` and `problem.open` for af-telemetry
  - `onReport(ctx)`, `request(method, url, body)`, `api`, `mount`, `interval`
