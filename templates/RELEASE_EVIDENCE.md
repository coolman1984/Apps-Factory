# Release evidence | one exact candidate

Product: ___ / Version: ___ / Commit: ___ / Artifact SHA-256: ___ / Owner: ___

| Gate | Actual test and artifact | Result (PASS / NO-GO / UNKNOWN) | Reviewer & date |
|---|---|---|---|
| G0 market | | | |
| G1 scope / data map | | | |
| G2 design / threat / roles | | | |
| G3 actual reused capability code | | | |
| G4 CI + browser negatives + money/retries | | | |
| G5 clean target OS install & upgrade | | | |
| G6 real-user acceptance + separate-PC backup restore | | | |
| G7 commercial/terms/privacy/support | | | |

### Security negatives
- Client sets role/admin=true; denied by server: ___
- Change record ID/org ID/export query to neighbor: denied: ___
- Tamper subscription date/signature or replay webhook: denied: ___
- Demo shortcut in production: unavailable: ___
- Vendor support without customer approval and after revocation: denied: ___
- Retry double payment/import; finance historical totals correct: ___
- Live data accidentally in logs/builds: none: ___

Known limitations, actual skipped checks and required real-world equipment:
Decision: **NO-GO unless all applicable gates are supported by verifiable evidence**.
