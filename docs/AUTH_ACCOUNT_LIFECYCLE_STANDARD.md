> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Auth account lifecycle standard

**Status:** `implemented` as `packages/af-auth` (stdlib, vendored). Pattern proven in Trip Orders v1.1.5; product-agnostic names and keys.
Controls: `IAM-01`, `IAM-02`, `IAM-06`, `IAM-07` (with `packages/af-access` for permission catalogue and `admin_safety`).

## 1. Flows every product may adopt

| Flow | Behaviour | Server must |
|---|---|---|
| First setup | One administrator account when no users exist | Hash password (PBKDF2-SHA256), grant manage permission |
| Self sign-up | `pending` until approved; optional request code for the queue | No session until `approved`; cap pending count |
| Approve / refuse / suspend | Administrator decision with reason on refuse | Refuse only from `pending`; burn reset codes on refuse/suspend; keep ≥1 active manager |
| Login | Generic error on failure | Lock after N failures; **never** hard-lock sole active manager |
| Reset code | Administrator issues; user sets new password | Single-use; replicate `clear-reset-code` bound to hash; 3 wrong guesses burn |
| Forgot password UI | Explains owner-mediated reset | No e-mail secrets in the factory part |

## 2. Rules that are never broken (tested in af-auth)

1. **Suspended usernames** cannot register again; **rejected** users may re-request (journal clears stale reset hashes).
2. **Sole active `users.manage`** (or product `manage_permission`) is exempt from `locked_until` on login and reset-guess lockout.
3. **Approve / refuse / suspend** must not remove the last active account that can manage people.
4. **Local lockout** (`failed`, `locked_until`) is not replicated; replicated user saves must not clear it.
5. **Reset code burn** is replicated with `reset_hash` binding so rebuild/fold cannot revive an old code after a reissue.

## 3. How a product takes it

```bash
python3 scripts/vendor_auth.py <product repo>   # → server/afauth.py, js/vendor/af-auth.js
```

Use pure helpers inside an existing `server/auth.py`, or `AuthStore` in tests. Wire your journal to append `afauth.clear_reset_code_op(uid, hash)` when burning codes.

Optional UI: `afAuth.create(host, { paths: { login: '/api/auth/login', ... } })` with i18n keys `auth.*` and `autherr.*` (no product names in the package).

## 4. Evidence

`python3 -m unittest discover -s packages/af-auth/tests -v` and `node --test packages/af-auth/tests/core.test.mjs`.
