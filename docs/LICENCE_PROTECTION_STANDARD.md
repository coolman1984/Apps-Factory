# Licence protection standard

This shared layer protects paid actions while always keeping read, export and backup available. It never deletes, hides, encrypts or changes customer data.

- **Block clock rollback.** Remember the latest UTC time seen; a rollback beyond the tolerance enables read/export/backup mode. Correcting the clock restores normal evaluation. Default tolerance is 2 hours; a paid product may choose 72 hours.
- **Fix the paid end in the signed code.** Only its `last_day` plus signed `grace_days` sets the end. Both are inclusive. A perpetual code (`last_day=None`) never expires by date.
- **Check the server date whenever online.** Poll on startup and about every 6 hours while connected, and on reconnection when due. Remember only the newest vendor date and re-check expiry immediately. An expired licence allows read/export/backup only. A server date can advance the effective date, never extend the signed period.
- **Use no aggressive local counters.** No runtime, per-day hour or lockout counters that can block honest users.
- **Close reasonable loopholes without risking user data.** Keep the time high-water mark outside the program folder, retain it across upgrades, and restore trusted time from the product's own verified signed data. Keep signature and device checks in the existing code reader.
- **Accept the never-online edge case.** A PC that never connects and keeps its date frozen may avoid date expiry. This accepted limit does not justify counters or any risk to user data.

Origin: **Teachers PR #35**. Its **30-hour-per-date runtime counter is intentionally NOT part of this standard**; the online server-date check replaces it. The owner supplied this origin; the PR was not independently reviewed here.

## Wiring a product

Create one `ClockGuard` in the product's existing data folder. It uses only Python's standard library. The existing code reader verifies signatures, product and device binding.

```python
from time import monotonic
from af_license import ClockGuard, codes
from af_license.guard import should_check_server

guard = ClockGuard(data_dir / 'licence_clock.json')
last_check_mono = None  # keep in memory, reset on process restart
# If available: guard.note_seen(at=timestamp_from_verified_signed_product_data)

# Run at startup and periodically, including when connectivity returns:
guard.note_seen()
if online and should_check_server(last_check_mono, monotonic()):
    # Product supplies a vendor HTTPS client with a timeout and network-error handling.
    # On failure, retain last_check_mono and retry with the product's normal backoff.
    server_day = fetch_vendor_day()  # successful response: validated YYYY-MM-DD
    guard.note_server_day(server_day)
    last_check_mono = monotonic()

verified = codes.read_code(
    saved_code, trusted_public_keys, product_id, device_code,
    today=guard.effective_day(),
    trial_only_keys=trial_only_keys,  # preserve the product's existing trust policy
)
access = guard.evaluate(verified)  # optional tolerance_hours=72 for paid products
# Re-check on paid actions and after every server-date response.
# Enforce access['full'] on paid write routes; always allow read/export/backup.
```

`evaluate` returns `state`, `full`, `reason` and an ISO string `effective_day`: the latest of local today, the UTC high-water date and the vendor date. It re-checks signed expiry and start dates, even for a previously active result. It makes no network requests.

Writes use a unique temporary file and atomic `os.replace`. Wall time is saved first, then after at least 5 minutes forward; server-date advances are saved immediately. Missing/corrupt/unreadable state starts fresh. Write failures preserve memory. Create the data folder first; use one writer per file.

Deleting state loses only its high-water marks on restart. Up to five minutes of unsaved observations can also be lost. Restore trusted time using `note_seen(at=...)` from verified signed product data. `vendor_licence.py` currently copies only the code verifier; integrate the optional guard before claiming product protection.

## Implementation evidence (2026-10-13)

[Agent Use Cases precedent](https://agentusecases.ai/use-case/hand-narrow-code-changes-to-devin-for-pull-requests) and [primary account](https://frontierai.substack.com/p/one-month-of-using-devin): reported small-change success and wider-integration failure, not independently reproduced. Applied: narrow scope, signed-code integration and recovery tests. A second Delete-button entry was unavailable (**NOT VERIFIED**).

Routing checked: [Addy's catalogue](https://github.com/addyosmani/agent-skills) / [security guidance](https://skills.addy.ie/skills/security-and-hardening/), [Claude Security README](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/claude-security/README.md), [Python atomic replacement](https://docs.python.org/3/library/os.html#os.replace). Applied local validation and negative checks; installed/ran no upstream tools. Upstream versions, changelogs and advisories: **NOT VERIFIED**. ManimGX: **not applicable** (no visuals).

Validation: 18 guard tests, 5 documentation tests and a standalone `python3 -S` stdlib smoke check passed. Full suite: `python3 -m unittest discover -s tests` from `packages/af-license`, **63 passed with `AF_STORE_REPO` pointing to a freshly vendored synthetic consumer inside this repo**. The default run failed only the pre-existing sibling Store drift check; `codes.py` is unchanged from HEAD and Store was not modified. There is no `python` command here. Product wiring, live polling, Windows and field acceptance remain pending.
