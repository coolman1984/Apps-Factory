# Licence protection standard

This shared layer protects paid actions while always keeping read, export and backup available. It never deletes, hides, encrypts or changes customer data.

- **Block significant clock rollback gently.** Remember the latest UTC instant observed locally, solely as rollback evidence. Default tolerance is 2 hours; a paid product may choose 72 hours. Small corrections within tolerance can restore access, including across midnight: an untrusted local maximum never independently sets the expiry day.
- **Recover from a mistaken future clock.** After correcting the PC clock, a fresh authenticated vendor day may correct `max_seen` when it is more than the tolerance ahead of the corrected clock and the vendor day equals the corrected local licence day, or when it is more than the tolerance beyond that vendor day's latest possible instant (for other fresh days). Only the server can prove this recovery. A fresh aware server timestamp can also repair a same-day future time. Recovery persists across restart. Historical anchors cannot prove today's date and cannot lower `max_seen`.
- **Keep trusted expiry evidence.** Remember the newest authenticated vendor day. Ignore older vendor days entirely, including for clock repair. Recovery never lowers this trusted day, changes signed terms or reopens a licence already expired according to it. Equal days are usable for repair only when the adapter has independently established response freshness.
- **Use the customer's licence calendar consistently.** Existing codes define whole days in the customer's local calendar. `first_day`, `last_day` and signed grace all use that calendar, with inclusive last days. Configure the same stable `calendar_tz` in the guard and server adapter. Prefer an aware UTC server timestamp passed to `note_server_time`, which converts it to that calendar. `note_server_day` requires a vendor date already expressed in that same calendar; a bare UTC day is incompatible outside UTC. The default is the system local timezone; an injected `today` must agree with the configured calendar. A perpetual code (`last_day=None`) never expires by date.
- **Check online when due.** Poll on startup, about every 6 hours while connected, and on reconnection when due. Re-check access immediately after successful responses. Failed requests use the product's normal backoff and preserve retained evidence.
- **Protect against removal of one state file.** Protected products must supply both independent verified anchor callbacks described below and restore the anchor before paid actions. The anchor retains authenticated server-time evidence in separate licence metadata outside the program folder, across upgrades. It may also retain the latest rollback watermark (`max_seen`) alongside the verified vendor day so deleting or corrupting `licence_clock.json` alone cannot erase a post-expiry local observation. Only a fresh server response may lower that watermark. No customer records are changed.
- **Use no aggressive local counters.** No runtime, usage, per-day hour or lockout counters. Persistence retry timestamps only schedule I/O; they never measure usage or consume an allowance.
- **Accept the offline limits.** A never-online PC with a frozen date may avoid date expiry. Erasing/restoring all local state, including every independent anchor, cannot be defeated by this helper alone. Those limits never justify risking customer data.

Origin: **Teachers PR #35**. Its **30-hour-per-date runtime counter is intentionally excluded**. The owner supplied this origin; the PR was not independently reviewed here.

## Wiring a protected product

`from af_license import ClockGuard` and `from af_license.guard import ClockGuard` work with the standard library only. `from af_license import codes` also uses only the standard library for verification. Package exports load `core`/`cryptography` only when its API is requested; signing still requires `cryptography` on the vendor machine. Existing core exports remain available.

Create one guard in the product's existing data folder. Keep signature, product, device and trial-key checks in the existing code reader. This helper makes no network requests and verifies no server responses itself.

```python
from time import monotonic
from zoneinfo import ZoneInfo
from af_license import ClockGuard, codes
from af_license.guard import should_check_server

licence_calendar = ZoneInfo(configured_licence_timezone)

# Product-owned adapters, required before claiming deletion protection:
# read_verified_time_anchor() -> verified YYYY-MM-DD; None only for a
# confirmed fresh installation. Missing/unreadable/unverified evidence in
# an established protected installation raises OSError or ValueError.
# retain_verified_time_anchor(record) durably retains the authenticated proof,
# atomically and independently of licence_clock.json, bound to this product,
# device and calendar. The guard passes either a plain YYYY-MM-DD vendor day
# or a compact JSON object {"day":"YYYY-MM-DD","max_seen":"<aware-or-UTC-iso>"}
# when rollback evidence must be mirrored. It never lowers an existing anchor
# or invents a proof.
# It raises OSError/ValueError on failure. It must not mutate customer records.
# Both functions check provenance; copying the guard's JSON is insufficient.
guard = ClockGuard(
    data_dir / 'licence_clock.json', calendar_tz=licence_calendar,
    load_anchor=read_verified_time_anchor,
    save_anchor=retain_verified_time_anchor,
)
last_check_mono = None

# Run at startup and periodically, including when connectivity returns:
guard.note_seen()  # also retries pending persistence and anchor recovery
if online and should_check_server(last_check_mono, monotonic()):
    # Authenticate vendor identity/TLS, enforce timeout, reject unexpected
    # redirects, cached/stale/replayed responses and mismatched scope.
    # A signed response also needs freshness validation (e.g. request nonce).
    # Retain its verified proof for the anchor writer; no client signing key.
    server_instant = fetch_fresh_verified_vendor_time()
    guard.note_server_time(server_instant)  # aware datetime, including UTC
    last_check_mono = monotonic()

verified = codes.read_code(
    saved_code, trusted_public_keys, product_id, device_code,
    today=guard.effective_day(), trial_only_keys=trial_only_keys,
)
access = guard.evaluate(verified)
# Re-check on paid actions and after every server response.
# Enforce access['full'] on paid writes; always allow read/export/backup.
```

