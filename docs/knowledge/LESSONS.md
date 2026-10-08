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
