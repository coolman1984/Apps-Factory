> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Access and administration standard: people, profiles, pages and permissions

**Status:** `implemented` as a gate (`packages/af-access`, tested). Source of the pattern: **BAMS** (`coolman1984/Mr.Ayman-HR`,
`server/auth.py` + `GUIDE_Users_Permissions.md`), proven in daily use since 2.0 and copied into Hessa and Trip Orders.
Controls: `IAM-03`, `IAM-04`, `IAM-07` and the new `IAM-08`…`IAM-12`.

The owner of a small business must be able to say, without help: *"this person sees these pages and may do these things,
only for these branches/teachers/areas"*. And the program must never let the owner lock themself out while doing it.

## 1. The model (what every product has)

| Piece | What it is | BAMS reference |
|---|---|---|
| **Permission catalogue** | A fixed, grouped list of permission ids (`area.verb`) with a plain-words label in every language. The order is the order on screen. | `PERMISSIONS` |
| **Page permissions** | One permission per page (`*.view`) decides whether the page is in the menu, the command palette, the dock and whether its data comes back from the server. | group *Pages – what the person can open*, `PAGES` |
| **Action permissions** | One per action that changes data (`create`, `edit`, `delete`, `approve`, `void`…). An action can *require* its page. | groups *Break Areas*, *Inventory*… |
| **Field permissions** | Sensitive columns that are removed **by the server** (cost, profit, phone numbers, national ID). | `maintenance.cost`, Hessa `contacts.view`, Store `cost.view` |
| **Administrator group** | The rights that control the system itself: manage people/profiles/permissions, activity and security logs, restore a backup, replace all data, internet gateway. Shown apart (orange), never ticked by *Select all*, never carried by a personal link. | `ADMIN_GROUP`, `ADMIN_PERMS` |
| **Profiles** | Named sets of ticks (*Cashier*, *Front desk*, *Viewer*). Ready-made ones ship with the product; the administrator can rename, change, delete them and make new ones. Choosing a profile ticks the boxes; changing one tick makes the person *Custom*. | `BUILTIN_PROFILES`, `save_profile`, `delete_profile` |
| **Locked profile** | *Administrator* (or *Owner*) always has every permission and cannot be changed or deleted. | `LOCKED_PROFILE` |
| **Data scope** | Optional limit to some records: branches, break areas, a teacher's groups. Empty = all. Checked on every read and write. | `areas`, Hessa/Trip Orders `scopes` |
| **Limits** | Numbers that belong to a person, not a tick: maximum discount %, cash limit. | Store `max_discount_pct` |

## 2. Rules that are never broken (server-side, tested)

