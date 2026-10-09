"""Shop requests from the relay, the owner-approved trial policy, and delivery of the signed code back.

The chain (docs/LICENCE_ACTIVATION.md): the shop's program asks the relay → the owner's phone is told (Telegram) → THIS program,
on the owner's trusted PC, pulls the request and decides → the signed code goes back through the relay → the shop checks it with
the vendor's public key and switches itself on. The signing key never leaves the studio's memory.

The policy (the owner switches it on; it is OFF until then, and every default is the owner's recorded decision):
  trial   automatic when ALL hold: the key is unlocked, the device code and the PC's tag are well formed, this PC never had a
          trial (permanent ledger), the day's cap is not reached, the sender is not flooding. 14 days at most, device-bound.
          A second request from the SAME device gets the SAME code again (a shop that lost it). Another device on the same PC is refused.
  monthly / permanent   never automatic. The request waits for the owner, who must tick that the payment arrived and write its
          reference. Then the code goes back the same way.
Every step is in the append-only audit. What a shop typed (its name, a payment reference) is shown to the owner as text only.
"""
from __future__ import annotations

import threading
import time
import uuid

from .relay import DEVICE, KIND_AR, KIND_EDITION, MACHINE, REASON_AR, UUID, RelayError, telegram
from .service import MONTHLY_DAYS, StudioError, now_iso

SAME_SOURCE_LIMIT = 5  # more than this many requests from one address in a day are held for the owner to look at (shops share addresses: held, never refused)


