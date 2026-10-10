# Playbook

Day-to-day maintenance of the factory. Use `python3` (the `python` command may be missing). Run everything from the repository root.

## 1. Run the tests
These are the commands CI runs (`.github/workflows/factory-checks.yml`). Run the ones for the part you touched; run all of them before a release.

```bash
python3 -m py_compile scripts/factory.py
python3 scripts/factory.py doctor                      # catalogue + schema consistency
for f in examples/hessa-product.json examples/trip-orders-product.json examples/multi-branch-reference.json \
         examples/vendor-control-center.json examples/al-store-product.json; do python3 scripts/factory.py check $f; done
python3 -m unittest discover -s tests -v               # factory CLI + docs (tests/test_docs.py)

(cd apps/control-center && pip install -r requirements.txt && PYTHONPATH=../../packages/af-license python3 -m unittest discover -s tests -v)
(cd packages/af-license && pip install -r requirements.txt && python3 -m unittest discover -s tests -v)
(cd packages/af-access && python3 -m unittest discover -s tests -v)
(cd packages/af-guide && python3 -m unittest discover -s tests -v && node --check af-guide.js && node --test tests/core.test.mjs \
   && python3 af_guide.py check examples/shop --ui examples/shop/ui-ar.json --ui examples/shop/ui-en.json \
        --access examples/shop/access.json --errors examples/shop/errors.json --release)
python3 -m unittest discover -s packages/af-consent/tests -v
python3 -m unittest discover -s packages/af-telemetry/tests -v
node --test packages/af-telemetry/tests/core.test.mjs
node --experimental-sqlite --test templates/telemetry-relay/test/relay.test.mjs templates/telemetry-relay/test/licence.test.mjs templates/telemetry-relay/test/telegram.test.mjs      # Node 22.13+
(cd apps/licence-studio && pip install -r requirements.txt && PYTHONPATH=../../packages/af-license python3 -m unittest discover -s tests -v)
python3 -m json.tool factory/ui-budgets.json > /dev/null
python3 -m unittest discover -s design-factory/tests -v                             # design-factory.yml
```
The browser tests (`packages/af-guide`: `python3 -m unittest tests.test_browser -v`) need Playwright and Chromium and run in the `guide-browser` job. The sample manifests `hessa-product`, `multi-branch-reference`, `vendor-control-center` and `al-store-product` must keep **failing** `check --release` (CI asserts it): that proves the gate still blocks.
Report exactly what you ran, and what you skipped.

### Windows commercial release rule
- The factory `windows-contract` job checks factory manifest/standard tests on `windows-2025`. It does **not** build each customer product.
- Every Windows product must configure a mandatory PR **and** main-push Windows job that builds the exact executable/installer, installs, launches, restarts, checks persistence and uninstall data retention, and links the green run + artifact hash in the release notes. A green Linux test is not enough.
- Set the Windows job as a **required GitHub branch protection check** through a repository administrator; CI alone cannot enforce a required check. Never merge pending/failed builds. The separate clean-PC backup restore and customer trial are still required.
- For new commercial plans use optional manifest `commercial_plan: solo | connected | mobile_ops | cloud_business`, see [commercial tiers](docs/SMB_COMMERCIAL_TIERS.md). On `--release` it requires extra backup/sync/mobile evidence.

### Company portfolio work: start at the decision map
Before tasking an agent with a new Store/Pixel Plus feature, read [the unified execution roadmap](docs/PIXEL_PLUS_EXECUTION_ROADMAP_2026.md), [Telegram-approved activation](docs/TELEGRAM_APPROVED_ACTIVATION.md), [Rafaa proposal](docs/RAFAA_GROWTH_DECISION_ADDON_PROPOSAL.md), and [Pixel Plus–Sanad handoff](docs/PIXEL_PLUS_SANAD_PARTNER_OPERATING_MODEL.md) as applicable. Do not expand a paid pilot into an unapproved cloud platform.

- Track every strategic idea as `planned` until *code exists*, `implemented` until tested, `verified` until field-tested, and `field_accepted` only when real client acceptance is documented.
- Never claim outgoing Telegram owner alerts mean the inbound 14-day approval flow already works. Make sign/approve/delivery separate permissions; private signing key never leaves the owner's encrypted local Studio.
- For UI/code audit use an **independent reviewer**, record selector → click → JS handler → API → server permission → DB effect → customer-visible state, with actual screenshots from real browser and negative tests, not only code inspection.
- Site/demo/Sanad/referral implementations stay in separate narrow PRs with synthetic test data, explicit cross-company customer consent and no externally published promises until approved.
- For every Windows product preserve PR and main-push installer workflow and restore-on-clean-PC field proof; no test skip used as a fake green signal.

