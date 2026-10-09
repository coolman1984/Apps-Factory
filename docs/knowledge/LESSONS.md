# Lessons learned 📚 — what went wrong, how it was fixed, the rule we keep

Each lesson comes from a real history file. A rule that caught a real bug outranks a rule that only sounds wise.

## Data and money (Hessa, Al-Store)
| What happened | Fix | Rule |
|---|---|---|
| A failed manager-approval login was rolled back together with the sale, so the lockout counter never grew | Verify the approver **before** opening the write transaction (`ctx.approver`) | Security counters live outside business transactions |
| A backup started inside an open write transaction and hung | Backups run outside transactions with the SQLite backup API, then `integrity_check` | Never copy a live SQLite file; never back up inside a tx |
| A ledger "no delete" test passed on an empty table — the trigger never fired | Test on tables that have rows | A guard test must prove the guard ran |
| Instalment "financed" amount included the fee; monthly amount had piasters | One function `instalment_amount` rounds to whole pounds; label fixed | Money words are tested as carefully as money numbers |
| Running balances drift after a correction (Hessa) | Balances computed from ledger lines; corrections are reversing records | Never store a running balance |

## UI (Al-Store 1.0 → 1.0.1)
| What happened | Fix | Rule |
|---|---|---|
| `$('[data-theme]')` matched `<html>`; one click replaced the whole page | JS hooks use dedicated `data-*-toggle` names | State attributes are never JS hooks |
| `'aria-current="page"'` was escaped into a broken attribute | `raw()` / `CUR` constants + a static test forbidding the pattern | Escaping template + tested exceptions |
| CSP blocked inline `style=` → bars had no width | `data-w` + `hydrate()` through CSSOM | Strict CSP from day one, design around it |
| Money read backwards inside Arabic text | Isolate numbers (LRI…PDI) + `unicode-bidi: plaintext` | Test RTL with real numbers, not lorem |
| Top bar 248 px wider than a phone | `min-width: 0` on text-holding flex children; measured sweep | Measure overflow; screenshots lie |
| CLS 0.57 on the phone counter | Results scroll inside their own area; skeletons of the final shape | Reserve space before data arrives |
| Backdrop blur cost ~20 ms/frame on a slow CPU | Opaque gradients | No effect without a UI Lab number |

## Design system v2 (Al-Store → Mizan, 2026-10-08)
| What happened | Fix | Rule |
|---|---|---|
| A neon accent (volt) looked striking in screenshots but failed contrast as text and tired the eye at a counter | One restrained accent used only for the main action; navy for structure | Brand colour is chosen at the counter, not in the demo |
| The factory's own `--af-text-tertiary` was 3.5:1 and used for 10–11px text | `qa/token_gate.py` fails the build; colour darkened | Contrast is a test, not a review comment |
| Raising body text to 16px made a table without a scroll wrapper spill out of its card on a 360px phone | Wrapper added; any bare table in a card scrolls inside it | Re-run the measured layout sweep after every type-scale change |
| KPI money wrapped onto two lines in narrow cards | Container-query font size (`cqi`) and `nowrap` | Numbers shrink, never wrap |
| A phone pay sheet hid its confirm button below the fold | Sticky dialog footer | The action that finishes the task is always visible |

## Review round and Windows build (Al-Store 1.0.2)
| What happened | Fix | Rule |
|---|---|---|
| The same sale line listed twice in one return was checked against the old returned quantity → refunded twice | Count earlier rows of the same request | A validation that reads the database must also count what the same request already added |
| "Activate" with an empty box saved an empty code over the working licence | Refuse empty; test that nothing can wipe the working code | A save button must never be able to replace good data with nothing |
| Shift float appeared in the drawer without leaving the safe → the safe grew every shift | Float comes out of the safe | Every cash move has two sides |
| A product counted, then sold, became a false surplus at count close | "Expected" = books at the moment of counting | Snapshot the comparison point |
| A filter applied after `LIMIT 200` hid customers | Filter in the query | Filter first, limit last |
| Settings accepted any value → one bad value broke every later sale | Typed settings | Validate stored configuration like input |
| A junk-input test found 20+ crashes in an hour | `core.whole/rows/obj/day`, `db._plain`, calm 400s | Test the edges with junk before customers do (QA-02) |
| Printing Arabic to a Windows console (cp1252) killed the compiled server at start-up | `say()`: UTF-8, ASCII fallback, no console OK | Run the built program on the target OS in CI and print its own output when it fails |
| A dialog's delayed `focus()` moved typed text from the password box to the user-name box (1-in-4 flaky test) | Only focus if the person is not already in a field | A flaky UI test is a real race until proven otherwise |
| Tests that deliberately send wrong passwords locked the owner account (the lockout works) | Keep lockout probes on throw-away users | Test accounts used for probing are never the one the rest of the suite needs |

## Automation (opening-nerp-tcode / G-MES, SmartOps, wad)
- **Wait for the exact state**, not a fixed sleep: the grid is "done" when its row count and busy flag say so.
- **Stop on an unknown dialog**; never click "OK" on something you did not expect.
- **A safety cap must not silently truncate**: if a limit is hit, the run fails loudly with the count.
- **Prove every action**: the file exists, has rows, and its header matches — or the step failed.
- Credentials stay in the OS vault (DPAPI), never in config or logs.

## Licence codes (factory, this session)
- Two processes created two install IDs because each test used a new temp folder → the device code differed. Share the data folder; the device code is part of the contract and must be stable.
- The verifier must be stdlib-only so a product does not need `cryptography`; a test checks the vendored copy is byte-identical to the package.
- Locked ≠ hostage: an expired product still reads, exports and backs up (constitution: never hold customer data).

## Films and motion (Animation repo CRAFT / QUALITY_PLAYBOOK)
- Every motion has a cause; blur only while moving; exact rest state; no looping decoration on working screens.
- Capture real screens for promos — never fake UI in marketing.

## Process
- A plan is not a feature. A Markdown rule is not working software. Status words: planned → implemented → verified → field_accepted.
- Every bug becomes a test in the same commit; every recalibrated budget records why.

## People and permissions (BAMS → factory, 2026-10-09)
| What happened | Fix | Rule |
|---|---|---|
| Al-Store's last-owner guard looked at the role name only; removing `users.manage` from the only owner with a per-person "removed tick" locked the shop out of its own settings | Guard on the *right* (`af_access.admin_safety`: last-manager, self-lockout), not on the role name | Protect the permission, not the label |
| Fixed roles in code could not express a real shop's "senior cashier" | Editable profiles with one locked administrator profile (BAMS) | Ship profiles as data the owner can change, never as code |
| Permission changes were audited as "role changed" without the ticks | `perm_diff` added/removed lists in the audit | Log what was granted and removed, by whom |
| Trip Orders copied the BAMS engine before Hessa fixed "a new person saved under the wrong profile name" and never got the fix; its ready-made profiles had no Arabic names | One gate (`packages/af-access`) every product runs in its tests; the gate found both on its first run | Copy the rules as a test, not only as code |
