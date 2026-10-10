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
The owner's buttons (Telegram «✅ موافق» / «❌ رفض», handled by the relay): «رفض» closes the request on the relay at once; this program
only learns of it (`sync_closed`). «موافق» is recorded on the relay and read here (`tg_decision`): for a TRIAL it stands in for the
policy even when the policy is off (the owner decided this one request by hand), so the owner's own caps do not hold it back; every hard
rule still does: key unlocked, well-formed device and PC tag, known product, one trial per PC. For monthly / permanent it records
the owner's intent only: signing still needs the payment tick and reference in this program. How long an approval counts is the relay's
decision (it answers `expired`): this program never judges it by its own clock.
Whatever way a code is signed for a shop's request, the owner's phone gets a copy of it (the manual way when the shop is offline).
Every step is in the append-only audit. What a shop typed (its name, a payment reference) is shown to the owner as text only.
"""
from __future__ import annotations

import calendar
import threading
import time
import uuid
from html import escape as html_escape

from .relay import DEVICE, KIND_AR, KIND_EDITION, MACHINE, REASON_AR, UUID, RelayError, telegram, telegram_configured
from .service import MONTHLY_DAYS, StudioError, now_iso, utc_today

TRIAL_DAYS = 14      # the trial a shop asks for, and the one an owner's button gives
CLAIM_SECONDS = 300  # a copy to the owner being sent for longer than this is taken to have died
COPY_WINDOW = 2 * 86400  # a copy is only sent while the code is this fresh: Telegram set up weeks later must not pour old codes onto the owner's phone
CHECK_SECONDS = 5  # each network step of the one look at the relay before signing waits at most this long (a socket timeout, not a total deadline)
RELAY_FORGETS = 3 * 86400  # a waiting request the relay does not know for this long is closed here (it can never be answered)
BUTTON = 'telegram'  # who signed when the owner's «✅ موافق» on Telegram was the decision (the owner's own press, not the policy)

SAME_SOURCE_LIMIT = 5  # more than this many requests from one address in a day are held for the owner to look at (shops share addresses: held, never refused)


class AutoTrial:
    def __init__(self, studio):
        self.s = studio
        self.lock = threading.Lock()
        self.last = {'at': None, 'ok': None, 'error': '', 'pulled': 0, 'issued': 0, 'refused': 0, 'held': 0, 'delivered': 0}
        self._told: set[tuple[str, str]] = set()
        self._deliver_lock = threading.Lock()  # a click's own thread and the round must not both hand the same decision to the relay

    # ------------------------------------------------------------------ the policy
    def verdict(self, r: dict, approved: bool = False) -> tuple[str, str, dict | None]:
        """('issue' | 'reissue' | 'refuse' | 'hold', reason, existing code row). Pure: it changes nothing. `approved`: the owner pressed
        «✅ موافق» for this very request, so the day's cap and the flood check (the owner's own limits) do not hold it back."""
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
        if approved:
            return 'issue', '', None
        pol = s.policy()
        # issued_at is stored in UTC, so the day is counted in UTC too: one reset a day, never two (review of PR #34)
        done = s.one("SELECT COUNT(*) AS n FROM codes WHERE issued_by = 'auto-trial' AND substr(issued_at, 1, 10) = ?", utc_today())['n']
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
        known = s.one('SELECT id, tg_decision, held FROM requests WHERE relay_id = ?', rid)
        if known:
            if known['held'] == 'relay_gone':  # the relay lists it again: it is a normal waiting request once more
                with s.lock:
                    s.db.execute("UPDATE requests SET held = '' WHERE id = ? AND status = 'pending' AND held = 'relay_gone'", (known['id'],))
            self.note_decision(known, item)
            return None
        kind = item['kind']
        days = {'trial': 14, 'monthly': MONTHLY_DAYS, 'permanent': 1}[kind]
        row = {'id': str(uuid.uuid4()), 'product': str(item.get('product') or '')[:48], 'edition': KIND_EDITION[kind], 'device': str(item.get('device') or '')[:20],
               'customer': ' '.join(str(item.get('shop') or '').split())[:80] or '—', 'phone': '', 'days': days,
               'note': ('الدفع: ' + str(item.get('ref') or '')[:60]) if item.get('ref') else '', 'requested_by': 'shop', 'requested_at': now_iso(),
               'status': 'pending', 'source': 'relay', 'relay_id': rid, 'machine': item.get('machine') if isinstance(item.get('machine'), str) else None,
               'src': str(item.get('src') or '')[:16] or None, 'kind': kind, 'payment_ref': str(item.get('ref') or '')[:60]}
        decision = item.get('owner_decision') if item.get('owner_decision') in ('approved', 'expired') and isinstance(item.get('owner_decided_at'), int) else ''
        if decision:
            row.update(tg_decision=decision, tg_at=item['owner_decided_at'])
        cols = ','.join(row)
        with s.lock:
            s.db.execute(f'INSERT INTO requests({cols}) VALUES ({",".join("?" * len(row))})', list(row.values()))
        s.audit('shop', 'request.relay', {'id': row['id'], 'relay': rid[:8], 'kind': kind, 'device': row['device'], 'machine': (row['machine'] or '')[:8]})
        if decision == 'approved':  # the owner pressed «✅ موافق» while this program was away
            s.audit('telegram', 'request.owner_pressed_approve', {'id': row['id'], 'relay': rid[:8]})
        return s.one('SELECT * FROM requests WHERE id = ?', row['id'])

    def note_decision(self, known: dict, item: dict):
        """The owner's «✅ موافق» arrived after the request was first pulled, or the relay says it is too old now. Audited once, when it changes.
        An expired approval stays expired (the relay still lists the press)."""
        s = self.s
        decision = item.get('owner_decision')
        at = item.get('owner_decided_at') if isinstance(item.get('owner_decided_at'), int) else None
        if decision == 'approved' and known['tg_decision'] == '':
            with s.lock:
                done = s.db.execute("UPDATE requests SET tg_decision = 'approved', tg_at = ? WHERE id = ? AND status = 'pending' AND tg_decision = ''", (at, known['id'])).rowcount
            if done:
                s.audit('telegram', 'request.owner_pressed_approve', {'id': known['id'], 'relay': str(item.get('id'))[:8]})
        elif decision == 'expired' and known['tg_decision'] in ('', 'approved'):
            with s.lock:
                done = s.db.execute("UPDATE requests SET tg_decision = 'expired', tg_at = ? WHERE id = ? AND status = 'pending' AND tg_decision IN ('', 'approved')", (at, known['id'])).rowcount
            if done:
                s.audit('studio', 'request.approval_expired', {'id': known['id']})
                self.tell('approval_old', known['id'], '⌛ موافقتك على طلب تجربة بقالها وقت طويل ومابقتش تنفع: وافق من برنامج التراخيص بنفسك.')

    def tell(self, key: str, rid: str, text: str):
        """One Telegram message per request and event (a retry loop never repeats it)."""
        if (key, rid) in self._told:
            return
        self._told.add((key, rid))
        telegram(text, private=False)  # an alert: kind, device, reason; never a code

    def deliver(self, r: dict) -> bool:
        """Hand a decided relay request's outcome back through the relay. A failure leaves it for the next cycle."""
        with self._deliver_lock:
            return self._deliver(r)

    def _deliver(self, r: dict) -> bool:
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
                s.audit(r['decided_by'] or 'owner', 'request.undeliverable', {'id': r['id'], 'status': e.status})
                self.tell('undeliverable', r['id'], f'⚠️ قرارك على طلب الجهاز {r["device"]} مااتبعتش: الطلب اتقفل عند الوسيط. ابعت الكود للمحل يدوي.')
            self.last.update(ok=False, error=e.key)
            return False
        with s.lock:
            s.db.execute('UPDATE requests SET relayed = 1 WHERE id = ?', (r['id'],))
        s.audit(r['decided_by'] or 'owner', 'request.delivered', {'id': r['id'], 'status': r['status']})
        self.last['delivered'] += 1
        return True

    # ------------------------------------------------------------------ one round
    def cycle(self) -> dict:
        """Pull, follow the owner's buttons, decide by policy, deliver, send the owner a copy. Safe to run again at any time; one round at a time."""
        if not self.lock.acquire(blocking=False):
            return {**self.last, 'busy': True}
        try:
            s = self.s
            self.last = {'at': now_iso(), 'ok': True, 'error': '', 'pulled': 0, 'issued': 0, 'refused': 0, 'held': 0, 'delivered': 0}
            s._recover_deciding()  # a decision left half-done by a studio that died (and not one being taken right now)
            if not s.relay.configured():
                self.last.update(ok=None, error='relay.off')
                return dict(self.last)
            try:
                seen = set()
                for item in s.relay.pending_all():
                    seen.add(item.get('id'))
                    if self.ingest(item):
                        self.last['pulled'] += 1
            except RelayError as e:
                self.last.update(ok=False, error=e.key)
                return dict(self.last)
            try:
                self.sync_closed(seen)
            except RelayError as e:  # an older relay without /licence/states, or a hiccup: everything else in this round still runs
                self.last.update(error='sync.' + e.key)
            # 1. the owner's own «✅ موافق»: it stands in for the policy for that one request (even when the policy is off)
            for r in s.rows("SELECT * FROM requests WHERE source = 'relay' AND status = 'pending' AND tg_decision = 'approved' AND kind = 'trial' AND held != 'relay_gone' ORDER BY requested_at"):
                self.decide_auto(r, BUTTON)   # (a paid kind is never signed by a button: it waits for the payment proof in this program)
            # 2. the policy the owner switched on, for the rest
            pol = s.policy()
            if pol['auto_trials']:
                for r in s.rows("SELECT * FROM requests WHERE source = 'relay' AND status = 'pending' AND NOT (kind = 'trial' AND tg_decision = 'approved') AND held != 'relay_gone' ORDER BY requested_at"):
                    self.decide_auto(r, 'auto-trial')   # (a trial the owner approved on the phone was handled above: this loop must not hold or re-word it)
            for r in s.rows("SELECT * FROM requests WHERE source = 'relay' AND status IN ('approved', 'refused') AND relayed = 0 ORDER BY requested_at"):
                self.deliver(r)
            self.send_copies()
            return dict(self.last)
        finally:
            self.lock.release()

    def sync_closed(self, seen: set):
        """Requests this program still holds as waiting but the relay no longer lists: the owner pressed «❌ رفض» on Telegram, the request
        timed out, or it was replaced. Ask the relay what happened and close them here too, so a later click cannot sign for a closed request."""
        s = self.s
        ours = [r for r in s.rows("SELECT id, relay_id, kind, device, requested_at FROM requests WHERE source = 'relay' AND status = 'pending'") if r['relay_id'] not in seen]
        if not ours:
            return
        states = s.relay.states([r['relay_id'] for r in ours])
        for r in ours:
            st = states.get(r['relay_id'])
            if st is None:
                self.relay_gone(r)
            else:
                self.close_from_relay(r, st)

    def close_from_relay(self, r: dict, st: dict) -> bool:
        """Close a waiting request here because the relay says it is no longer waiting. Returns True when it was closed."""
        s = self.s
        if st.get('status') == 'pending':
            with s.lock:  # still waiting on the relay (it just fell outside the page we read): a «gone» mark from an outage is wrong now
                s.db.execute("UPDATE requests SET held = '' WHERE id = ? AND status = 'pending' AND held = 'relay_gone'", (r['id'],))
            return False
        by = 'telegram' if st.get('owner_decision') == 'denied' else 'relay'
        reason = 'owner_refused' if by == 'telegram' else ('expired' if st.get('status') == 'expired' else 'closed_elsewhere')
        with s.lock:
            done = s.db.execute("UPDATE requests SET status = 'refused', decided_at = ?, decided_by = ?, held = ?, relayed = 2 WHERE id = ? AND status = 'pending'",
                                (now_iso(), by, reason, r['id'])).rowcount
        if done:
            s.audit(by, 'request.refuse', {'id': r['id'], 'reason': reason, 'closed_on_relay': True})
            self.last['refused'] += 1
        return bool(done)

    def relay_gone(self, r: dict):
        """The relay does not know this waiting request at all (a different relay was set up, or its record is gone). That is not «refused» or
        «expired»: the request is kept for the owner, marked, and no automatic round signs it, until the relay lists it again or it is old
        enough that no shop is still waiting (then it is closed as expired)."""
        s = self.s
        age = time.time() - (self._epoch(r.get('requested_at')) or time.time())
        if age > RELAY_FORGETS:
            self.close_from_relay(r, {'status': 'expired'})
            return
        with s.lock:
            marked = s.db.execute("UPDATE requests SET held = 'relay_gone' WHERE id = ? AND status = 'pending' AND held != 'relay_gone'", (r['id'],)).rowcount  # (the other reasons are worked out again once the relay lists it)
        if marked:
            s.audit('studio', 'request.relay_gone', {'id': r['id']})
            self.last['held'] += 1

    @staticmethod
    def _epoch(stamp) -> float | None:
        try:
            return calendar.timegm(time.strptime(stamp, '%Y-%m-%dT%H:%M:%SZ'))  # a UTC stamp read as UTC, whatever this PC's clock zone and summer time are
        except (TypeError, ValueError):
            return None

    def relay_state(self, r: dict) -> str:
        """Before signing: 'closed' (the relay closed it, so it is closed here too), 'gone' (the relay does not know it) or 'open'."""
        st = self.s.relay.states([r['relay_id']], timeout=CHECK_SECONDS).get(r['relay_id'])
        if st is None:
            return 'gone'
        return 'closed' if self.close_from_relay(r, st) else 'open'

    def refresh_one(self, r: dict) -> bool:
        """Before the owner signs for a relay request in this program: has the relay closed it meanwhile (a «❌ رفض» on the phone)?
        A request the relay does not know is not «closed»: the owner decides, and delivery reports what the relay says."""
        return self.relay_state(r) == 'closed'

    def decide_auto(self, r: dict, by: str):
        """Decide one waiting request without the owner at the keyboard: `by` is 'auto-trial' (the owner's policy) or 'telegram' (the owner's
        own «✅ موافق» for this request). Everything that can refuse or hold a request still does."""
        s = self.s
        approved = by == BUTTON
        kind, reason, existing = self.verdict(r, approved=approved)
        if kind == 'refuse':
            self._close(r, 'refused', reason, by)
            self.last['refused'] += 1
            self.tell('refused', r['id'], f'⛔ طلب {KIND_AR[r["kind"]]} اترفض\nالجهاز: {r["device"]}\nالسبب: {REASON_AR.get(reason, reason)}')
            return
        if kind == 'hold':
            if r['held'] != reason:
                with s.lock:
                    s.db.execute('UPDATE requests SET held = ? WHERE id = ?', (reason, r['id']))
                self.last['held'] += 1
                if reason != 'payment_needed':  # paid requests were already announced by the relay, which also tells the owner what is still missing
                    self.tell('held:' + reason, r['id'], f'⏳ طلب {KIND_AR[r["kind"]]} مستني قرارك\nالجهاز: {r["device"]}\nالسبب: {REASON_AR.get(reason, reason)}')
            return
        if not s.unlocked():  # the owner said yes (or the policy allows it), but the key is locked: wait, and say so once
            if r['held'] != 'locked':
                with s.lock:
                    s.db.execute("UPDATE requests SET held = 'locked' WHERE id = ?", (r['id'],))
                self.last['held'] += 1
                self.tell('locked', r['id'], f'🔒 فيه طلب تجربة {"وافقت عليه" if approved else "مستني"} والبرنامج مقفول\nالجهاز: {r["device"]}\nافتح برنامج التراخيص واكتب كلمة السر.')
            return
        try:  # the owner may have refused it on the phone since this round pulled it: ask the relay once more, right before signing
            state = self.relay_state(r)
            if state == 'closed':
                return
            if state == 'gone':  # (listed a moment ago yet unknown now: not signed on a guess; the next round looks again)
                return
        except RelayError as e:
            if e.status != 404:  # (404: a relay older than 0.14 has no such call and no buttons either: nothing to re-check)
                return  # the relay cannot confirm that the request is still open: do not sign now, the next round tries again
        token = s.claim(r['id'])
        if not token:  # the owner decided it a moment ago
            return
        try:
            if kind == 'reissue':
                serial = existing['serial']
            else:
                # a button is the owner's decision on THIS request, which asked for (and the alert offered) the standard 14-day trial;
                # the shorter term the owner may have set for the automatic policy applies to the policy only
                pol = s.policy()  # read once: the length and the cap come from one snapshot
                code = s.issue(r['product'], 'trial', r['device'], r['customer'], '', TRIAL_DAYS if approved else pol['auto_trial_days'],
                               note='تجربة بموافقتك على تليجرام' if approved else 'تجربة تلقائية بسياسة المالك',
                               actor=by, request_id=r['id'], machine=r['machine'], claim=token,
                               daily_cap=None if approved else pol['auto_trial_daily_cap'])  # (the owner's own «✅» is not held back by the cap)
                serial = code['serial']
        except StudioError as e:
            s.release(r['id'], token)
            if e.key in ('key.locked', 'request.closed'):  # (closed: this decision was taken over by another window: that one stands)
                return
            if e.key == 'daily_cap':  # two rounds or windows passed the first look together: the one that lost waits for tomorrow, it is not refused
                self.last['held'] += 1
                return
            self._close(r, 'refused', 'already_used' if e.key == 'trial.repeat' else 'bad_device', by)
            self.last['refused'] += 1
            return
        with s.lock:
            saved = s.db.execute("UPDATE requests SET status = 'approved', decided_at = ?, decided_by = ?, serial = ?, held = '' WHERE id = ? AND status = 'deciding' "
                                 "AND decide_claim = ?", (now_iso(), by, serial, r['id'], token)).rowcount
        if not saved:
            return
        s.audit(by, 'request.approve', {'id': r['id'], 'serial': serial, 'reissued': kind == 'reissue'})
        self.last['issued'] += 1
        self.deliver(r)

    def send_copies(self):
        """The owner's phone gets the signed code of every shop request, so a shop that is offline can be told it by phone and type it in
        (the manual way). Only to the owner's own chat (TELEGRAM_OWNER_CHAT_ID); never logged, never in the audit. Once per request: the
        flag is saved only after Telegram accepted the message, so a failed send is repeated next round."""
        s = self.s
        if not telegram_configured():
            return
        stale = int(time.time()) - CLAIM_SECONDS  # a claim older than this was left by a send that died (PC shut down): it is taken again
        cutoff = time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(time.time() - COPY_WINDOW))
        old = "source = 'relay' AND status = 'approved' AND decided_at IS NOT NULL AND decided_at != '' AND decided_at < ? AND (code_sent = 0 OR (code_sent = 2 AND COALESCE(code_claim, 0) < ?))"
        waiting = s.one(f'SELECT COUNT(*) AS n FROM requests WHERE {old}', cutoff, stale)['n']  # (never one being sent right now, never a row with no date)
        if waiting and telegram(f'⚠️ فيه {waiting} كود اتصدّر من أكتر من يومين ومااتبعتش لك نسخة منه على تليجرام. ماتبعتش القديم: هتلاقيه في برنامج التراخيص.', private=False):
            # the owner is told first, and only then are they settled (3 = skipped): a Telegram that was down for two days never swallows them silently
            with s.lock:
                skipped = s.db.execute(f'UPDATE requests SET code_sent = 3 WHERE {old}', (cutoff, stale)).rowcount
            if skipped:
                s.audit('studio', 'request.copy_skipped', {'count': skipped})
        for r in s.rows("SELECT * FROM requests WHERE source = 'relay' AND status = 'approved' AND (code_sent = 0 OR (code_sent = 2 AND COALESCE(code_claim, 0) < ?)) "
                        "ORDER BY requested_at", stale):
            row = s.one('SELECT code, serial FROM codes WHERE serial = ?', r['serial'])
            if not row:
                continue
            with s.lock:  # one sender per request: the round and the owner's own click can both get here at once
                claimed = s.db.execute('UPDATE requests SET code_sent = 2, code_claim = ? WHERE id = ? AND (code_sent = 0 OR (code_sent = 2 AND COALESCE(code_claim, 0) < ?))',
                                       (int(time.time()), r['id'], stale)).rowcount == 1
            if not claimed:
                continue
            ok = telegram(f'✅ اتصدّر {html_escape(KIND_AR[r["kind"]])}\nالجهاز: {html_escape(r["device"] or "")}\nرقم الكود: {html_escape(row["serial"])}\n'
                          f'لو المحل معاه نت هيتفعّل لوحده. لو لأ، ابعت له الكود ده يكتبه في شاشة التفعيل:\n<code>{html_escape(row["code"])}</code>', html=True, private=True)
            with s.lock:
                s.db.execute('UPDATE requests SET code_sent = ? WHERE id = ?', (1 if ok else 0, r['id']))
            if ok:
                s.audit('studio', 'request.copy_to_owner', {'id': r['id'], 'serial': row['serial']})
            else:
                break  # Telegram cannot be reached: one try per round, not one slow try per request

    def _close(self, r: dict, status: str, reason: str, by: str = 'auto-trial'):
        s = self.s
        with s.lock:
            s.db.execute('UPDATE requests SET status = ?, decided_at = ?, decided_by = ?, held = ? WHERE id = ? AND status = ?',
                         (status, now_iso(), by, reason, r['id'], 'pending'))
        s.audit(by, 'request.refuse', {'id': r['id'], 'reason': reason})
        self.deliver(r)

    # ------------------------------------------------------------------ owner's decisions on a relay request
    def owner_decided(self, rid: str, defer: bool = False):
        """The owner approved or refused in the studio: send the outcome to the shop through the relay (best effort, retried each round).
        `defer`: from a page click, the network work (the relay, then Telegram) runs on its own thread: the decision is already saved and
        signed, and the owner's window must not wait up to a minute for a slow network."""
        if defer:
            threading.Thread(target=self._deliver_now, args=(rid,), daemon=True).start()
        else:
            self._deliver_now(rid)

    def _deliver_now(self, rid: str):
        for step in (lambda r: self.deliver(r), lambda r: self.send_copies()):
            try:  # a failure is retried by the next round, and left in the audit: it must never surface as an error in a finished decision
                r = self.s.one('SELECT * FROM requests WHERE id = ?', rid)
                if r and r['source'] == 'relay':
                    step(r)
            except Exception as e:
                self.last.update(ok=False, error='deliver.crash')
                self.s.audit('studio', 'request.deliver_crash', {'id': rid, 'error': e.__class__.__name__})

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

