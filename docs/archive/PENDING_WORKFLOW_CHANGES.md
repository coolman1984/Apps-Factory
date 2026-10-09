# CI steps still to be added to `.github/workflows/`

> **Status (2026-10-09): applied.** Every step below is now in `.github/workflows/factory-checks.yml` (the `validate` job
> and the new `guide-browser` job), added with an account that has the `workflow` scope in the PR
> `ci/align-workflows-20261009`. The relay test runs on Node `^22.13.0`. The vendored-copy drift tests, which skip when the
> product repositories are not next to this one, now run against real checkouts in `.github/workflows/vendored-drift.yml`.
> Nothing below is pending any more; this file is kept as the record of what was added and why.

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

## PR 3 (Control Center telemetry, relay): add to the `validate` job
```yaml
      - uses: actions/setup-node@v4
        with:
          node-version: '22'
      - name: Telemetry relay tests (Cloudflare Worker + D1 shim)
        run: node --experimental-sqlite --test templates/telemetry-relay/test/relay.test.mjs
```

The Control Center tests (`apps/control-center/tests`, including `test_telemetry.py`) already run in the existing job.
They need `packages/af-telemetry` and `packages/af-consent`, which are found by path inside this repo.
