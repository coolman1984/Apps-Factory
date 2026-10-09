// Run: node --experimental-sqlite --test test/licence.test.mjs   (Node 22.13+). The licence mailbox: a shop asks, the owner's
// licensing program decides, the shop collects. D1 is the node:sqlite shim of d1.mjs; Telegram is a recording stub.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash, randomUUID} from 'node:crypto';
import {d1} from './d1.mjs';
import worker from '../src/worker.js';
import {alertText, cleanupLicence} from '../src/licence.js';

const NOW = 1_800_000_000;
const DAY = 86400;
const ADMIN = 'admin-secret-' + 'x'.repeat(20);
const DEVICE = '7KD2M-QX9TP';
const MACHINE = createHash('sha256').update('this-pc').digest('hex');
const CODE = Array.from({length: 24}, (_, i) => '0123456789ABCDEFGHJKMNPQRSTVWXYZ'.slice(i, i + 6).padEnd(6, '7')).join('-');
const OTHER_CODE = CODE.replace(/^.{6}/, 'ZZZZZZ');

let telegram = [];
const realFetch = globalThis.fetch;
const stubTelegram = (ok = true) => {
  telegram = [];
  globalThis.fetch = async (url, init) => {
    telegram.push({url: String(url), body: JSON.parse(init.body)});
    if (!ok) throw new Error('network down');
    return new Response('{"ok":true}', {status: 200});
  };
};
test.afterEach(() => { globalThis.fetch = realFetch; });

const env = (extra = {}) => ({DB: d1(), LICENCE_ADMIN_TOKEN: ADMIN, TELEGRAM_BOT_TOKEN: '123456:BOT-SECRET', TELEGRAM_OWNER_CHAT_ID: '42', ...extra});
const call = (e, path, init = {}, now = NOW) => worker.fetch(new Request('https://relay.example' + path, init), e, {}, now);
const json = (body, headers = {}) => ({method: 'POST', body: JSON.stringify(body), headers: {'content-type': 'application/json', ...headers}});
const ask = (e, over = {}, headers = {}, now = NOW) => call(e, '/licence/request', json({
  product: 'al-store', kind: 'trial', device: DEVICE, machine: MACHINE, nonce: randomUUID(), shop: 'Test shop', version: '1.6.0', ...over,
}, {'cf-connecting-ip': '203.0.113.7', ...headers}), now);
const admin = {authorization: 'Bearer ' + ADMIN};
const poll = (e, id, token, now = NOW) => call(e, '/licence/status?id=' + id, {headers: {authorization: 'Bearer ' + token}}, now);
const decide = (e, body, now = NOW) => call(e, '/licence/decide', json(body, admin), now);
const pendingList = async (e) => (await (await call(e, '/licence/pending', {headers: admin})).json()).requests;
const rowCount = (e) => e.DB.raw.prepare('SELECT COUNT(*) AS n FROM licence_requests').get().n;

test('a request becomes pending, the owner is told on Telegram, and the poll token is shown once', async () => {
  stubTelegram();
  const e = env();
  const r = await ask(e);
  assert.equal(r.status, 202);
  const a = await r.json();
  assert.equal(a.status, 'pending');
  assert.match(a.poll_token, /^lp_[0-9a-f]{48}$/);
  assert.equal(a.server_time, NOW);
  assert.equal(telegram.length, 1);
  assert.match(telegram[0].url, /^https:\/\/api\.telegram\.org\/bot123456:BOT-SECRET\/sendMessage$/);
  assert.equal(telegram[0].body.chat_id, '42');
  assert.match(telegram[0].body.text, /تجربة 14 يوم/);
  assert.ok(telegram[0].body.text.includes(DEVICE) && telegram[0].body.text.includes(a.id.slice(0, 8)));
  assert.ok(!telegram[0].body.text.includes('Test shop'), 'what the shop typed never goes into the alert');
  const stored = e.DB.raw.prepare('SELECT * FROM licence_requests').get();
  assert.notEqual(stored.poll_hash, a.poll_token, 'only the hash of the token is stored');
  assert.equal(stored.poll_hash, createHash('sha256').update(a.poll_token).digest('hex'));
  assert.equal(JSON.stringify(a).includes('BOT-SECRET'), false);
  const [p] = await pendingList(e);
  assert.deepEqual(Object.keys(p).sort(), ['created_at', 'device', 'id', 'kind', 'machine', 'product', 'ref', 'shop', 'src', 'version']);
  assert.equal(p.src.length, 16, 'the sender address is only a daily-salted hash');
});

