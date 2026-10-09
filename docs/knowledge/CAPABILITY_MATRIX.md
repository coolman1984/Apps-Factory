# Capability matrix: what each product has, and what moves where

**Owner's rule (2026-10-09):** every repository carries the best of the others. A good capability in a product comes into the
factory as a standard or package. A factory capability that a product lacks goes into that product. In the end, all products
offer the same core capabilities.

Survey of 2026-10-09, based on code, tests and workflows (not on docs alone).
✓ = present, ◐ = partial, — = absent.

| # | Capability | BAMS | Hessa | Trip Orders | Al-Store | Factory (standard / package) |
|---|---|---|---|---|---|---|
| 1 | Licence codes (signed, trial, grace, read-only after expiry) | — | ✓ | — | ✓ | ✓ `packages/af-license` |
| 2 | Recycle bin / restore deleted | ✓ | ✓ | ✓ | — (ledger rows are reversed, never deleted) | — |
| 3 | Undo an edit from history | — | ✓ | — | ◐ (reversals) | — |
| 4 | Own app window | ✓ | ✓ | — | — | — |
| 5 | Step-by-step guides + "Guide me" coach | ◐ (af-guide copied) | ✓ | ✓ (2026-10-09) | ✓ (2026-10-09) | ✓ `HELP_AND_GUIDANCE_STANDARD`, `packages/af-guide` (HELP-07) |
| 6 | "Solve a problem" with a guide per problem | ◐ (af-guide copied) | ✓ | ✓ (2026-10-09) | ✓ (2026-10-09) | ✓ `packages/af-guide` (HELP-09) |
| 7 | Learning path per role with "you are here" | ◐ (af-guide copied) | ✓ (2026-10-09) | ✓ (2026-10-09) | ✓ (2026-10-09) | ✓ `packages/af-guide` (HELP-07: `course`, `state`) |
| 8 | "Check my data" button | ✓ | ✓ | ◐ | ◐ | — |
| 9 | Automatic backups + second folder/USB | ✓ | ✓ | ✓ | ✓ | — |
| 10 | Owner's watch (anti-theft alerts) | — | ✓ | — | ✓ | — |
| 11 | Activity log incl. clicks | ✓ | ✓ | ◐ | ◐ | — |
| 12 | Support link to the seller's Control Center | — | ✓ | — | ✓ | ✓ `apps/control-center` |
| 13 | Fuzz (junk input) tests | — | — | — | ✓ | QA-02 |
| 14 | UI lab (performance + accessibility gate) | — | — | — | ◐ | ✓ `tools/ui-lab` |
| 15 | Wide Linux font + 360 px phone browser test | — | ✓ | — | ◐ | — |
| 16 | Several PCs share data | ✓ | ✓ | ✓ | — | — |
| 17 | Command palette | ✓ | ✓ | ✓ | ✓ | — |
| 18 | Print/PDF + Excel export | ✓ | ✓ | ✓ | ◐ (CSV) | — |
| 19 | First-run tour / slides (in Help) | ◐ | ✓ | ✓ | — | — |
| 20 | Windows installer + `--check` of shipped files | ◐ | ✓ | ◐ | ✓ | ✓ template |
| 21 | CI runs unit + browser tests | ◐ | ✓ | ✓ | ✓ | ◐ |
| 22 | Release notes for users | ✓ | ✓ (build stops without them) | ✓ | ✓ | ◐ template |
| 23 | Both dictionaries have the same keys (test) | n/a (English only) | ✓ | ✓ | ✓ | — |
| 24 | Strict CSP: no inline style/script (test) | ◐ | ◐ | ◐ | ✓ | — |
| 25 | Trial sign-in / practice shop | ◐ | ✓ | ◐ | ✓ | — |
| 26 | People, profiles, page visibility gate | ✓ (source) | ✓ | ✓ | ✓ | ✓ `packages/af-access` |

## Worth copying (found in one product only)
| Capability | Where | Goes to |
|---|---|---|
| Ledger tables refuse UPDATE/DELETE by trigger | `Store/server/db.py` | Hessa and Trip Orders money tables; factory data standard |
| Smoke test of the built `.exe` | `Store/tools/smoke_exe.py` | already in the installer template; Hessa, Trip Orders |
| Junk-input (fuzz) tests | `Store/tests/test_fuzz.py` | every product (QA-02) |
| Strict CSP + "no inline style" test | `Store/tests/test_frontend.py` | Hessa, Trip Orders (needs removing inline styles first) |
| Wide-font layout test (DejaVu at XL, 360 px) | `Teachers/tests/test_acceptance.py` | Store, Trip Orders |
| Owner's watch page | `Teachers/server/watch.py` | Trip Orders (fuel, cancelled trips), BAMS |
| Offline outbox for the phone link | `Yousef-Transportation/gateway/public/app/outbox.js` | Hessa parent/owner pages |
| Undo an edit from change history | `Teachers/js/views/audit.js` | Trip Orders, BAMS |

## Order of work (value first, smallest change first)
1. **Done 2026-10-09:** guides, "Solve a problem", learning paths and simple formal Arabic in Hessa, Trip Orders and Al-Store,
   checked by `af-guide`; the same `af-guide` copy is also in BAMS (its own guides are still to be checked). People and
   permissions in the three products, checked by `af-access`.
2. **Next:**
   - wide-font layout test in Store and Trip Orders;
   - fuzz tests in Hessa and Trip Orders;
   - licence codes in Trip Orders (`scripts/vendor_licence.py`);
   - "Check my data" in Trip Orders and Store.
3. **Then:**
   - owner's watch in Trip Orders;
   - undo from history in Trip Orders;
   - ledger triggers in Hessa and Trip Orders;
   - strict CSP in Hessa and Trip Orders.
4. **Owner decision needed:** several PCs in Al-Store (a large change; a single shop usually has one PC plus phones).

Each item ships as its own pull request with tests, like the rest of the factory.