The adapter functions above are product requirements, not APIs supplied by this package. If the endpoint returns only a day, it must use the configured licence calendar and the same authenticity/freshness checks before `note_server_day(day, tolerance_hours=...)`. Pass the same tolerance policy to evaluation and recovery. Changing the PC timezone is not a way to establish trusted calendar policy; products should persist their configured licence timezone independently.

The loader is called at construction and retried after recoverable failures. It restores the latest trusted expiry day and mirrored rollback watermark even if the guard file is missing, corrupt or an older valid snapshot. A vendor day in the clock file that the anchor has not accepted is discarded on load in favour of the verified anchor day. Every new server day is retained independently by the writer before attempting the guard file save; the in-memory vendor day does not advance until that write succeeds. Write failures preserve memory and retry, including unchanged-day responses and frozen wall clocks. If an anchor cannot be read or retained, `evaluate` returns `anchor_unavailable` with `full=False` (unless another restriction already applies). Repairing metadata access restores normal evaluation without a usage allowance or permanent lockout. Read/export/backup remain available throughout.

`guard.deletion_protected` reports whether both callbacks are configured, the anchor is available and the newest server day is retained. Without callbacks, standalone clock protection is still usable, but **deletion resistance is unimplemented**: removing this file can lose trusted expiry evidence. Products must not claim the protected startup contract without implementing and testing the adapters. A fresh server response remains necessary for lowering a mistaken local maximum; restoring an old signed anchor alone cannot perform that recovery.

`evaluate` returns `state`, `full`, `reason` and ISO `effective_day`, the latest of local today and the retained trusted vendor day in the licence calendar. UTC observations do not independently affect expiry. Signed start/end/grace terms are rechecked even for previously active, expired or future results. `note_seen(at=...)` can restore rollback evidence from verified signed product metadata, but does not replace the independent expiry anchor.

State writes use a unique sibling temporary file, flush/file `fsync` and atomic `os.replace`. Ordinary local observations save first and after 5 minutes of forward movement; vendor advances and authenticated corrections save immediately unless retry backoff is pending. Failed writes retry after 5 monotonic seconds even when wall time and vendor day are unchanged. They preserve old disk state, in-memory evidence and unrelated files. Up to five minutes of unsaved local observations can be lost on restart. Create the folder first and use one writer per file. Parent-directory crash durability, Windows and power-loss behavior require product drills.

`vendor_licence.py` currently copies only the code verifier. Integrate the optional guard and independent anchor before claiming product protection. This package does not claim an already deployed adapter, live polling or field acceptance.

## Fix evidence (2026-10-13)

Customer job: protect paid actions without trapping an honest customer after a wrong clock, shortening paid calendar days or touching customer records. Acceptance: reproduce each review failure with synthetic clocks, genuinely signed licences/anchors, frozen-time I/O faults and the exact documented imports without third-party packages.

Live [Agent Use Cases catalogue](https://agentusecases.ai/), [narrow-change entry](https://agentusecases.ai/use-case/hand-narrow-code-changes-to-devin-for-pull-requests) and [primary account](https://frontierai.substack.com/p/one-month-of-using-devin) checked 2026-10-13. The account reports small-change success and integration failure; those anecdotes were not independently reproduced. Applied lesson: reproduce the real signed-code/import/restart boundary rather than infer integration from component checks.

Relevant catalogue routing: [Addy's official repository](https://github.com/addyosmani/agent-skills) / [security reference](https://skills.addy.ie/skills/security-and-hardening/) and [official Claude Security README](https://github.com/anthropics/claude-plugins-official/blob/main/plugins/claude-security/README.md), checked as reference material only. Applied explicit trust boundaries, focused changes and reproducible negative tests. No other CLI/agent was invoked and no upstream code, dependencies or setup commands were adopted. Stable versions, commits, changelogs, licenses and advisories: **NOT VERIFIED**; GitHub API release/commit lookups failed. These tools are not dependencies. Other specialist upstreams and ManimGX: **not applicable** (local Python licensing; no UI, motion or video).

Official Python [date/time semantics](https://docs.python.org/3.13/library/datetime.html) and [atomic replacement](https://docs.python.org/3.13/library/os.html#os.replace) checked; calendar and I/O behavior were exercised locally. Test results and remaining gates are recorded below after validation. Product adapter authentication/freshness, live polling, Windows, power loss, clean-PC recovery and field acceptance remain pending.

Validation actually run in `packages/af-license`: `python -m unittest discover -s tests` — **79 passed**, using a temporary system-site-packages virtualenv because this host has no global `python` command. `AF_STORE_REPO=/tmp/af-license-validation-3h9r6lyy/Store` points to an isolated worktree of the **real Store repository**, source commit `1be5dac5eaf2d5c58f0bd6ae3c14b6d1aa2a4464`, with only its two generated verifier files refreshed by `scripts/vendor_licence.py`. This is not a synthetic consumer; the existing drift test was neither changed nor skipped. The original `/workspace/Store` checkout was not modified. The unconfigured `python3` suite ran 79 tests with **78 passed, 1 failed** because that original sibling still has pre-existing verifier drift; consumer release work remains pending there.

Guard/import regression coverage: **34 passed**, including future-jump repair after restart, same-day repair, tolerance crossing midnight, UTC-negative/positive inclusive start/end/grace, frozen-wall-clock persistence retries, independently signed device-bound anchor recovery after removal/corruption/old snapshots, unavailable/unverified anchor handling and a fresh `python -I -S` consumer process verifying a genuine signed code without `cryptography`. Root documentation checks: **5 passed**. `git diff --check` passed. No CI, deployment, installer, live endpoint or sales-readiness claim.
