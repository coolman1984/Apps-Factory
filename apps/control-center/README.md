# Vendor Control Center (برج المراقبة) v0.1.0

**Status:** `implemented` — 15 API/UI tests pass. **Not deployed, not field-verified.** Manifest: [examples/vendor-control-center.json](../../examples/vendor-control-center.json) • Spec: [PROTECTION_UPDATES_AND_SUPPORT.md](../../docs/PROTECTION_UPDATES_AND_SUPPORT.md) §3–5.

## What works now
- Customer and install registry; one-time install tokens (stored hashed); deactivate an install.
- Heartbeats with a fixed field list (unknown fields refused) and Arabic health reasons: stale, old backup, licence, errors, unsynced changes, low disk.
- Help tickets from products, redacted on the server (Egyptian phones, national IDs, e-mails, secrets, keys) and marked as untrusted text.
- Customer-initiated support grants (max 120 minutes, named approver, 9-digit code); the customer can end them; ending cancels pending repairs.
- Repairs: allowlist of 4 non-destructive actions, only under a live grant with `repair` scope; the AI agent token can only *request*; the owner approves.
- Licence desk: claims template per install → sign **offline** with `af-license` → upload; the server verifies the signature before storing; expiring list.
- Audit of every write; UUIDv7 IDs; forward-only migrations; Arabic RTL dashboard (customer text rendered as text only).

## Not yet
MCP gateway process for the AI agent (the API is its backend), product-side agent library, GlitchTip/RustDesk/Uptime Kuma deployment, owner MFA, HTTPS deployment, backups of this server.

## Run
```bash
pip install -r requirements.txt
export PYTHONPATH=../../packages/af-license CC_DB=data/control-center.db
export CC_LICENCE_PUBLIC_KEYS="<kid>:<public key>"        # from: python -m af_license keygen
python -m control_center token --kind owner --name "Owner"  # printed once
python -m control_center token --kind agent --name "AI agent"
python -m control_center serve --host 127.0.0.1 --port 8765 # put HTTPS (reverse proxy) in front before going online
python -m unittest discover -s tests -v
```