test('sending the same request again is a replay: nothing new, no second alert, no token', async () => {
  stubTelegram();
  const e = env();
  const nonce = randomUUID();
  const first = await (await ask(e, {nonce})).json();
  const again = await ask(e, {nonce});
  assert.equal(again.status, 200);
  const b = await again.json();
  assert.equal(b.id, first.id);
  assert.equal(b.replay, true);
  assert.equal(b.poll_token, undefined, 'a replay never learns the poll token');
  assert.equal(rowCount(e), 1);
  assert.equal(telegram.length, 1);
});

test('status and ack belong to the holder of the poll token; a stranger learns nothing', async () => {
  stubTelegram();
  const e = env();
  const a = await (await ask(e)).json();
  const mine = await poll(e, a.id, a.poll_token);
  assert.deepEqual(await mine.json(), {status: 'pending', reason: '', server_time: NOW});
  const wrong = await poll(e, a.id, 'lp_' + 'f'.repeat(48));
  const unknown = await poll(e, randomUUID(), a.poll_token);
  assert.equal(wrong.status, 401);
  assert.equal(unknown.status, 401);
  assert.deepEqual(await wrong.json(), await unknown.json(), 'an unknown id and a wrong token look the same');
  assert.equal((await call(e, '/licence/status?id=' + a.id)).status, 401);
  assert.equal((await call(e, '/licence/ack', json({id: a.id}, {authorization: 'Bearer nope-nope-nope-nope-nope'}))).status, 401);
});

test('the owner issues; the shop collects the code once and the relay forgets it', async () => {
  stubTelegram();
  const e = env();
  const a = await (await ask(e)).json();
  assert.equal((await decide(e, {id: a.id, action: 'issue', code: CODE})).status, 200);
  const got = await (await poll(e, a.id, a.poll_token)).json();
  assert.equal(got.status, 'issued');
  assert.equal(got.code, CODE);
  const ack = await call(e, '/licence/ack', json({id: a.id}, {authorization: 'Bearer ' + a.poll_token}), NOW + 5);
  assert.equal((await ack.json()).status, 'delivered');
  const after = await (await poll(e, a.id, a.poll_token)).json();
  assert.equal(after.status, 'delivered');
  assert.equal(after.code, undefined);
  assert.equal(e.DB.raw.prepare('SELECT code FROM licence_requests WHERE id = ?').get(a.id).code, null, 'the code left the relay');
  assert.equal((await pendingList(e)).length, 0);
  const again = await call(e, '/licence/ack', json({id: a.id}, {authorization: 'Bearer ' + a.poll_token}));
  assert.equal((await again.json()).status, 'delivered', 'ack is repeatable');
});

test('only the owner decides: wrong, missing or unset admin token is refused; bad codes and conflicts too', async () => {
  stubTelegram();
  const e = env();
  const a = await (await ask(e)).json();
  const body = {id: a.id, action: 'issue', code: CODE};
  assert.equal((await call(e, '/licence/decide', json(body))).status, 401);
  assert.equal((await call(e, '/licence/decide', json(body, {authorization: 'Bearer wrong'}))).status, 401);
  assert.equal((await call(e, '/licence/pending')).status, 401);
  assert.equal((await call(e, '/licence/events')).status, 401);
  assert.equal((await call(env({LICENCE_ADMIN_TOKEN: ''}), '/licence/pending', {headers: {authorization: 'Bearer '}})).status, 401, 'no token set: closed');
  assert.equal((await call(e, '/licence/pending', {headers: {authorization: 'Bearer pull-secret'}})).status, 401, 'the telemetry token does not open the licence side');
  assert.equal((await decide(e, {id: a.id, action: 'issue', code: 'NOT-A-CODE'})).status, 400);
  assert.equal((await decide(e, {id: a.id, action: 'issue', code: CODE.toLowerCase().replace('7', 'U')})).status, 400);
  assert.equal((await decide(e, {id: a.id, action: 'maybe'})).status, 400);
  assert.equal((await decide(e, {id: randomUUID(), action: 'refuse'})).status, 404);
  assert.equal((await decide(e, body)).status, 200);
  const repeat = await decide(e, body);
  assert.equal(repeat.status, 200);
  assert.equal((await repeat.json()).repeat, true, 'the owner\'s program may retry after a network error');
  assert.equal((await decide(e, {...body, code: OTHER_CODE})).status, 409, 'a second, different code for the same request is refused');
  assert.equal((await decide(e, {id: a.id, action: 'refuse'})).status, 409);
});

