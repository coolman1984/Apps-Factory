"""The owner's two buttons on Telegram, end to end over real HTTP: the shop asks, the real relay Worker alerts the owner with «✅ موافق» /
«❌ رفض», the owner presses one (a webhook update with the secret Telegram sends back), the studio on the owner's PC follows it, signs for
THAT request only, hands the code back through the relay, and sends the owner's phone a copy. Every wrong press changes nothing.
Skipped without Node 22.13+."""
import json
import os
import sys
import threading
import time
import unittest
import urllib.request
import uuid
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import test_relay_chain as rc  # noqa: E402
from test_relay_chain import ADMIN, PASS, WEBHOOK, Harness, TelegramStub, codes, machine_tag, node_ok  # noqa: E402
from licence_studio import relay as relay_mod  # noqa: E402
from licence_studio.service import StudioError  # noqa: E402


@unittest.skipUnless(node_ok(), 'Node 22.13+ (node:sqlite) is needed to run the relay Worker')
class Buttons(Harness):
    def ok(self, d):
        return f"ok:{d['id']}"

    def no(self, d):
        return f"no:{d['id']}"

    def copies(self):
        """Messages the STUDIO sent to the owner's phone that carry a code."""
        return [m for m in TelegramStub.messages if '<code>' in m['text']]

    # ---- the whole journey
    def test_approve_on_the_phone_signs_on_the_owners_pc_and_the_shop_switches_on(self):
        device, st, d = self.ask()
        self.assertEqual(st, 202)
        # the alert on the owner's phone has the two buttons (data: action + request id only)
        alert = [c for c in self.relay_calls() if c['method'] == 'sendMessage'][0]['body']
        self.assertEqual([b['callback_data'] for b in alert['reply_markup']['inline_keyboard'][0]], [self.ok(d), self.no(d)])
        # the policy is OFF (the default): nothing is signed by itself
        self.s.auto.cycle()
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        self.assertEqual(self.status(d)['status'], 'pending')
        # the owner presses «✅ موافق»
        self.assertEqual(self.press(self.ok(d)), 200)
        self.assertEqual(self.status(d), {'status': 'pending', 'reason': '', 'stage': 'approved', 'server_time': self.status(d)['server_time']})
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0, 'the button alone signs nothing: the studio does, on its own PC')
        before_unlock = self.s._unlocked_at
        out = self.s.auto.cycle()
        self.assertEqual((out['issued'], out['delivered']), (1, 1), out)
        self.assertEqual(self.s._unlocked_at, before_unlock, 'signing for a button press does not count as the owner being at the PC')
        got = self.status(d)
        self.assertEqual(got['status'], 'issued')
        # the shop checks the code itself, with the public key and its own device code
        read = codes.read_code(got['code'], [self.public], 'al-store', device)
        self.assertEqual((read.valid, read.terms['edition'], read.terms['days_left']), (True, 'trial', 14))
        self.assertFalse(codes.read_code(got['code'], [self.public], 'al-store', codes.device_code('other-pc', 'x')).valid)
        self.assertEqual(self.shop('POST', '/licence/ack', {'id': d['id']}, token=d['poll_token'])[1]['status'], 'delivered')
        # the owner's phone has a copy, in the owner's own chat only, for the manual way
        [copy] = self.copies()
        self.assertIn(got['code'], copy['text'])
        self.assertEqual((copy['chat_id'], copy['parse_mode']), ('7', 'HTML'))
        # who signed, in the append-only audit; no code, no secret in it
        log = self.s.audit_log()
        by = {(r['action'], r['actor']) for r in log}
        for pair in (('request.owner_pressed_approve', 'telegram'), ('code.issue', 'telegram'), ('request.approve', 'telegram'),
                     ('request.delivered', 'telegram'), ('request.copy_to_owner', 'studio')):
            self.assertIn(pair, by)
        blob = json.dumps(log) + json.dumps(self.s.requests(status=''))
        for secret in (got['code'], PASS, ADMIN, WEBHOOK, 'STUDIO-BOT-SECRET', d['poll_token']):
            self.assertNotIn(secret, blob)
        # nothing twice: another round, another press, a second copy
        self.press(self.ok(d))
        out = self.s.auto.cycle()
        self.assertEqual((out['pulled'], out['issued']), (0, 0))
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 1)
        self.assertEqual(len(self.copies()), 1, 'one copy per request')
        self.assertEqual(self.s.one('SELECT issued_by FROM codes')['issued_by'], 'telegram')

    def test_approved_but_the_key_is_locked_waits_says_so_once_and_signs_after_the_unlock(self):
        _, _, d = self.ask()
        self.s.auto.cycle()
        self.press(self.ok(d))
        self.s.lock_key()
        out = self.s.auto.cycle()
        self.assertEqual((out['issued'], out['held']), (0, 1))
        self.assertEqual(self.s.requests()[0]['held'], 'locked')
        self.s.auto.cycle()
        self.assertEqual(len([m for m in self.messages() if '🔒' in m and 'وافقت' in m]), 1, 'one message, not one per round')
        self.assertEqual(self.status(d)['stage'], 'approved', 'the shop is told the company agreed, honestly not that it is active')
        self.s.unlock(PASS)
        self.assertEqual(self.s.auto.cycle()['issued'], 1)
        self.assertEqual(self.status(d)['status'], 'issued')

    def test_the_owners_refuse_closes_it_everywhere_and_nothing_is_ever_signed(self):
        _, _, d = self.ask()
        self.s.auto.cycle()                       # the studio already holds it as waiting
        self.assertEqual(self.press(self.no(d)), 200)
        self.assertEqual((self.status(d)['status'], self.status(d)['reason']), ('refused', 'owner_refused'), 'the shop sees it at once')
        out = self.s.auto.cycle()
        self.assertEqual((out['refused'], out['issued']), (1, 0))
        [req] = self.s.requests(status='')
        self.assertEqual((req['status'], req['decided_by'], req['held']), ('refused', 'telegram', 'owner_refused'))
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        # a late «موافق», or the owner's click in the studio, cannot bring it back
        self.press(self.ok(d))
        self.s.auto.cycle()
        self.assertEqual(self.status(d)['status'], 'refused')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        with self.assertRaises(StudioError) as e:
            self.s.decide(req['id'], True)
        self.assertEqual(e.exception.key, 'request.closed')

    def test_a_refuse_pressed_while_the_studio_page_was_open_is_caught_before_signing(self):
        _, _, d = self.ask()
        self.s.auto.cycle()
        rid = self.s.requests()[0]['id']
        self.press(self.no(d))                    # the studio has not looked again yet
        with self.assertRaises(StudioError) as e:
            self.s.decide(rid, True)
        self.assertEqual(e.exception.key, 'request.closed')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0, 'no code was made for a request the owner refused')
        self.assertEqual(self.s.one('SELECT status, decided_by FROM requests')['decided_by'], 'telegram')

    def test_withdrawing_an_approval_works_until_the_code_is_signed_and_not_after(self):
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.press(self.no(d))                    # «سحب الموافقة»
        self.assertEqual(self.s.auto.cycle()['issued'], 0)
        self.assertEqual(self.status(d)['status'], 'refused')
        _, _, d2 = self.ask(pc='pc-2', install='i2')
        self.press(self.ok(d2))
        self.s.auto.cycle()
        self.assertEqual(self.status(d2)['status'], 'issued')
        self.press(self.no(d2))                   # too late: a code may already be on the shop's PC
        self.assertEqual(self.status(d2)['status'], 'issued')
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM codes WHERE device = ?", codes.device_code('pc-2', 'i2'))['n'], 1)

    def test_paid_kinds_need_the_owners_button_and_the_money_never_the_button_alone(self):
        device, _, d = self.ask(kind='monthly')
        self.press(self.ok(d))
        self.s.auto.cycle()
        [req] = self.s.requests()
        self.assertEqual((req['status'], req['tg_decision'], req['policy']), ('pending', 'approved', {'verdict': 'hold', 'reason': 'payment_needed'}))
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0, 'no code from a button for a paid kind')
        self.assertEqual(self.status(d)['status'], 'pending')
        with self.assertRaises(StudioError) as e:
            self.s.decide(req['id'], True)        # approved on the phone, but no proof of payment
        self.assertEqual(e.exception.key, 'payment.required')
        self.s.decide(req['id'], True, payment_confirmed=True, payment_ref='InstaPay 7788')
        read = codes.read_code(self.status(d)['code'], [self.public], 'al-store', device)
        self.assertEqual((read.terms['edition'], read.valid), ('standard', True))
        self.assertEqual(len(self.copies()), 1, 'the owner is sent a copy of a paid code too')
        # a permanent code, with the button pressed by someone else: nothing
        _, _, p = self.ask(pc='pc-9', install='i9', kind='permanent')
        self.assertEqual(self.press(self.ok(p), sender=999, chat=999), 200)
        self.s.auto.cycle()
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 1)

    def test_a_press_by_anyone_else_or_without_the_secret_never_reaches_the_studio(self):
        _, _, d = self.ask()
        for kw in ({'sender': 999}, {'chat': -1001}, {'sender': 999, 'chat': 999}, {'secret': 'guess'}, {'secret': ''}):
            self.press(self.ok(d), **kw)
        out = self.s.auto.cycle()
        self.assertEqual((out['pulled'], out['issued']), (1, 0))
        [req] = self.s.requests()
        self.assertEqual((req['tg_decision'], req['status']), ('', 'pending'))
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        self.assertEqual(self.status(d)['status'], 'pending')

    def test_an_approval_is_not_a_way_around_the_hard_rules(self):
        # a PC that already had its trial: the studio's permanent ledger refuses even with the owner's «موافق»
        self.s.set_setting('auto_trials', True)
        _, _, first = self.ask(pc='pc-1', install='i1')
        self.s.auto.cycle()
        self.shop('POST', '/licence/ack', {'id': first['id']}, token=first['poll_token'])
        item = {'id': str(uuid.uuid4()), 'product': 'al-store', 'kind': 'trial', 'device': codes.device_code('pc-1', 'i-new'),
                'machine': machine_tag('pc-1'), 'shop': 'x', 'ref': '', 'src': 'a' * 16, 'owner_decision': 'approved', 'owner_decided_at': int(time.time())}
        row = self.s.auto.ingest(item)
        self.assertEqual(row['tg_decision'], 'approved')
        self.assertEqual(self.s.auto.verdict(row, approved=True)[:2], ('refuse', 'already_used'))
        # a malformed device or PC tag is refused too
        bad = self.s.auto.ingest({**item, 'id': str(uuid.uuid4()), 'device': 'nope', 'machine': machine_tag('pc-5')})
        self.assertEqual(self.s.auto.verdict(bad, approved=True)[:2], ('refuse', 'bad_device'))

    def test_the_owners_button_beats_the_daily_cap_that_only_the_policy_obeys(self):
        self.s.set_setting('auto_trials', True)
        self.s.set_setting('auto_trial_daily_cap', 1)
        ds = [self.ask(pc=f'pc-{i}', install=f'i-{i}')[2] for i in range(3)]
        self.s.auto.cycle()
        self.assertEqual([self.status(d)['status'] for d in ds].count('issued'), 1, 'the policy stops at its cap')
        pending = [d for d in ds if self.status(d)['status'] == 'pending']
        self.press(self.ok(pending[0]))
        self.s.auto.cycle()
        self.assertEqual([self.status(d)['status'] for d in ds].count('issued'), 2, 'the owner chose this one by hand')
        self.assertEqual(self.status(pending[1])['status'], 'pending')

    def test_an_old_approval_is_not_acted_on_the_relay_says_so_and_the_owner_is_told(self):
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.lock_key()                          # the owner is away: the studio pulls the request with its approval and waits
        self.s.auto.cycle()
        self.assertEqual(self.s.requests()[0]['tg_decision'], 'approved')
        self.relay_clock_ahead(73 * 3600)          # ... and by the time the owner is back the approval is three days old (the RELAY's clock decides)
        self.s.unlock(PASS)
        out = self.s.auto.cycle()
        self.assertEqual(out['issued'], 0)
        [req] = self.s.requests()
        self.assertEqual((req['tg_decision'], req['status']), ('expired', 'pending'), 'the request itself is untouched')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0)
        self.assertEqual(len([m for m in self.messages() if '⌛' in m]), 1)
        self.s.auto.cycle()
        self.assertEqual(len([m for m in self.messages() if '⌛' in m]), 1, 'told once')
        self.assertEqual(self.s.requests()[0]['tg_decision'], 'expired', 'and it stays expired although the relay still lists the press')
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM audit WHERE action = 'request.approval_expired'")['n'], 1, 'audited once, not every round')
        self.assertEqual(self.status(d)['status'], 'pending')
        self.s.decide(self.s.requests()[0]['id'], True)
        self.assertEqual(self.status(d)['status'], 'issued', 'the owner can still approve it by hand')

    def test_a_studio_killed_between_signing_and_saving_the_decision_puts_it_right_on_restart(self):
        """Found by asking «what if the PC is switched off in every step»: the request stayed in `deciding` for ever (not waiting, not decided, never
        delivered) and the shop never got its code."""
        from licence_studio.service import Studio
        device, _, d = self.ask()
        self.press(self.ok(d))
        out = self.s.relay.pending_all()
        self.s.auto.ingest(out[0])
        [req] = self.s.requests()
        self.assertTrue(self.s.claim(req['id']))                      # the owner's PC took the request ...
        code = self.s.issue('al-store', 'trial', req['device'], req['customer'], '', 14, actor='telegram', request_id=req['id'], machine=req['machine'])
        self.assertEqual(self.s.one('SELECT status FROM requests')['status'], 'deciding')   # ... signed ... and was switched off before saving
        self.s.db.execute('UPDATE requests SET decide_claim = ?', (time.time_ns() - 600 * 10**9,))  # (some minutes ago: a decision younger than the lease is a live one)
        self.s.db.close()
        again = Studio(self.dir)                                       # the owner starts the studio again
        try:
            again.unlock(PASS)
            again.relay.save(self.base, ADMIN)
            row = again.one('SELECT status, serial, decided_by FROM requests')
            self.assertEqual((row['status'], row['serial']), ('approved', code['serial']))
            self.assertIn('request.recovered', [a['action'] for a in again.audit_log()])
            self.assertEqual(again.auto.cycle()['delivered'], 1)
            self.assertEqual(self.status(d)['status'], 'issued', 'the shop gets the code it was signed')
            self.assertEqual(again.one('SELECT COUNT(*) AS n FROM codes')['n'], 1, 'no second code was made')
        finally:
            again.db.close()
        # a request taken but not yet signed simply waits again
        self.s = Studio(self.dir)
        self.s.unlock(PASS)
        self.s.relay.save(self.base, ADMIN)
        device2, _, d2 = self.ask(pc='pc-2', install='i2')
        self.s.auto.ingest(self.s.relay.pending_all()[0])
        rid = self.s.one("SELECT id FROM requests WHERE status = 'pending'")['id']
        self.assertTrue(self.s.claim(rid))
        self.s.db.execute('UPDATE requests SET decide_claim = ?', (time.time_ns() - 600 * 10**9,))
        self.s.db.close()
        self.s = Studio(self.dir)
        self.assertEqual(self.s.one('SELECT status FROM requests WHERE id = ?', rid)['status'], 'pending')

    def test_a_paid_approval_cut_off_after_signing_keeps_the_payment_the_owner_confirmed(self):
        """Review of PR #40: the owner's «the money arrived» and its reference were saved only after signing, so a studio switched off in between
        recovered the request as approved, delivered the paid code, and the record said the payment was never confirmed."""
        from licence_studio.service import Studio
        device, _, d = self.ask(kind='monthly')
        self.s.auto.cycle()
        [req] = self.s.requests()
        self.assertTrue(self.s.claim(req['id'], 'InstaPay 5521 / 350 EGP'))            # the owner ticked «arrived» and wrote the reference ...
        code = self.s.issue('al-store', req['edition'], req['device'], req['customer'], '', 30, grace_days=3, actor='owner', request_id=req['id'])
        self.s.db.execute('UPDATE requests SET decide_claim = ?', (time.time_ns() - 600 * 10**9,))   # ... signed ... and the PC died some minutes ago
        self.s.db.close()
        again = Studio(self.dir)
        try:
            row = again.one('SELECT * FROM requests')
            self.assertEqual((row['status'], row['serial'], row['payment_confirmed'], row['payment_ref'], row['decided_by']),
                             ('approved', code['serial'], 1, 'InstaPay 5521 / 350 EGP', 'owner'))
            [seen] = [a for a in again.audit_log() if a['action'] == 'request.recovered']
            self.assertIn('InstaPay 5521', seen['detail'], 'the audit keeps the reference too')
            # taken with a payment but never signed: it waits again and the payment has to be confirmed again
            device2, _, d2 = self.ask(pc='pc-2', install='i2', kind='monthly')
            again.relay.save(self.base, ADMIN)
            again.auto.cycle()
            rid = [r for r in again.requests() if r['status'] == 'pending'][0]['id']
            self.assertTrue(again.claim(rid, 'InstaPay 9'))
            again.db.execute('UPDATE requests SET decide_claim = ? WHERE id = ?', (time.time_ns() - 600 * 10**9, rid))
            again._recover_deciding()
            row2 = again.one('SELECT status, payment_confirmed FROM requests WHERE id = ?', rid)
            self.assertEqual((row2['status'], row2['payment_confirmed']), ('pending', 0))
            with self.assertRaises(StudioError):
                again.decide(rid, True)
        finally:
            again.db.close()
            self.s = Studio(self.dir)

    def test_a_second_window_on_the_same_folder_leaves_a_decision_being_made_alone(self):
        """Review of PR #40: every `deciding` request was taken for crash residue when a studio opened, so another window (a second `serve`, a
        command on the same folder) reset one that was being signed right then."""
        from licence_studio.service import Studio
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.ingest(self.s.relay.pending_all()[0])
        [req] = self.s.requests()
        self.assertTrue(self.s.claim(req['id']))                      # window one is deciding it right now
        other = Studio(self.dir)                                       # window two opens on the same folder
        try:
            other._recover_deciding()
            self.assertEqual(other.one('SELECT status FROM requests')['status'], 'deciding', 'a live decision is not touched')
            self.assertFalse(other.claim(req['id']), 'and cannot be taken a second time')
        finally:
            other.db.close()

    def _taken_over(self):
        """A window takes a request, goes to sleep for ten minutes (a closed laptop), and another window takes it back."""
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.ingest(self.s.relay.pending_all()[0])
        row = self.s.one('SELECT * FROM requests')
        self.assertTrue(self.s.claim(row['id']))
        token = time.time_ns() - 600 * 10**9                          # (the token is the moment of the claim: ten minutes have passed since)
        self.s.db.execute('UPDATE requests SET decide_claim = ?', (token,))
        return row, token

    def test_a_window_that_slept_past_the_lease_cannot_overwrite_the_decision_that_replaced_it(self):
        """Review of PR #40: the lease had a timestamp but no fencing token, so the window that woke up saved its approval over the owner's
        refusal (and signed a code for a refused request)."""
        row, token = self._taken_over()
        self.s._recover_deciding()                                    # the other window takes it back ...
        self.s.decide(row['id'], False)                               # ... and the owner refuses it
        with self.assertRaises(StudioError) as e:                     # the first window wakes up and goes on with its approval
            self.s._decide_claimed(row, True, 'owner', True, False, '', token)
        self.assertEqual(e.exception.key, 'request.closed')
        now = self.s.one('SELECT status, serial FROM requests')
        self.assertEqual((now['status'], now['serial']), ('refused', None), 'the refusal stands')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0, 'and no code was signed for a refused request')
        self.s.release(row['id'], token)                              # its release cannot reopen anything either
        self.assertEqual(self.s.one('SELECT status FROM requests')['status'], 'refused')

    def test_a_window_that_wakes_up_after_signing_cannot_replace_the_recovery_that_approved_with_its_code(self):
        row, token = self._taken_over()
        code = self.s.issue('al-store', 'trial', row['device'], row['customer'], '', 14, actor='owner', request_id=row['id'], machine=row['machine'], claim=token)
        self.s._recover_deciding()                                    # signed, then asleep: the recovery approves it with that code
        self.assertEqual(self.s.one('SELECT status, serial FROM requests')['serial'], code['serial'])
        with self.assertRaises(StudioError) as e:                     # it wakes up and tries to save its own decision
            self.s._decide_claimed(row, True, 'owner', True, False, '', token)
        self.assertEqual(e.exception.key, 'request.closed')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 1)
        self.assertEqual(self.s.one('SELECT status FROM requests')['status'], 'approved')

    def test_a_code_signed_while_the_recovery_was_looking_is_never_left_on_a_reopened_request(self):
        """Review of PR #40: the recovery looked for a code, found none, and reopened the request in a second step; a stale window finishing its signing in
        between left a valid code on a request the next decision could refuse."""
        row, token = self._taken_over()
        real, done = self.s.one, []

        def late(sql, *a):
            out = real(sql, *a)
            if 'FROM codes WHERE request_id' in sql and out is None and not done:
                done.append(1)   # the sleeping window wakes up and finishes signing right after the recovery looked
                self.s.issue('al-store', 'trial', row['device'], row['customer'], '', 14, actor='owner', request_id=row['id'], machine=row['machine'], claim=token)
            return out
        self.s.one = late
        try:
            self.s._recover_deciding()
        finally:
            self.s.one = real
        self.assertEqual(done, [1])
        self.assertEqual(self.s.one('SELECT status FROM requests')['status'], 'deciding', 'not reopened: a code exists for it')
        self.s._recover_deciding()                                    # the next pass sees the code and approves with it
        now = self.s.one('SELECT status, serial FROM requests')
        self.assertEqual(now['status'], 'approved')
        self.assertEqual(now['serial'], self.s.one('SELECT serial FROM codes')['serial'])
        with self.assertRaises(StudioError):
            self.s.decide(row['id'], False)

    def test_a_paid_request_left_by_the_old_version_with_a_code_and_no_saved_payment_waits_for_the_owner(self):
        """Review of PR #40: a studio upgraded with such a request in `deciding` (the old version saved the owner's payment only after signing) would
        have approved and delivered the paid code with the record saying the payment was never confirmed, and his reference is lost."""
        from licence_studio.service import Studio
        self.ask(kind='monthly')
        self.s.auto.cycle()
        [req] = self.s.requests()
        self.assertTrue(self.s.claim(req['id']))                      # the old version: taken without saving the payment ...
        code = self.s.issue('al-store', req['edition'], req['device'], req['customer'], '', 30, grace_days=3, actor='owner', request_id=req['id'])
        self.s.db.execute('UPDATE requests SET decide_claim = NULL')  # ... signed ... and switched off (an old row has no claim time)
        self.s.db.close()
        again = Studio(self.dir)                                       # the upgraded studio starts
        try:
            row = again.one('SELECT status, serial, payment_confirmed FROM requests')
            self.assertEqual((row['status'], row['payment_confirmed']), ('pending', 0), 'not approved on its own')
            self.assertEqual(again.one('SELECT COUNT(*) AS n FROM codes')['n'], 1)
            [seen] = [a for a in again.audit_log() if a['action'] == 'request.recovered']
            self.assertIn('confirm again', seen['detail'])
            again.relay.save(self.base, ADMIN)
            self.assertEqual(again.auto.cycle()['delivered'], 0, 'nothing is delivered before the owner confirms the payment')
            with self.assertRaises(StudioError) as e:
                again.decide(req['id'], True)
            self.assertEqual(e.exception.key, 'payment.required')
            again.decide(req['id'], True, payment_confirmed=True, payment_ref='InstaPay 5521 / 350 EGP')   # the owner confirms again
            row = again.one('SELECT status, serial, payment_confirmed, payment_ref FROM requests')
            self.assertEqual((row['status'], row['serial'], row['payment_confirmed'], row['payment_ref']), ('approved', code['serial'], 1, 'InstaPay 5521 / 350 EGP'))
            self.assertEqual(again.one('SELECT COUNT(*) AS n FROM codes')['n'], 1, 'the same code goes out, no second one')
        finally:
            again.db.close()
            self.s = Studio(self.dir)

    def test_two_windows_signing_the_same_request_make_one_code(self):
        """Review of PR #40: the check «is there a code for this request» ran before the write transaction, and `codes.request_id` is not unique, so two
        windows that passed it together signed two append-only codes for one request."""
        from licence_studio.service import Studio
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.ingest(self.s.relay.pending_all()[0])
        [req] = self.s.requests()
        other = Studio(self.dir)
        other.unlock(PASS)
        gate = threading.Barrier(2)
        real = codes.issue_code

        def slow(*a, **k):  # both windows are past the first check and have signed when either one starts to write
            out = real(*a, **k)
            gate.wait(10)
            return out
        got, bad = [], []

        def run(studio):
            try:
                got.append(studio.issue('al-store', 'trial', req['device'], req['customer'], '', 14, actor='owner', request_id=req['id'])['serial'])
            except Exception as e:  # noqa: BLE001
                bad.append(repr(e))
        codes.issue_code = slow
        try:
            threads = [threading.Thread(target=run, args=(x,)) for x in (self.s, other)]
            [t.start() for t in threads]
            [t.join(30) for t in threads]
        finally:
            codes.issue_code = real
            other.db.close()
        self.assertEqual(bad, [])
        self.assertEqual(len(set(got)), 1, 'both windows are given the same code')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes WHERE request_id = ?', req['id'])['n'], 1)

    def test_a_copy_whose_sender_died_is_sent_again_after_a_while(self):
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.cycle()
        TelegramStub.messages.clear()
        with self.s.lock:  # the studio was killed right after claiming the copy
            self.s.db.execute('UPDATE requests SET code_sent = 2, code_claim = ?', (int(time.time()),))
        self.s.auto.send_copies()
        self.assertEqual(len(self.copies()), 0, 'a fresh claim is respected: another sender may be working on it')
        with self.s.lock:
            self.s.db.execute('UPDATE requests SET code_claim = ?', (int(time.time()) - 600,))
        self.s.auto.send_copies()
        self.assertEqual(len(self.copies()), 1)
        self.assertEqual(self.s.one('SELECT code_sent FROM requests')['code_sent'], 1)

    def test_with_telegram_down_one_try_is_made_per_round_not_one_per_request(self):
        os.environ['LS_TELEGRAM_API'] = 'http://127.0.0.1:9'
        for i in range(3):
            _, _, d = self.ask(pc=f'pc-{i}', install=f'i-{i}')
            self.press(self.ok(d))
        calls = []
        real = relay_mod.telegram
        import licence_studio.autotrial as at
        at.telegram = lambda *a, **k: (calls.append(1), False)[1]
        try:
            self.s.auto.cycle()
        finally:
            at.telegram = real
        self.assertEqual(len(calls), 1, 'one failed try stops the round\'s sending')

    def test_the_copy_to_the_owner_is_retried_until_telegram_takes_it_and_never_sent_twice(self):
        os.environ['LS_TELEGRAM_API'] = 'http://127.0.0.1:9'          # nothing listens: Telegram is unreachable
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.cycle()
        self.assertEqual(self.status(d)['status'], 'issued', 'the shop is served even when the owner\'s phone cannot be reached')
        self.assertEqual(self.s.one('SELECT code_sent FROM requests')['code_sent'], 0)
        os.environ['LS_TELEGRAM_API'] = f'http://127.0.0.1:{self.tg.server_port}'
        threads = [threading.Thread(target=self.s.auto.send_copies) for _ in range(6)]   # the round and the owner's click can meet
        [t.start() for t in threads]
        [t.join() for t in threads]
        self.assertEqual(len(self.copies()), 1, 'six senders, one message')
        self.assertEqual(self.s.one('SELECT code_sent FROM requests')['code_sent'], 1)
        self.s.auto.send_copies()
        self.assertEqual(len(self.copies()), 1)

    def test_a_request_the_relay_dropped_is_closed_here_too(self):
        _, _, d = self.ask()
        self.s.auto.cycle()
        with urllib.request.urlopen(urllib.request.Request(self.base + '/licence/decide', method='POST', headers={'Authorization': 'Bearer ' + ADMIN, 'Content-Type': 'application/json'},
                                                           data=json.dumps({'id': d['id'], 'action': 'refuse', 'reason': 'owner_refused'}).encode()), timeout=10):
            pass
        out = self.s.auto.cycle()                  # refused elsewhere (not by a button): closed here with its own reason
        self.assertEqual(out['refused'], 1)
        [req] = self.s.requests(status='')
        self.assertEqual((req['status'], req['decided_by']), ('refused', 'relay'))

    def test_the_policy_when_on_still_issues_and_the_owner_gets_the_copy(self):
        self.s.set_setting('auto_trials', True)
        self.s.keep_unlocked(1)
        device, _, d = self.ask()
        self.s.auto.cycle()
        [copy] = self.copies()
        self.assertIn(self.status(d)['code'], copy['text'])
        self.assertEqual(self.s.one('SELECT issued_by FROM codes')['issued_by'], 'auto-trial')

    def test_a_trial_the_owner_approved_is_not_held_or_reworded_by_the_policy_loop(self):
        self.s.set_setting('auto_trials', True)       # the policy also looks at each request every round
        self.s.set_setting('auto_trial_daily_cap', 0)  # ... and its cap is reached
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.lock_key()                              # the owner said yes, but the key is locked
        seen = []
        for _ in range(3):
            out = self.s.auto.cycle()
            seen.append((self.s.requests()[0]['held'], out['held']))
        self.assertEqual(seen, [('locked', 1), ('locked', 0), ('locked', 0)], seen)
        self.assertEqual([m for m in self.messages() if '⏳' in m], [], 'nobody says "waiting for your decision" to an owner who already decided')
        self.s.unlock(PASS)
        self.assertEqual(self.s.auto.cycle()['issued'], 1, 'and the approval still goes through, cap or no cap')

    def test_a_relay_that_cannot_answer_the_states_call_never_stops_the_round(self):
        """An older relay answers 404 to /licence/states (and has no buttons): the policy still signs. A relay in trouble (500): the round
        still runs, but nothing is signed on a guess that the request is still open."""
        self.s.set_setting('auto_trials', True)
        _, _, old = self.ask(pc='pc-old', install='i-old')
        real = self.s.relay.states

        def answers(code):
            def f(ids):
                raise relay_mod.RelayError('relay.http', f'The relay answered {code}.', code)
            return f
        try:
            self.s.relay.states = answers(500)
            out = self.s.auto.cycle()
            self.assertEqual((out['ok'], out['issued']), (True, 0))
            self.assertEqual(self.status(old)['status'], 'pending', 'it could not be confirmed open, so nothing is signed this round')
            self.s.relay.states = answers(404)
            self.assertEqual(self.s.auto.cycle()['issued'], 1, 'an older relay has nothing to confirm: the policy works as in 1.1')
        finally:
            self.s.relay.states = real
        self.assertEqual(self.status(old)['status'], 'issued')

    def test_a_refuse_between_the_pull_and_the_signature_stops_the_signature(self):
        _, _, d = self.ask()
        self.s.auto.cycle()
        self.press(self.ok(d))
        real = self.s.relay.pending_all

        def pull_then_refuse(*a, **k):
            items = real(*a, **k)
            self.press(self.no(d))                     # the owner changes their mind right after the pull
            return items
        self.s.relay.pending_all = pull_then_refuse
        try:
            out = self.s.auto.cycle()
        finally:
            self.s.relay.pending_all = real
        self.assertEqual(out['issued'], 0)
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM codes')['n'], 0, 'no code and no trial-ledger row for a request the owner refused')
        self.assertEqual(self.s.one('SELECT COUNT(*) AS n FROM trial_ledger')['n'], 0)
        self.assertEqual(self.status(d)['status'], 'refused')

    def test_the_audit_says_who_pressed_even_when_the_press_came_before_the_first_pull(self):
        _, _, d = self.ask()
        self.press(self.ok(d))                        # the studio was off
        self.s.auto.cycle()
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM audit WHERE action = 'request.owner_pressed_approve'")['n'], 1)
        # a signed request that the relay still lists (delivery keeps failing) adds nothing every round
        self.relay_proc.terminate()
        self.relay_proc.wait(10)
        for _ in range(3):
            self.s.auto.cycle()
        self.assertEqual(self.s.one("SELECT COUNT(*) AS n FROM audit WHERE action = 'request.owner_pressed_approve'")['n'], 1)

    def test_a_copy_is_only_ever_sent_to_the_owners_private_chat(self):
        os.environ['TELEGRAM_OWNER_CHAT_ID'] = '-1001234567'          # a group: every member would read the codes
        self.assertFalse(relay_mod.telegram_configured())
        self.assertFalse(relay_mod.telegram('hello'))
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.cycle()
        self.assertEqual(self.status(d)['status'], 'issued', 'the shop is served')
        self.assertEqual(TelegramStub.messages, [], 'nothing went to the group')
        self.assertEqual(self.s.one('SELECT code_sent FROM requests')['code_sent'], 0)

    def test_html_in_what_the_relay_sends_cannot_break_the_copy_to_the_owner(self):
        _, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.cycle()
        with self.s.lock:  # a hostile relay row: the device text is not a device code
            self.s.db.execute("UPDATE requests SET device = '<b>x</b>&', code_sent = 0")
        TelegramStub.messages.clear()
        self.s.auto.send_copies()
        [m] = TelegramStub.messages
        self.assertNotIn('<b>', m['text'])
        self.assertIn('&lt;b&gt;x&lt;/b&gt;&amp;', m['text'])

    # ---- setting the webhook up
    def test_a_button_always_gives_the_14_days_the_shop_asked_for_whatever_the_policy_term_is(self):
        self.s.set_setting('auto_trial_days', 3)       # the owner's automatic policy is stricter
        device, _, d = self.ask()
        self.press(self.ok(d))
        self.s.auto.cycle()
        read = codes.read_code(self.status(d)['code'], [self.public], 'al-store', device)
        self.assertEqual(read.terms['days_left'], 14)

    def test_the_command_that_sets_the_webhook_never_prints_the_secret(self):
        import io
        import contextlib
        from licence_studio.__main__ import main
        os.environ['TELEGRAM_BOT_TOKEN'] = '999:STUDIO-BOT-SECRET'
        os.environ['TELEGRAM_WEBHOOK_SECRET'] = WEBHOOK
        os.environ['LS_TELEGRAM_API'] = f'http://127.0.0.1:{self.tg.server_port}'
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                code = main(['telegram-webhook', '--url', 'https://relay.example.workers.dev', '--home', self.dir])
        finally:
            os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)
        self.assertEqual(code, 0)
        self.assertNotIn(WEBHOOK, out.getvalue())
        self.assertNotIn('STUDIO-BOT-SECRET', out.getvalue())
        self.assertIn('https://relay.example.workers.dev/telegram', out.getvalue())
        os.environ.pop('TELEGRAM_WEBHOOK_SECRET', None)
        with contextlib.redirect_stdout(io.StringIO()) as quiet:
            self.assertEqual(main(['telegram-webhook', '--url', 'https://relay.example.workers.dev', '--home', self.dir]), 2)
        self.assertNotIn(WEBHOOK, quiet.getvalue())

    def test_the_webhook_is_set_to_the_relay_with_only_the_buttons_and_a_secret(self):
        os.environ['TELEGRAM_BOT_TOKEN'] = '999:STUDIO-BOT-SECRET'
        with self.assertRaises(relay_mod.RelayError):
            relay_mod.set_webhook('http://example.com', 'x' * 30)         # Telegram only talks to https
        with self.assertRaises(relay_mod.RelayError):
            relay_mod.set_webhook('https://relay.example.workers.dev', 'short')
        with self.assertRaises(relay_mod.RelayError):
            relay_mod.set_webhook('https://relay.example.workers.dev', 'has spaces and !! ' + 'x' * 20)
        seen = []

        class Api(BaseHTTPRequestHandler):
            def do_POST(self):
                seen.append((self.path, json.loads(self.rfile.read(int(self.headers['Content-Length'])))))
                self.send_response(200)
                self.send_header('Content-Type', 'application/json')
                self.end_headers()
                self.wfile.write(b'{"ok":true,"result":true}')

            def log_message(self, *a):
                pass
        api = HTTPServer(('127.0.0.1', 0), Api)
        threading.Thread(target=api.serve_forever, daemon=True).start()
        os.environ['LS_TELEGRAM_API'] = f'http://127.0.0.1:{api.server_port}'
        try:
            out = relay_mod.set_webhook('https://relay.example.workers.dev/', WEBHOOK)
        finally:
            api.shutdown()
            api.server_close()
        self.assertTrue(out['ok'])
        [(path, body)] = seen
        self.assertEqual(path, '/bot999:STUDIO-BOT-SECRET/setWebhook')
        self.assertEqual(body['url'], 'https://relay.example.workers.dev/telegram')
        self.assertEqual(body['secret_token'], WEBHOOK)
        self.assertEqual(body['allowed_updates'], ['callback_query'], 'only button presses are wanted')
        self.assertTrue(body['drop_pending_updates'])



