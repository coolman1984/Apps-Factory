# Hidden diagnostics probe

Controls: `DIAG-01` … `DIAG-03`. Builds on [PROTECTION_UPDATES_AND_SUPPORT.md](PROTECTION_UPDATES_AND_SUPPORT.md) and `apps/control-center`.

Every product contains an isolated diagnostics module that does not appear in customer menus. The vendor starts it from the
Control Center only while the customer has an open support window with the `repair` scope (the existing grant rules apply:
customer-initiated, time-boxed, visible, revocable, audited).

| Probe | Checks |
|---|---|
| Data | integrity of every database file, signed history, schema version, free space |
| Backups | last backup age, test restore into a temporary folder, extra backup folders reachable |
| Network | own port answers, other site PCs and sync port reachable, internet and Control Center reachable, clock offset |
| Sync | pending changes, last exchange per PC, conflicts waiting |
| Licence | state, device binding, clock rollback |
| Program | version, recent errors (redacted) |

Rules: read-only; temporary files only; no names, phone numbers or money in the report; each run written to the product's
security log and the Control Center audit. Fixes reach the customer as signed updates (see the protection spec), never as
ad-hoc changes.