test('the owner can refuse, with a machine-readable reason the shop can show', async () => {
  stubTelegram();
  const e = env();
  const a = await (await ask(e)).json();
  assert.equal((await decide(e, {id: a.id, action: 'refuse', reason: 'owner_refused'})).status, 200);
  const got = await (await poll(e, a.id, a.poll_token)).json();
  assert.equal(got.status, 'refused');
  assert.equal(got.reason, 'owner_refused');
  assert.equal(got.code, undefined);
  const a2 = await (await ask(e, {device: 'AAAAA-BBBBB', machine: 'b'.repeat(64)})).json();
  await decide(e, {id: a2.id, action: 'refuse', reason: '<script>'});
  assert.equal((await (await poll(e, a2.id, a2.poll_token)).json()).reason, 'owner_refused', 'a reason that is not a plain key is replaced');
});

test('one trial per machine and per device: the repeat is refused quietly and the owner is not woken', async () => {
  stubTelegram();
  const e = env({LICENCE_PER_DEVICE_DAY: '20'});
  const first = await (await ask(e)).json();
  await decide(e, {id: first.id, action: 'issue', code: CODE});
  const alerts = telegram.length;
  // a fresh install on the same PC gets a new device code but the same machine tag
  const sameMachine = await ask(e, {device: 'AAAAA-BBBBB'});
  assert.equal(sameMachine.status, 200);
  const sm = await sameMachine.json();
  assert.equal(sm.status, 'refused');
  assert.equal(sm.reason, 'already_used');
  // the same device on another claimed machine
  const sameDevice = await (await ask(e, {machine: 'c'.repeat(64)})).json();
  assert.equal(sameDevice.status, 'issued', 'the code for this device is still waiting: it is handed over again, see the next test');
  assert.equal(telegram.length, alerts, 'refusals and re-delivery never alert the owner');
  const p = await (await poll(e, sm.id, sm.poll_token)).json();
  assert.equal(p.reason, 'already_used');
  // after delivery the same device and machine are both used up
  await call(e, '/licence/ack', json({id: sameDevice.id}, {authorization: 'Bearer ' + sameDevice.poll_token}));
  for (const over of [{machine: 'd'.repeat(64)}, {device: 'CCCCC-DDDDD'}, {}]) {
    const r = await (await ask(e, over)).json();
    assert.equal(r.reason, 'already_used', JSON.stringify(over));
  }
  assert.equal((await pendingList(e)).length, 0);
  // a paid request is not a trial: it is allowed
  const paid = await ask(e, {kind: 'monthly', machine: undefined, ref: 'InstaPay 123'});
  assert.equal(paid.status, 202);
});

test('a shop that lost its poll token gets the waiting code again, not a second trial', async () => {
  stubTelegram();
  const e = env();
  const first = await (await ask(e)).json();
  await decide(e, {id: first.id, action: 'issue', code: CODE});
  const again = await (await ask(e)).json();
  assert.equal(again.status, 'issued');
  assert.equal(again.reason, 'reissued');
  assert.equal((await (await poll(e, again.id, again.poll_token)).json()).code, CODE);
  assert.equal((await (await poll(e, first.id, first.poll_token)).json()).status, 'delivered', 'the old request is closed: its code now lives on the new one');
});

test('a new request for the same device replaces the one still waiting', async () => {
  stubTelegram();
  const e = env();
  const old = await (await ask(e)).json();
  const fresh = await (await ask(e)).json();
  assert.notEqual(old.id, fresh.id);
  const list = await pendingList(e);
  assert.deepEqual(list.map((x) => x.id), [fresh.id]);
  assert.equal((await (await poll(e, old.id, old.poll_token)).json()).status, 'expired');
});