class AutoTrial:
    def __init__(self, studio):
        self.s = studio
        self.lock = threading.Lock()
        self.last = {'at': None, 'ok': None, 'error': '', 'pulled': 0, 'issued': 0, 'refused': 0, 'held': 0, 'delivered': 0}
        self._told: set[tuple[str, str]] = set()

    # ------------------------------------------------------------------ the policy
    def verdict(self, r: dict) -> tuple[str, str, dict | None]:
        """('issue' | 'reissue' | 'refuse' | 'hold', reason, existing code row). Pure: it changes nothing."""
        s = self.s
        if r['kind'] != 'trial':
            return 'hold', 'payment_needed', None
        if not DEVICE.match(r['device'] or ''):
            return 'refuse', 'bad_device', None
        if not MACHINE.match(r['machine'] or ''):
            return 'refuse', 'bad_machine', None
        if not s.one('SELECT 1 FROM products WHERE id = ?', r['product']):
            return 'refuse', 'unknown_product', None
        led = s.one('SELECT * FROM trial_ledger WHERE product = ? AND machine = ?', r['product'], r['machine'])
        if led:  # this PC had its trial: only the very same device may get that code again
            if led['device'] == r['device']:
                return 'reissue', '', s.one('SELECT * FROM codes WHERE serial = ?', led['serial'])
            return 'refuse', 'already_used', None
        had = s.one('SELECT * FROM codes WHERE product = ? AND device = ? ORDER BY issued_at DESC LIMIT 1', r['product'], r['device'])
        if had:
            if had['edition'] == 'trial':
                return 'reissue', '', had
            return 'refuse', 'already_used', None
        pol = s.policy()
        # issued_at is stored in UTC, so the day is counted in UTC too: one reset a day, never two (review of PR #34)
        done = s.one("SELECT COUNT(*) AS n FROM codes WHERE issued_by = 'auto-trial' AND substr(issued_at, 1, 10) = ?", time.strftime('%Y-%m-%d', time.gmtime()))['n']
        if done >= pol['auto_trial_daily_cap']:
            return 'hold', 'daily_cap', None
        if r.get('src') and s.one("SELECT COUNT(*) AS n FROM requests WHERE source = 'relay' AND src = ? AND requested_at >= ?", r['src'],
                                  time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - 86400)))['n'] > SAME_SOURCE_LIMIT:
            return 'hold', 'review_src', None
        return 'issue', '', None

    # ------------------------------------------------------------------ requests from the relay
    def ingest(self, item: dict) -> dict | None:
        """Put one pulled request into the studio's own list (once per relay id). Returns the new row, or None if it was already known."""
        s = self.s
        rid = item.get('id')
        if not isinstance(rid, str) or not UUID.match(rid) or item.get('kind') not in KIND_EDITION:
            return None
        if s.one('SELECT 1 FROM requests WHERE relay_id = ?', rid):
            return None
        kind = item['kind']
        days = {'trial': 14, 'monthly': MONTHLY_DAYS, 'permanent': 1}[kind]
        row = {'id': str(uuid.uuid4()), 'product': str(item.get('product') or '')[:48], 'edition': KIND_EDITION[kind], 'device': str(item.get('device') or '')[:20],
               'customer': ' '.join(str(item.get('shop') or '').split())[:80] or '—', 'phone': '', 'days': days,
               'note': ('الدفع: ' + str(item.get('ref') or '')[:60]) if item.get('ref') else '', 'requested_by': 'shop', 'requested_at': now_iso(),
               'status': 'pending', 'source': 'relay', 'relay_id': rid, 'machine': item.get('machine') if isinstance(item.get('machine'), str) else None,
               'src': str(item.get('src') or '')[:16] or None, 'kind': kind, 'payment_ref': str(item.get('ref') or '')[:60]}
        cols = ','.join(row)
        with s.lock:
            s.db.execute(f'INSERT INTO requests({cols}) VALUES ({",".join("?" * len(row))})', list(row.values()))
        s.audit('shop', 'request.relay', {'id': row['id'], 'relay': rid[:8], 'kind': kind, 'device': row['device'], 'machine': (row['machine'] or '')[:8]})
        return s.one('SELECT * FROM requests WHERE id = ?', row['id'])

    def tell(self, key: str, rid: str, text: str):
        """One Telegram message per request and event (a retry loop never repeats it)."""
        if (key, rid) in self._told:
            return
        self._told.add((key, rid))
        telegram(text)

    def deliver(self, r: dict) -> bool:
        """Hand a decided relay request's outcome back through the relay. A failure leaves it for the next cycle."""
        s = self.s
        r = s.one('SELECT * FROM requests WHERE id = ?', r['id'])
        if not r or r['source'] != 'relay' or r['relayed'] or r['status'] not in ('approved', 'refused'):
            return False
        try:
            if r['status'] == 'approved':
                code = s.one('SELECT code FROM codes WHERE serial = ?', r['serial'])['code']
                s.relay.issue(r['relay_id'], code)
            else:
                s.relay.refuse(r['relay_id'], r['held'] if r['held'] in REASON_AR else 'owner_refused')
        except RelayError as e:
            if e.status in (404, 409):  # closed or gone on the relay: the shop will never get this answer from it. Not "sent" (review of PR #34)
                with s.lock:
                    s.db.execute('UPDATE requests SET relayed = 2 WHERE id = ?', (r['id'],))
                s.audit('auto-trial' if r['decided_by'] == 'auto-trial' else 'owner', 'request.undeliverable', {'id': r['id'], 'status': e.status})
                self.tell('undeliverable', r['id'], f'⚠️ قرارك على طلب الجهاز {r["device"]} مااتبعتش: الطلب اتقفل عند الوسيط. ابعت الكود للمحل يدوي.')
            self.last.update(ok=False, error=e.key)
            return False
        with s.lock:
            s.db.execute('UPDATE requests SET relayed = 1 WHERE id = ?', (r['id'],))
        s.audit('auto-trial' if r['decided_by'] == 'auto-trial' else 'owner', 'request.delivered', {'id': r['id'], 'status': r['status']})
        self.last['delivered'] += 1
        return True

    # ------------------------------------------------------------------ one round
    def cycle(self) -> dict:
        """Pull, decide by policy, deliver. Safe to run again at any time; one round at a time."""
        if not self.lock.acquire(blocking=False):
            return {**self.last, 'busy': True}
        try:
            s = self.s
            self.last = {'at': now_iso(), 'ok': True, 'error': '', 'pulled': 0, 'issued': 0, 'refused': 0, 'held': 0, 'delivered': 0}
            if not s.relay.configured():
                self.last.update(ok=None, error='relay.off')
                return dict(self.last)
            try:
                for item in s.relay.pending_all():
                    if self.ingest(item):
                        self.last['pulled'] += 1
            except RelayError as e:
                self.last.update(ok=False, error=e.key)
                return dict(self.last)
            pol = s.policy()
            if pol['auto_trials']:
                for r in s.rows("SELECT * FROM requests WHERE source = 'relay' AND status = 'pending' ORDER BY requested_at"):
                    self.decide_by_policy(r)
            for r in s.rows("SELECT * FROM requests WHERE source = 'relay' AND status IN ('approved', 'refused') AND relayed = 0 ORDER BY requested_at"):
                self.deliver(r)
            return dict(self.last)
        finally:
            self.lock.release()

    def decide_by_policy(self, r: dict):
        s = self.s
        kind, reason, existing = self.verdict(r)
        if kind == 'refuse':
            self._close(r, 'refused', reason)
            self.last['refused'] += 1
            self.tell('refused', r['id'], f'⛔ طلب {KIND_AR[r["kind"]]} اترفض تلقائيًا\nالجهاز: {r["device"]}\nالسبب: {REASON_AR.get(reason, reason)}')
            return
        if kind == 'hold':
            if r['held'] != reason:
                with s.lock:
                    s.db.execute('UPDATE requests SET held = ? WHERE id = ?', (reason, r['id']))
                self.last['held'] += 1
                if reason != 'payment_needed':  # paid requests were already announced by the relay
                    self.tell('held:' + reason, r['id'], f'⏳ طلب {KIND_AR[r["kind"]]} مستني قرارك\nالجهاز: {r["device"]}\nالسبب: {REASON_AR.get(reason, reason)}')
            return
        if not s.unlocked():  # the policy would allow it, but the key is locked: wait, and say so once
            if r['held'] != 'locked':
                with s.lock:
                    s.db.execute("UPDATE requests SET held = 'locked' WHERE id = ?", (r['id'],))
                self.last['held'] += 1
                self.tell('locked', r['id'], f'🔒 فيه طلب تجربة مستني والبرنامج مقفول\nالجهاز: {r["device"]}\nافتح برنامج التراخيص واكتب كلمة السر.')
            return
        if not s.claim(r['id']):  # the owner decided it a moment ago
            return
        try:
            if kind == 'reissue':
                serial = existing['serial']
            else:
                code = s.issue(r['product'], 'trial', r['device'], r['customer'], '', s.policy()['auto_trial_days'], note='تجربة تلقائية بسياسة المالك',
                               actor='auto-trial', request_id=r['id'], machine=r['machine'])
                serial = code['serial']
        except StudioError as e:
            s.release(r['id'])
            if e.key == 'key.locked':
                return
            self._close(r, 'refused', 'already_used' if e.key == 'trial.repeat' else 'bad_device')
            self.last['refused'] += 1
            return
        with s.lock:
            s.db.execute("UPDATE requests SET status = 'approved', decided_at = ?, decided_by = 'auto-trial', serial = ?, held = '' WHERE id = ? AND status = 'deciding'",
                         (now_iso(), serial, r['id']))
        s.audit('auto-trial', 'request.approve', {'id': r['id'], 'serial': serial, 'reissued': kind == 'reissue'})
        self.last['issued'] += 1
        self.deliver(r)
        self.tell('issued', r['id'], f'✅ اتصدّرت تجربة 14 يوم تلقائيًا{" (نفس الكود تاني)" if kind == "reissue" else ""}\nالجهاز: {r["device"]}\nرقم الكود: {serial}')

    def _close(self, r: dict, status: str, reason: str):
        s = self.s
        with s.lock:
            s.db.execute('UPDATE requests SET status = ?, decided_at = ?, decided_by = ?, held = ? WHERE id = ? AND status = ?',
                         (status, now_iso(), 'auto-trial', reason, r['id'], 'pending'))
        s.audit('auto-trial', 'request.refuse', {'id': r['id'], 'reason': reason})
        self.deliver(r)

    # ------------------------------------------------------------------ owner's decisions on a relay request
    def owner_decided(self, rid: str):
        """The owner approved or refused in the studio: send the outcome to the shop through the relay (best effort, retried each round)."""
        r = self.s.one('SELECT * FROM requests WHERE id = ?', rid)
        if r and r['source'] == 'relay':
            self.deliver(r)

    # ------------------------------------------------------------------ background loop
    def loop(self, stop: threading.Event, every: float = 60.0):
        while not stop.wait(every):
            try:
                self.cycle()
            except Exception:  # the loop must outlive any one bad round
                self.last.update(ok=False, error='crash')

    def start(self, every: float = 60.0) -> threading.Event:
        stop = threading.Event()
        threading.Thread(target=self.loop, args=(stop, every), daemon=True).start()
        return stop

