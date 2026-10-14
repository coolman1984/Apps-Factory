# af-license v0.3.2 • signed licences and update manifests

**Status:** `implemented` (unit-tested here). Not yet `verified` inside a shipped product or field-accepted.
Controls: `BIZ-04`, `PROT-02`, `PROT-04`, `REL-02`. Spec: [docs/PROTECTION_UPDATES_AND_SUPPORT.md](../../docs/PROTECTION_UPDATES_AND_SUPPORT.md).

- Ed25519 through the vetted `cryptography` library; the algorithm is fixed in code, never read from the file.
- Purpose-separated keys: a `licence` key and an `update` key. The purpose is inside the signed bytes.
- Licence states: `active`, `grace`, `expired`, `not_yet_valid`, `invalid`. `expired`/`invalid` → the app switches to **read/export/backup**; it never deletes, hides or encrypts customer data.
- Optional device binding with `fingerprint(...)`, and `clock_rolled_back(...)` for a tampered clock.
- Source-only trial features (`af_license.runtime.dev_features_allowed`, 0.3.2): admin/123 and similar stay on only when the config flag is true **and** `distributed_runtime` is false. A shipped binary ignores `dev_login: true`. Import runtime helpers as `af_license.runtime` (they are not re-exported from `af_license`).

## First config on a sold copy

When a product writes the first `config.json` on a distributed build, force the source-only flag off. `first_run_source_flag(True)` returns false when `distributed_runtime` is true, and the caller's default on a plain `python` run. Editing the file later must still not turn the feature on: the sign-in path calls `dev_features_allowed`, not the stored flag alone.

```python
from af_license.runtime import dev_features_allowed, first_run_source_flag

cfg['dev_login'] = first_run_source_flag(True)   # false inside a shipped binary
if dev_features_allowed(cfg.get('dev_login')):
    ...  # trial sign-in, source runs only
```

Tests pass `compiled=True` or `frozen=True`. They do not need a Nuitka build. This helper does not detect Nuitka markers itself; that stays in `distributed_runtime`.

```bash
pip install -r requirements.txt
python -m af_license keygen --purpose licence --out-dir ~/offline-keys      # once, on the vendor machine
python -m af_license issue --key ~/offline-keys/licence-<kid>.private.pem --purpose licence --claims claims.json --output customer.lic.json
python -m af_license verify customer.lic.json --public <kid>:<key> --purpose licence --product hessa-centre
python -m unittest discover -s tests
```
Private keys: offline, backed up twice, never in a repository, CI secret or customer build. Rotate by adding a new `kid` to the app's trusted list.