test('limits: per address per day, per device per day, and the waiting list is capped', async () => {
  stubTelegram();
  const e = env({LICENCE_PER_SOURCE_DAY: '3', LICENCE_PER_DEVICE_DAY: '2', LICENCE_PENDING_MAX: '5'});
  const dev = (n) => ({device: `ABCDE-${String(n).padStart(5, '0')}`, machine: createHash('sha256').update('m' + n).digest('hex')});
  for (let i = 0; i < 3; i++) assert.equal((await ask(e, dev(i), {'cf-connecting-ip': '198.51.100.1'})).status, 202);
  assert.equal((await ask(e, dev(3), {'cf-connecting-ip': '198.51.100.1'})).status, 429, 'per address');
  assert.equal((await ask(e, dev(3), {'cf-connecting-ip': '198.51.100.2'})).status, 202, 'another address is not affected');
  assert.equal((await ask(e, dev(9), {'cf-connecting-ip': '198.51.100.3'})).status, 202);
  assert.equal((await ask(e, dev(9), {'cf-connecting-ip': '198.51.100.4'})).status, 202);
  assert.equal((await ask(e, dev(9), {'cf-connecting-ip': '198.51.100.5'})).status, 429, 'per device: only two a day');
  assert.equal((await ask(e, dev(10), {'cf-connecting-ip': '198.51.100.6'})).status, 503, 'the waiting list is full');
  assert.equal((await ask(e, dev(0), {'cf-connecting-ip': '198.51.100.1'}, NOW + DAY + 5)).status, 202, 'the next day counts again');
});

test('bad input is refused with the name of the field, and shop text is cleaned', async () => {
  stubTelegram();
  const e = env();
  const field = async (over) => (await (await ask(e, over)).json()).field;
  assert.equal(await field({product: 'other'}), 'product');
  assert.equal(await field({product: 'AL STORE'}), 'product');
  assert.equal(await field({kind: 'free'}), 'kind');
  assert.equal(await field({device: '7KD2M-QX9TI'}), 'device', 'I is not in the code alphabet');
  assert.equal(await field({device: '7kd2m-qx9tp'}), 'device', 'devices are upper case');
  assert.equal(await field({machine: undefined}), 'machine', 'a trial needs the machine tag');
  assert.equal(await field({machine: 'abc'}), 'machine');
  assert.equal(await field({nonce: 'not-a-uuid'}), 'nonce');
  assert.equal((await call(e, '/licence/request', {method: 'POST', body: 'plain'})).status, 400);
  assert.equal((await call(e, '/licence/request', {method: 'POST', body: '[]'})).status, 400);
  assert.equal((await call(e, '/licence/request', {method: 'POST', body: 'x'.repeat(3000)})).status, 413);
  assert.equal((await call(e, '/licence/request')).status, 404, 'GET is not a request');
  assert.equal(rowCount(e), 0);
  await ask(e, {shop: '  A‮B\u0000C\n\n' + 'x'.repeat(200), ref: undefined});
  const row = e.DB.raw.prepare('SELECT shop FROM licence_requests').get();
  assert.ok(row.shop.length <= 60);
  assert.doesNotMatch(row.shop, /[\u0000-\u001f‪-‮]/);
  assert.match(row.shop, /^A B C x+$/);
});

test('Telegram trouble never fails a request; with no Telegram secrets nothing is sent', async () => {
  stubTelegram(false);
  const e = env();
  assert.equal((await ask(e)).status, 202);
  assert.equal(telegram.length, 1, 'tried once');
  stubTelegram();
  const quiet = env({TELEGRAM_BOT_TOKEN: '', TELEGRAM_OWNER_CHAT_ID: ''});
  assert.equal((await ask(quiet)).status, 202);
  assert.equal(telegram.length, 0);
  assert.match(alertText({kind: 'monthly', product: 'al-store', device: DEVICE, id: randomUUID()}), /تأكيد الدفع/);
});

test('the log tells what happened and holds no code and no shop text', async () => {
  stubTelegram();
  const e = env();
  const a = await (await ask(e)).json();
  await decide(e, {id: a.id, action: 'issue', code: CODE});
  await call(e, '/licence/ack', json({id: a.id}, {authorization: 'Bearer ' + a.poll_token}), NOW + 3);
  const ev = (await (await call(e, '/licence/events', {headers: admin})).json()).events;
  assert.deepEqual(ev.map((x) => x.event).reverse(), ['created', 'issued', 'delivered']);
  const text = JSON.stringify(ev);
  assert.ok(!text.includes(CODE) && !text.includes('Test shop') && !text.includes('BOT-SECRET') && !text.includes(a.poll_token));
});

