# Business calendar vs UTC on CI runners

**Source:** a product test fix ported to the factory on 2026-10-13.

## What went wrong

API tests asserted `date.today()` and record date fields against the **runner's local calendar**. GitHub Actions uses UTC. A product whose server uses a fixed business timezone (e.g. Africa/Cairo) can be on the **previous or next calendar day** relative to UTC around midnight. Tests passed locally and failed in CI (or the reverse).

## Fix pattern

In integration tests, compute "today" the same way the server does:

```python
from datetime import datetime, timezone

def business_today(business_tz):
    return datetime.now(timezone.utc).astimezone(business_tz).date()
```

Import the product's `BUSINESS` tz constant (or inject it in test config). Never use bare `date.today()` for assertions on server-generated dates unless the server explicitly uses local wall clock without a business zone.

## Rule

**Assertions on business dates must use the product's business timezone, not the CI runner's default zone.**