1. **Deny by default, checked on the server for every request** — hiding a button is a convenience only
   ([OWASP ASVS 5.0 V8.3.1](https://github.com/OWASP/ASVS/blob/master/5.0/en/0x17-V8-Authorization.md); OWASP Authorization Cheat Sheet).
   Exports, prints, batch saves and reports are checked too (ASVS V8.2.1–V8.2.3: function, data and field level).
2. **There is always a way to manage the system**: a change that would leave no active person with `users.manage` is
   refused (`af_access.admin_safety` → `last-manager`). A person cannot remove their own `users.manage` or switch
   themself off (`self-lockout`). BAMS: `_admins`, Store: `auth.err.lastOwner`.
3. **A personal link never carries an administrator right** (`link-admin`); administrators sign in with a password.
4. **Changes take effect immediately** (ASVS V8.3.2): permissions are read per request; switching someone off or
   resetting a password ends their sessions.
5. **Every change to a person, a profile or a tick is in the security log** with *who, when, what was added, what
   was removed* (`af_access.perm_diff`). Logs never contain passwords or tokens.
6. **Two administrators editing the same person**: the second save is refused with "changed by X at T – open it again"
   (BAMS `ver`), never silently overwritten.
7. **Deleting a profile never takes rights away silently**: its people keep their ticks and show as *Custom*.
   Changing a profile asks *"also update the N people who have it?"*.
8. **Least privilege, but easy to grant**: a new person starts from a profile, not from *everything*. It is easier to
   add a tick later than to take one away (OWASP Authorization Cheat Sheet). Ready-made profiles follow the real jobs of
   the market (Square *permission sets*, Shopify *POS roles*: named, editable, assigned per person; the default role
   cannot be deleted).
9. **Separation of duty where money is involved**: the person who takes money is not the only one who can reverse it;
   a manager approval (password typed on the cashier's screen) is recorded with both names (Store `approve`).
   This is the static/dynamic SoD idea of the NIST RBAC standard (ANSI/INCITS 359) in its simplest useful form.

## 3. The administrator's screens (UX contract)

| Screen | Must have | Must not |
|---|---|---|
| People list | Name, profile (or *Custom*), status badges (*off*, *locked*, *online*), one **Add person** button | Technical ids, permission codes |
| Person window | Name → profile picker → ticks grouped as in the catalogue, group tick = whole group, *Select all* (without the admin group), *Clear all*; limits and scope under **More options** | A free-text role, a hidden admin right |
| Profiles | List with *people who have it*; **New profile**, **Edit** (with "update the people who have it"), **Delete** (people keep ticks); the locked one shows a lock | Deleting or editing the locked profile |
| Who can do what | The matrix *profiles × permissions* (`af_access.matrix`), printable | — |
| Errors | One plain sentence that says what to do: *"At least one active person must keep the right to manage people."* | Codes, stack traces |

Everything in both languages of the product (Arabic RTL first for Egyptian shops), keyboard reachable, works at 360 px.

## 4. How a product proves it (the gate)

Each product exports its catalogue as data (a function next to its permission list) and runs the factory gate in its
own unit tests — the same idea as `design-factory/qa/token_gate.py`:

```python
import afaccess                        # vendored with: python scripts/vendor_access.py <product repo>
cat = auth.catalogue()                 # groups, pages, profiles, languages (labels from both dictionaries)
assert afaccess.errors(cat) == []      # ids, labels in every language, one admin group, locked profile with every
                                       # permission, pages guarded, profiles valid and usable, a work profile exists
```

and tests the runtime rules with forced wrong-role API calls (role-denial tests, `IAM-03`).

`python packages/af-access/af_access.py matrix catalogue.json ar` prints the matrix for the owner's review.

## 5. Adoption (2026-10-09)

| Product | Before | Result |
|---|---|---|
| BAMS (reference) | Full model | Exported as `packages/af-access/examples/bams-catalogue.json`; passes the gate |
| Hessa (Teachers) | Full BAMS model + teacher scope | Gate in `tests/test_access_gate.py`: no finding. Added *Who can do what* |
| Trip Orders (Yousef) | Full BAMS model, copied earlier than Hessa | Gate found: ready-made profiles had no Arabic names; a new person was saved under the wrong profile name (Hessa had fixed it, Trip Orders not); "Money" sat in Pages but opens no page. All fixed; *Who can do what* added |
| Al-Store | Four fixed roles in code + per-person extra/removed ticks | 1.1.0: editable profiles, page permissions for Products/Stock/Customers enforced on the server, administrator group, **lock-out bug fixed** (removing a tick from the only owner locked the shop out), audit of ticks added/removed, *Who can do what*; gate in `tests/test_access.py` |

## Sources
- OWASP ASVS 5.0, chapter V8 Authorization — https://github.com/OWASP/ASVS/blob/master/5.0/en/0x17-V8-Authorization.md
- OWASP Authorization Cheat Sheet — https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html
- OWASP Developer Guide, access-control checklist — https://devguide.owasp.org/en/04-design/02-web-app-checklist/07-access-controls/
- NIST RBAC project and ANSI/INCITS 359-2004 — https://csrc.nist.gov/projects/role-based-access-control/faqs
- Square, custom permission sets — https://squareup.com/help/us/en/article/5822-employee-permissions
- Shopify POS roles — https://help.shopify.com/en/manual/sell-in-person/shopify-pos/staff-management/pos-roles
