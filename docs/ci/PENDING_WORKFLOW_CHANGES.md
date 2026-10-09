# CI steps still to be added to `.github/workflows/`

The automation token that pushed this branch has no `workflow` scope, so GitHub refuses any change under `.github/workflows/`. Until the owner adds these steps with one commit from an account that has that right, they run locally. The results are in each PR description.

## PR 1 (af-guide): add to `.github/workflows/factory-checks.yml`

**Step for the `validate` job** (insert before "Licence Studio tests"):
```yaml
      - name: Guide engine tests (af-guide; browser tests run in the guide-browser job)
        working-directory: packages/af-guide
        run: |
          python -m unittest discover -s tests -v
          node --check af-guide.js
          node --check demo/demo.js
          node --test tests/core.test.mjs
          python af_guide.py check examples/shop --ui examples/shop/ui-ar.json --ui examples/shop/ui-en.json --access examples/shop/access.json --errors examples/shop/errors.json --release
```

**New job** (append at the end of the file):
```yaml
  guide-browser:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      - name: Install Playwright for QA only
        run: |
          python -m pip install playwright==1.55.0
          python -m playwright install --with-deps chromium
      - name: af-guide in a real browser (walk every course, resume, language switch, CSP)
        working-directory: packages/af-guide
        run: python -m unittest tests.test_browser -v
```

## PR 2 (af-consent, af-telemetry): add to the `validate` job
```yaml
      - name: Consent and telemetry tests (af-consent, af-telemetry)
        run: |
          python -m unittest discover -s packages/af-consent/tests -v
          python -m unittest discover -s packages/af-telemetry/tests -v
          node --check packages/af-consent/af-consent.js
          node --check packages/af-telemetry/af-telemetry.js
          node --test packages/af-telemetry/tests/core.test.mjs
```