test('D1 free-plan limits: a request is at most 9 queries, a poll one, a decision two', async () => {
  stubTelegram();
  const e = env();
  e.DB.log.length = 0;
  const a = await (await ask(e)).json();
  assert.ok(e.DB.log.length <= 9, `request used ${e.DB.log.length} queries`);
  e.DB.log.length = 0;
  await poll(e, a.id, a.poll_token);
  assert.equal(e.DB.log.length, 1);
  e.DB.log.length = 0;
  await decide(e, {id: a.id, action: 'issue', code: CODE});
  assert.ok(e.DB.log.length <= 3, `decision used ${e.DB.log.length} queries`);
  for (const sql of e.DB.log) assert.doesNotMatch(sql.replace(/\s+/g, ' '), /COUNT\(\*\)[^]*FROM licence_requests(?! WHERE)/i);
  const plan = (sql, ...args) => JSON.stringify(e.DB.raw.prepare('EXPLAIN QUERY PLAN ' + sql).all(...args));
  assert.match(plan('SELECT COUNT(*) FROM licence_requests WHERE src = ? AND created_at > ?', 'x', 1), /licence_src/);
  assert.match(plan('SELECT COUNT(*) FROM licence_requests WHERE device = ? AND created_at > ?', 'x', 1), /licence_device/);
  assert.match(plan("SELECT COUNT(*) FROM licence_requests WHERE status = 'pending'"), /licence_status/);
  assert.match(plan("SELECT 1 FROM licence_requests WHERE product = ? AND kind = 'trial' AND status IN ('issued','delivered') AND (machine = ? OR device = ?)", 'p', 'm', 'd'), /licence_machine|licence_device/);
});

test('clean-up closes old requests, drops their codes, and remembers trials for more than a year', async () => {
  stubTelegram();
  const e = env();
  const a = await (await ask(e)).json();
  const b = await (await ask(e, {device: 'AAAAA-BBBBB', machine: 'b'.repeat(64)})).json();
  await decide(e, {id: b.id, action: 'issue', code: CODE});
  assert.equal(await cleanupLicence(e, NOW + 13 * DAY), 0);
  assert.ok(await cleanupLicence(e, NOW + 15 * DAY) >= 2);
  const rows = e.DB.raw.prepare('SELECT id, status, code FROM licence_requests ORDER BY created_at').all();
  assert.deepEqual(rows.map((r) => r.status), ['expired', 'expired']);
  assert.ok(rows.every((r) => r.code === null));
  assert.equal((await (await poll(e, a.id, a.poll_token, NOW + 15 * DAY)).json()).status, 'expired');
  const c = await (await ask(e, {device: 'EEEEE-FFFFF', machine: 'e'.repeat(64)}, {}, NOW + 20 * DAY)).json();
  await decide(e, {id: c.id, action: 'issue', code: CODE}, NOW + 20 * DAY);
  await call(e, '/licence/ack', json({id: c.id}, {authorization: 'Bearer ' + c.poll_token}), NOW + 20 * DAY);
  await cleanupLicence(e, NOW + 300 * DAY);
  assert.equal(e.DB.raw.prepare("SELECT COUNT(*) AS n FROM licence_requests WHERE status = 'delivered'").get().n, 1, 'still remembered after 300 days');
  await cleanupLicence(e, NOW + 450 * DAY);
  assert.equal(e.DB.raw.prepare("SELECT COUNT(*) AS n FROM licence_requests WHERE status = 'delivered'").get().n, 0);
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM licence_events').get().n, 0, 'old events are removed');
});

test('template carries no licence secret', async () => {
  const {readFileSync} = await import('node:fs');
  const toml = readFileSync(new URL('../wrangler.toml', import.meta.url), 'utf8');
  assert.doesNotMatch(toml, /LICENCE_ADMIN_TOKEN\s*=|TELEGRAM_BOT_TOKEN\s*=|TELEGRAM_OWNER_CHAT_ID\s*=/);
  assert.match(toml, /LICENCE_PRODUCTS/);
});
