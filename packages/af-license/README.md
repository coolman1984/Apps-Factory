# af-license v0.1.0 • signed licences and update manifests

**Status:** `implemented` (unit-tested here). Not yet `verified` inside a shipped product or field-accepted.
Controls: `BIZ-04`, `PROT-02`, `PROT-04`, `REL-02`. Spec: [docs/PROTECTION_UPDATES_AND_SUPPORT.md](../../docs/PROTECTION_UPDATES_AND_SUPPORT.md).

- Ed25519 through the vetted `cryptography` library; the algorithm is fixed in code, never read from the file.
- Purpose-separated keys: a `licence` key and an `update` key. The purpose is inside the signed bytes.
- Licence states: `active`, `grace`, `expired`, `not_yet_valid`, `invalid`. `expired`/`invalid` → the app switches to **read/export/backup**; it never deletes, hides or encrypts customer data.
- Optional device binding with `fingerprint(...)`, and `clock_rolled_back(...)` for a tampered clock.

```bash
pip install -r requirements.txt
python -m af_license keygen --purpose licence --out-dir ~/offline-keys      # once, on the vendor machine
python -m af_license issue --key ~/offline-keys/licence-<kid>.private.pem --purpose licence --claims claims.json --output customer.lic.json
python -m af_license verify customer.lic.json --public <kid>:<key> --purpose licence --product hessa-centre
python -m unittest discover -s tests
```
Private keys: offline, backed up twice, never in a repository, CI secret or customer build. Rotate by adding a new `kid` to the app's trusted list.
