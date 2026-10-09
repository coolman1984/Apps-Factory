# af-consent v0.1.0: two-level consent records

**Status:** `implemented`. It is unit-tested here; no product uses it yet. Standard: [docs/PRIVACY_TELEMETRY_STANDARD.md](../../docs/PRIVACY_TELEMETRY_STANDARD.md).

Controls: `PRIV-01`, `PRIV-02`.

Copy it into a product with:

```
python scripts/vendor_consent.py <repo>
```

This writes `server/afconsent.py`, `<js>/vendor/af-consent.js` and `<css>/af-consent.css`.

```python
import afconsent
db.executescript(afconsent.SQL)
consent = afconsent.Consent(db, on_change=tel.on_consent_change)        # purge the outbox on decline/withdraw
p = afconsent.prompt(lang, afconsent.vendor_name(settings, DEVELOPER))   # {"text_id", "text", "agree", "decline", "more"}
consent.record('person', me.id, 'agree', p['text_id'], p['lang'], by=me.id)
consent.allowed(me.id)        # installation AND person agreed
consent.needs_prompt(me.id)   # show the card at sign-in
consent.status(me.id)         # for Settings «الخصوصية والمساعدة»
```

Browser:
- `AFConsent.ask(prompt, decide)` shows the first sign-in card. Its two buttons look the same, and Esc does not decide.
- `AFConsent.settings(box, {status, prompt, decide, showSent})` renders the consent section in Settings.

`python -m unittest discover -s tests -v`
