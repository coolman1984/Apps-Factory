# af-access v0.1.0 • people, profiles, pages and permissions gate

**Status:** `implemented` (unit-tested here; reference catalogue from BAMS passes). Standard:
[docs/ACCESS_AND_ADMINISTRATION_STANDARD.md](../../docs/ACCESS_AND_ADMINISTRATION_STANDARD.md). Controls `IAM-08`…`IAM-12`.

One file, standard library only, copied into each product (`python scripts/vendor_access.py <product repo>` → `server/afaccess.py`).

```bash
python af_access.py check examples/bams-catalogue.json     # exit 1 on any error
python af_access.py matrix examples/bams-catalogue.json    # who can do what, as a Markdown table
python -m unittest discover -s tests
```

## Catalogue format
```json
{
  "product": "al-store", "languages": ["en", "ar"], "manage": "users.manage",
  "groups": [
    {"id": "sell", "labels": {"en": "Selling", "ar": "البيع"}, "permissions": [
      {"id": "sales.view", "kind": "page", "labels": {"en": "Sales page", "ar": "صفحة المبيعات"}},
      {"id": "sales.return", "requires": ["sales.view"], "labels": {"en": "Take returns", "ar": "استلام المرتجعات"}}]},
    {"id": "admin", "admin": true, "labels": {"en": "Administrator rights", "ar": "صلاحيات المدير"}, "permissions": [
      {"id": "users.manage", "kind": "admin", "labels": {"en": "Manage people", "ar": "إدارة الأشخاص"}}]}
  ],
  "pages": {"home": "*", "sales": ["sales.view"]},
  "profiles": [{"id": "owner", "locked": true, "labels": {"en": "Owner", "ar": "المالك"}, "perms": ["..."]}]
}
```
`kind`: `page` | `action` (default) | `field` | `admin`. `label` (one string) is accepted for single-language products.
`pages`: route → permissions of which **any one** opens it, or `"*"` for everybody signed in.

## Rules (`check`)
Errors: `perm-id`, `perm-duplicate`, `perm-kind`, `label-missing`, `requires-unknown`, `requires-self`, `admin-group`,
`manage-missing`, `manage-not-admin`, `page-unguarded`, `page-unknown-perm`, `locked-profile`, `profile-duplicate`,
`profile-reserved-name`, `profile-unknown-perm`, `profile-missing-requires`, `no-work-profile`.
Warnings: `page-perm-unused`, `perm-unused`.

## Runtime helpers
`admin_safety(before, after, actor_id, admin_perms)` → `last-manager` / `self-lockout` / `link-admin`;
`effective(base, extra, denied)`; `perm_diff(before, after)` for the security log; `matching_profile(perms, profiles)`
to show *Custom*; `matrix(cat, lang)`.
