# af-auth v0.1.0 • sign-up approval, reset codes, lockout, admin safety

**Status:** `implemented` (unit-tested; ported from Trip Orders v1.1.5 auth rules). Standard:
[docs/AUTH_ACCOUNT_LIFECYCLE_STANDARD.md](../../docs/AUTH_ACCOUNT_LIFECYCLE_STANDARD.md). Controls `IAM-01`, `IAM-02`, `IAM-06`, `IAM-07`.

One file, standard library only, copied into each product (`python scripts/vendor_auth.py <product repo>` → `server/afauth.py`).

```bash
python -m unittest discover -s tests
python examples/minimal/consumer.py
```

## What it covers

- Self-service **sign-up** → `pending` until an administrator **approves**, **refuses** (reason required) or **suspends**.
- **Forgot password** is owner-mediated: administrators issue a single-use **reset code**; wrong guesses burn the code after three tries and replicate `clear-reset-code` so rebuilds cannot revive it.
- **Failed-login lockout** is local (never replicated); the sole active `users.manage` account is never hard-locked (login or reset guesses).
- **Last-manager** guard on approve/refuse/suspend (and via `af_access.admin_safety` for permission edits).
- **Suspended** usernames cannot register again; **rejected** users may re-request (clears stale reset hashes in the journal).

Products still own sessions, HTTP routes, permission catalogues, multi-PC journals and UI copy. Optional JS helpers: `af-auth.js` (generic sign-in / sign-up / reset forms).

## Integration sketch

```python
import afauth

store = afauth.AuthStore(data_dir + '/auth.db', {'manage_permission': 'users.manage'})
# Or call the pure helpers from your existing Auth class:
sole = afauth.sole_admin_id(rows, manage='users.manage')
failed, locked = afauth.login_failure_update(row['failed'], sole, max_failed, lock_minutes)
```

Wire replicated writes through your journal; append `afauth.clear_reset_code_op(uid, reset_hash)` whenever a code is burned.

On login or reset `AuthError`, sleep `afauth.http_auth_delay_seconds(store, username)` (or `0.6 + store.sole_admin_login_delay(username)`) so the sole manager account is throttled without hard lockout.