class Upgrade(unittest.TestCase):
    def test_an_older_studio_does_not_flood_the_owners_phone_with_old_codes(self):
        """Studio 1.1 had no `code_sent`: when 1.2 opens its database, the finished requests count as already sent."""
        import shutil
        import sqlite3
        import tempfile
        from licence_studio.service import Studio
        home = tempfile.mkdtemp()
        try:
            first = Studio(home)
            first.db.executescript(
                "ALTER TABLE requests DROP COLUMN code_sent; ALTER TABLE requests DROP COLUMN tg_at; ALTER TABLE requests DROP COLUMN tg_decision;"
                "INSERT INTO requests(id, product, edition, device, customer, phone, days, note, requested_by, requested_at, status, source, relay_id, kind) "
                "VALUES ('r1','al-store','trial','AAAAA-BBBBB','x','',14,'','shop','2026-10-01T00:00:00Z','approved','relay','11111111-1111-4111-8111-111111111111','trial');")
            first.db.close()
            again = Studio(home)
            self.assertEqual(again.one("SELECT code_sent, tg_decision FROM requests WHERE id = 'r1'"), {'code_sent': 1, 'tg_decision': ''})
            again.db.close()
            third = Studio(home)  # a second start changes nothing
            self.assertEqual(third.one("SELECT code_sent FROM requests WHERE id = 'r1'")['code_sent'], 1)
            third.db.close()
        finally:
            shutil.rmtree(home, ignore_errors=True)


if __name__ == '__main__':
    unittest.main()