## 2. Check that vendored copies have not drifted
Products hold byte-identical copies of af-access, af-license codes, af-guide, af-consent and af-telemetry. The drift tests look for the product repositories next to this one and **skip** when they are absent, so a green local run proves nothing without them. CI runs them for real against the public product repos (`.github/workflows/vendored-drift.yml`, on every factory change and daily).
To run locally, clone the products into one folder and set `AF_STORE_REPO`, `AF_TEACHERS_REPO`, `AF_YOUSEF_TRANSPORTATION_REPO`, `AF_MR_AYMAN_HR_REPO`, then:
```bash
python3 -m unittest discover -s packages/af-license/tests -k test_vendored_copy_in_known_products_matches -v
for p in af-access af-guide af-consent af-telemetry; do python3 -m unittest discover -s packages/$p/tests -k VendoredCopies -v; done
```
A stale copy is fixed in the product, not here: bump the part's version if the code changed, run `python3 scripts/vendor_<name>.py <product dir>`, run the product's tests, open a PR in the product repo.

## 3. Release a factory version
1. Make the change on a branch; run section 1.
2. Bump the **Version** line in `README.md` (format: `**Version:** X.Y.Z — one-line summary; … see [CHANGELOG](CHANGELOG.md)`).
3. Add the entry at the top of `CHANGELOG.md` (`## X.Y.Z (date)`, what changed, what did not).
4. If `factory/controls.json` changed, bump its `catalog_version` (and `updated`). The catalogue has its own version, separate from the factory version.
5. If a part changed, bump the part's own version (`__version__` in its code) and update `PARTS.md`.
6. Open a PR; wait for CI; small safe merge. Never force-push.

## 4. Add or update a control
1. Edit `factory/controls.json`. A control needs `id`, `slug`, `category`, `profiles`, `tier` (`core` or `reference`), `requirement`, `acceptance_evidence`, `required_if_applies`, `implementation_status`.
2. New controls start as **reference**. Make one `core` only with an owner decision recorded in `DECISIONS.md`, and update the table in `RULES.md`.
3. Merging or dropping a control: list the old id in the survivor's `merged_from`, or add it to `retired` with a reason, so `python3 scripts/factory.py controls <OLD-ID>` still answers.
4. Controls state practical outcomes only; no wording about outside authorities (a test checks).
5. Bump `catalog_version`; run `python3 scripts/factory.py doctor` and the unit tests.

## 5. Add a product
1. Use the skill `new-product` or run `python3 scripts/factory.py new --id my-app --name "…" --mode lan --market EG --output my-app.json` (more flags: `--tier`, `--sites`, `--clients`, `--multi-owner`).
2. Fill in buyer, problem, the one core journey and acceptance scenarios; copy `templates/PRODUCT_BRIEF.md` and `templates/MARKET_RESEARCH.md`.
3. `python3 scripts/factory.py check my-app.json`; add the file to `examples/` when it is a real product.
4. Vendor the parts it needs (`PARTS.md`), then add the product's repo to the drift workflow when it vendors anything.
5. Release evidence per candidate: `templates/RELEASE_EVIDENCE.md`; the gate is `check --release`.

## 6. Alerts and the Control Center basics
- Run: `cd apps/control-center && pip install -r requirements.txt`, then `python3 -m control_center token --kind owner --name "Owner"` (printed once), then `python3 -m control_center serve --host 127.0.0.1 --port 8765`. Put HTTPS in front before going online. Full options: `apps/control-center/README.md`.
- Every alert goes to **all enabled channels at once** (no order, no fallback); one failing channel never blocks the others. Telegram is the core owner channel and turns on by itself when `TELEGRAM_BOT_TOKEN` and `TELEGRAM_OWNER_CHAT_ID` are set. Secrets come from environment variables only, never from settings or the repository.
- Alert text never carries the customer's own words: channels get the ticket number, category, page and a dashboard link.
- New PCs appear under «أجهزة جديدة مستنية موافقتك»: approve (choose customer and tier) or discard.
- Time-based rules and clean-up can be run once by hand: `python3 -m control_center alerts`, `python3 -m control_center retention`, `python3 -m control_center pull-relay`.
- Licence codes: use `apps/licence-studio` (`python3 -m licence_studio serve`). The private key never goes into a repository, CI or a product.
- Customer problem to fix to delivery: design in `docs/CUSTOMER_PATCH_PIPELINE.md` (not built yet).
