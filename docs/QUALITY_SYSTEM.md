# Quality department ✅

**Status:** `implemented` as a checklist + the automated suites below; first product filled it: Al-Store 1.0.1. Control `QA-01`.
Rule zero: a check counts only when it ran on the exact commit and its output is recorded. Skipped stays skipped.

## The quality report of a release candidate
| # | Gate | How (Al-Store example) | Result recorded |
|---|---|---|---|
| Q1 | Rules of the business (money, stock, approvals, instalments) | `tests/test_domain.py` | count + OK |
| Q2 | HTTP, security guards, roles that must be refused | `tests/test_api.py` (CSP, Host, Origin, lockout, cashier denied) | count + OK |
| Q3 | Licence gate (none / other PC / expired / clock back) | `tests/test_api.py::LicenceGateTests`, browser `LicenceLock` | OK |
| Q4 | Words in both languages, no inline styles, logical CSS, icons exist, size budgets | `tests/test_frontend.py` | OK |
| Q5 | Core journey in a real browser (sell → print → return with approval) | `tests/test_e2e_browser.py::CoreJourney` | OK |
| Q6 | Measured layout sweep: 360 / 390 (XL text) / 820 dark / 1366 English, every route | `LayoutSweep` (UX-08) | OK |
| Q7 | Speed, smoothness, accessibility on a ×4 slower CPU | `tools/ui-lab` → `docs/ui-lab/REPORT.md` (PERF-01, A11Y-01) | "All pages within budget" |
| Q8 | The factory code chain: studio key → device-bound code → product accepts, other PC refuses | `apps/licence-studio/tests/test_studio.py` | OK |
| Q9 | Clean-PC install + restore drill | field | PENDING until done |
| Q10 | Receipt printer (80 mm / 58 mm, Arabic shaping on the real driver) | field | PENDING until done |
| Q11 | First paying user completes the journey alone | field | PENDING until done |

A candidate with any Q1–Q8 red is NO-GO. Q9–Q11 pending means "pilot only", never "ready to sell" (DELIVERY_GATES).

## The design review rubric ("Showroom bar")
Answered by a person looking at the UI Lab screenshots, light and dark, Arabic and English:
1. Can a cashier find **the one action** of each screen in one second? (one volt button)
2. Does every empty / loading / error / denied / offline state say what to do next?
3. Does any number, name or badge touch an edge, wrap badly or read backwards in RTL?
4. Is every motion caused by the user, short, and gone at rest? Would "reduce motion" lose information?
5. Would the owner trust this screen with money? (ledger words, reversals with reasons, approvals visible)

## Where the tests came from
Every bug found becomes a test in the same commit (Hessa and Al-Store histories). A finding of the UI Lab or the sweep that was
fixed is listed in the product's DEVELOPMENT_HISTORY with before/after numbers.
