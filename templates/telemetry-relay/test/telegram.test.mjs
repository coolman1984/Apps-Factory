// Run: node --experimental-sqlite --test test/telegram.test.mjs   (Node 22.13+). The owner's two buttons on Telegram (POST /telegram):
// who may press them, what a press does and does not do, and what every wrong press leaves behind (nothing).
// D1 is the node:sqlite shim of d1.mjs; Telegram is a recording stub (no network, no real bot).
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash, randomUUID} from 'node:crypto';
import {d1} from './d1.mjs';
import worker from '../src/worker.js';

const NOW = 1_800_000_000;
const HOUR = 3600;
const ADMIN = 'admin-secret-' + 'x'.repeat(20);
const SECRET = 'webhook-secret-' + 'y'.repeat(24);
const OWNER = '42';
const DEVICE = '7KD2M-QX9TP';
const MACHINE = createHash('sha256').update('this-pc').digest('hex');
const CODE = Array.from({length: 24}, (_, i) => '0123456789ABCDEFGHJKMNPQRSTVWXYZ'.slice(i, i + 6).padEnd(6, '7')).join('-');

let sent = [];
const realFetch = globalThis.fetch;
const stub = () => {
  sent = [];
  globalThis.fetch = async (url, init) => {
    sent.push({method: String(url).split('/').pop(), body: JSON.parse(init.body)});
    return new Response('{"ok":true}', {status: 200});
  };
};
test.beforeEach(stub);
test.afterEach(() => { globalThis.fetch = realFetch; });
const calls = (method) => sent.filter((c) => c.method === method);

const env = (extra = {}) => ({DB: d1(), LICENCE_ADMIN_TOKEN: ADMIN, TELEGRAM_BOT_TOKEN: '123456:BOT-SECRET', TELEGRAM_OWNER_CHAT_ID: OWNER,
  TELEGRAM_WEBHOOK_SECRET: SECRET, ...extra});
const call = (e, path, init = {}, now = NOW) => worker.fetch(new Request('https://relay.example' + path, init), e, {}, now);
const json = (body, headers = {}) => ({method: 'POST', body: JSON.stringify(body), headers: {'content-type': 'application/json', ...headers}});
const ask = async (e, over = {}, now = NOW) => (await call(e, '/licence/request', json({
  product: 'al-store', kind: 'trial', device: DEVICE, machine: MACHINE, nonce: randomUUID(), shop: 'Test shop', version: '1.8.0', ...over,
}, {'cf-connecting-ip': '203.0.113.7'}), now)).json();
const admin = {authorization: 'Bearer ' + ADMIN};
const poll = async (e, a, now = NOW) => (await call(e, '/licence/status?id=' + a.id, {headers: {authorization: 'Bearer ' + a.poll_token}}, now)).json();
const row = (e, id) => e.DB.raw.prepare('SELECT r.*, o.decision AS owner_decision, o.decided_at AS owner_decided_at FROM licence_requests r '
  + 'LEFT JOIN licence_owner o ON o.request_id = r.id WHERE r.id = ?').get(id);
const events = (e) => e.DB.raw.prepare('SELECT * FROM licence_events ORDER BY id').all();

// What Telegram sends when a button is pressed (the parts we read).
const press = (e, data, {from = OWNER, chat = OWNER, message_id = 77, secret = SECRET, id = 'cb1'} = {}, now = NOW) => call(e, '/telegram', json(
  {update_id: 1, callback_query: {id, from: {id: Number(from)}, message: {message_id, chat: {id: Number(chat)}}, data}},
  secret === null ? {} : {'x-telegram-bot-api-secret-token': secret}), now);
const ok = (id) => `ok:${id}`;
const no = (id) => `no:${id}`;

test('every alert carries exactly two buttons whose data is only an action and the request id', async () => {
  const e = env();
  const a = await ask(e);
  const alert = calls('sendMessage')[0].body;
  const [buttons] = alert.reply_markup.inline_keyboard;
  assert.deepEqual(buttons.map((b) => b.callback_data), [ok(a.id), no(a.id)]);
  assert.ok(buttons.every((b) => Buffer.byteLength(b.callback_data) <= 64), 'Telegram allows 64 bytes');
  assert.deepEqual(buttons.map((b) => b.text), ['✅ موافق', '❌ رفض']);
  assert.ok(!JSON.stringify(alert).includes('Test shop'));
  const paid = await ask(e, {kind: 'monthly', machine: undefined, device: 'AAAAA-BBBBB'});
  const paidAlert = calls('sendMessage')[1].body;
  assert.match(paidAlert.text, /تأكيد الدفع/, 'a paid request says that approving here is not enough');
  assert.equal(paidAlert.reply_markup.inline_keyboard[0][0].callback_data, ok(paid.id));
});

test('without the webhook secret the alert has no buttons (they would do nothing) and says what the Studio will do', async () => {
  const e = env({TELEGRAM_WEBHOOK_SECRET: ''});
  await ask(e);
  const alert = calls('sendMessage')[0].body;
  assert.equal(alert.reply_markup, undefined);
  assert.doesNotMatch(alert.text, /✅|❌/);
  assert.match(alert.text, /برنامج التراخيص/);
});

test('the buttons are closed unless the webhook secret, the bot and a private owner chat are all set', async () => {
  const a = await ask(env());
  for (const extra of [{TELEGRAM_WEBHOOK_SECRET: ''}, {TELEGRAM_BOT_TOKEN: ''}, {TELEGRAM_OWNER_CHAT_ID: ''}, {TELEGRAM_OWNER_CHAT_ID: '-100123'}]) {
    const e = env(extra);
    sent = [];
    const b = await ask(e);
    assert.equal((await press(e, ok(b.id))).status, 404, JSON.stringify(extra));
    assert.equal(row(e, b.id).owner_decision, null);
    assert.equal(sent.filter((c) => c.body.reply_markup).length, 0, `an alert never carries buttons that cannot work: ${JSON.stringify(extra)}`);
  }
  assert.equal((await call(env(), '/telegram')).status, 404, 'a GET is not a press');
  assert.ok(a.id);
});

test('a wrong or missing secret is refused, changes nothing, costs no D1 query and tells nobody', async () => {
  const e = env();
  const a = await ask(e);
  sent = [];
  e.DB.log.length = 0;
  const warn = console.warn;
  console.warn = () => {};
  try {
    for (const secret of [null, '', 'nope', SECRET + 'x', SECRET.slice(0, -1)]) {
      assert.equal((await press(e, ok(a.id), {secret})).status, 401, String(secret));
    }
  } finally { console.warn = warn; }
  assert.equal(row(e, a.id).owner_decision, null);
  assert.equal(row(e, a.id).status, 'pending');
  assert.equal(sent.length, 0, 'an unauthenticated caller makes the bot say nothing');
  assert.equal(e.DB.log.length, 0, 'a flood of wrong secrets never touches the database (the address is public and the plan is free)');
});

test('the log of refused presses (from the owner\'s own chat or Telegram) is capped, so nobody can fill the database', async () => {
  const e = env();
  for (let i = 0; i < 80; i++) await press(e, ok(randomUUID()), {from: '999'});
  assert.equal(events(e).filter((x) => x.event === 'tg_refused').length, 50);
  await press(e, ok(randomUUID()), {from: '999'}, NOW + 2 * HOUR);
  assert.equal(events(e).filter((x) => x.event === 'tg_refused').length, 51, 'the next hour counts again');
});

test('only the owner\'s own private chat counts: another person, a copied message in another chat, a forwarded press', async () => {
  const e = env();
  const a = await ask(e);
  sent = [];
  assert.equal((await press(e, ok(a.id), {from: '999'})).status, 200, 'authentic updates are always answered 200 so Telegram does not retry');
  await press(e, ok(a.id), {chat: '-100777'});                       // the owner, but on a message in a group
  await press(e, ok(a.id), {from: '999', chat: '999'});             // a stranger in their own chat with the bot
  await press(e, no(a.id), {from: '999', chat: OWNER});             // a stranger on the owner's message (cannot happen, still refused)
  assert.equal(row(e, a.id).owner_decision, null);
  assert.equal(row(e, a.id).status, 'pending');
  assert.equal(calls('editMessageText').length, 0, 'the owner\'s message is not touched');
  assert.deepEqual(calls('answerCallbackQuery').map((c) => c.body.text), Array(4).fill('مش مسموح'));
  assert.deepEqual(events(e).filter((x) => x.event === 'tg_refused').map((x) => x.detail), Array(4).fill('not_owner'));
});

test('approve records the owner\'s decision, keeps the request waiting, tells the shop "approved" and offers only «سحب الموافقة»', async () => {
  const e = env();
  const a = await ask(e);
  sent = [];
  assert.equal((await press(e, ok(a.id))).status, 200);
  const r = row(e, a.id);
  assert.equal(r.status, 'pending', 'an approval is not a licence');
  assert.equal(r.owner_decision, 'approved');
  assert.equal(r.owner_decided_at, NOW);
  assert.equal(r.code, null);
  assert.deepEqual(await poll(e, a), {status: 'pending', reason: '', stage: 'approved', server_time: NOW});
  const [p] = (await (await call(e, '/licence/pending', {headers: admin})).json()).requests;
  assert.equal(p.owner_decision, 'approved');
  assert.equal(calls('answerCallbackQuery')[0].body.text, 'تمت الموافقة ✅');
  const edit = calls('editMessageText')[0].body;
  assert.equal(edit.chat_id, OWNER);
  assert.equal(edit.message_id, 77);
  assert.deepEqual(edit.reply_markup.inline_keyboard[0].map((b) => b.callback_data), [no(a.id)]);
  assert.match(edit.text, /وافقت/);
  assert.deepEqual(events(e).map((x) => x.event), ['created', 'approved']);
  assert.equal(JSON.stringify(Object.keys(row(e, a.id)).filter((k) => k.startsWith('owner'))), '["owner_decision","owner_decided_at"]');
});

test('the shop is told "approved" only for a trial and only while the approval counts', async () => {
  const e = env();
  const trial = await ask(e);
  const paid = await ask(e, {kind: 'monthly', machine: undefined, device: 'AAAAA-BBBBB'});
  await press(e, ok(trial.id));
  await press(e, ok(paid.id), {id: 'p'});
  assert.equal((await poll(e, trial)).stage, 'approved');
  assert.equal((await poll(e, paid)).stage, undefined, 'a paid kind is only the owner\'s intent: the shop is not told it is settled');
  assert.equal((await poll(e, trial, NOW + 73 * HOUR)).stage, undefined, 'and the word expires with the approval');
  const [a, b] = (await (await call(e, '/licence/pending', {headers: admin})).json()).requests;
  assert.deepEqual([a.owner_decision, b.owner_decision], ['approved', 'approved']);
  const late = (await (await call(e, '/licence/pending', {headers: admin}, NOW + 73 * HOUR)).json()).requests;
  assert.deepEqual(late.map((r) => r.owner_decision), ['expired', 'expired'], 'the relay, not the owner\'s PC clock, says an approval is too old');
});

test('LICENCE_APPROVAL_HOURS can not be set to nothing: an approval always counts for at least an hour', async () => {
  const e = env({LICENCE_APPROVAL_HOURS: '0'});
  const a = await ask(e);
  await press(e, ok(a.id), {}, NOW + 30 * 60);
  assert.equal(row(e, a.id).owner_decision, 'approved');
});

test('upgrading a 0.13 database is just running schema.sql again (no ALTER, nothing to forget)', async () => {
  const {readFileSync} = await import('node:fs');
  const {DatabaseSync} = await import('node:sqlite');
  const db = new DatabaseSync(':memory:');
  const schema = readFileSync(new URL('../schema.sql', import.meta.url), 'utf8');
  db.exec(schema.replace(/CREATE TABLE IF NOT EXISTS licence_owner[^;]*;\s*CREATE INDEX IF NOT EXISTS licence_owner_at[^;]*;/, ''));   // a database made by 0.13
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE name = 'licence_owner'").get().n, 0);
  db.exec(schema);
  db.exec(schema);                                                                   // and twice is fine
  assert.equal(db.prepare("SELECT COUNT(*) AS n FROM sqlite_master WHERE name = 'licence_owner'").get().n, 1);
});

test('pressing approve twice (a double click, or Telegram sending it again) does one thing', async () => {
  const e = env();
  const a = await ask(e);
  await press(e, ok(a.id));
  const before = events(e).length;
  for (let i = 0; i < 3; i++) await press(e, ok(a.id), {id: 'again' + i});
  assert.equal(events(e).length, before, 'nothing new was recorded');
  assert.equal(row(e, a.id).owner_decided_at, NOW);
  assert.equal(calls('answerCallbackQuery').at(-1).body.text, 'وافقت قبل كده ✅');
});

test('pressing approve again after the approval has gone stale does not promise a code (review of PR #42)', async () => {
  const e = env({LICENCE_APPROVAL_HOURS: '2'});
  const a = await ask(e);
  await press(e, ok(a.id));
  await press(e, ok(a.id), {id: 'inside'}, NOW + 3600);
  assert.equal(calls('answerCallbackQuery').at(-1).body.text, 'وافقت قبل كده ✅', 'inside the window it is still the approval');
  const before = events(e).length;
  await press(e, ok(a.id), {id: 'late'}, NOW + 3 * 3600);
  assert.equal(calls('answerCallbackQuery').at(-1).body.text, 'الموافقة قديمة: وافق من برنامج التراخيص بنفسك أو خلي المحل يطلب تاني');
  assert.match(calls('editMessageText').at(-1).body.text, /الموافقة قديمة/);
  assert.deepEqual(calls('editMessageText').at(-1).body.reply_markup.inline_keyboard, [], 'no approve button is left on it');
  assert.equal(events(e).length, before + 1, 'one audit line: the stale press');
  await press(e, ok(a.id), {id: 'later'}, NOW + 4 * 3600);
  await press(e, ok(a.id), {id: 'later2'}, NOW + 5 * 3600);
  assert.equal(events(e).length, before + 1, 'pressing it again adds nothing: one line per request');
  assert.equal(events(e).at(-1).event, 'tg_stale');
  assert.equal(row(e, a.id).status, 'pending', 'nothing is signed or closed by it');
});

test('«رفض» closes the request at once, the shop sees the refusal, and a refusal is final', async () => {
  const e = env();
  const a = await ask(e);
  sent = [];
  await press(e, no(a.id));
  const r = row(e, a.id);
  assert.equal(r.status, 'refused');
  assert.equal(r.reason, 'owner_refused');
  assert.equal(r.owner_decision, 'denied');
  assert.deepEqual(await poll(e, a), {status: 'refused', reason: 'owner_refused', server_time: NOW});
  assert.deepEqual(calls('editMessageText')[0].body.reply_markup.inline_keyboard, [], 'no button is left');
  // a later «موافق» (the message was copied, or an old button) cannot bring it back
  await press(e, ok(a.id), {id: 'late'});
  assert.equal(row(e, a.id).status, 'refused');
  assert.equal(row(e, a.id).owner_decision, 'denied');
  assert.equal(calls('answerCallbackQuery').at(-1).body.text, 'الطلب اترفض قبل كده');
  assert.equal((await (await call(e, '/licence/pending', {headers: admin})).json()).requests.length, 0);
});

test('the owner can take an approval back until the code is signed', async () => {
  const e = env();
  const a = await ask(e);
  await press(e, ok(a.id));
  await press(e, no(a.id), {id: 'withdraw'});
  assert.equal(row(e, a.id).status, 'refused');
  assert.match(events(e).at(-1).detail, /withdrawn/);
  assert.equal((await poll(e, a)).status, 'refused');
});

test('once the owner\'s program has issued the code, a button changes nothing', async () => {
  const e = env();
  const a = await ask(e);
  await press(e, ok(a.id));
  assert.equal((await call(e, '/licence/decide', json({id: a.id, action: 'issue', code: CODE}, admin))).status, 200);
  sent = [];
  await press(e, no(a.id), {id: 'too-late'});
  assert.equal(row(e, a.id).status, 'issued', 'a refusal after signing cannot undo a code the shop may already hold');
  assert.equal(row(e, a.id).code, CODE);
  assert.equal(calls('answerCallbackQuery')[0].body.text, 'الطلب اتقفل خلاص');
  assert.match(calls('editMessageText')[0].body.text, /اتقفل/);
  // delivered
  await call(e, '/licence/ack', json({id: a.id}, {authorization: 'Bearer ' + a.poll_token}), NOW + 5);
  await press(e, ok(a.id), {id: 'later'}, NOW + 10);
  assert.equal(row(e, a.id).status, 'delivered');
});

test('an approval older than the limit is refused: the shop must ask again', async () => {
  const e = env();
  const a = await ask(e);
  sent = [];
  await press(e, ok(a.id), {}, NOW + 73 * HOUR);
  assert.equal(row(e, a.id).owner_decision, null);
  assert.equal(calls('answerCallbackQuery')[0].body.text, 'الطلب قديم: خلي المحل يطلب تاني');
  assert.equal(events(e).at(-1).event, 'tg_refused');
  await press(e, ok(a.id), {id: 'fresh'}, NOW + 71 * HOUR);
  assert.equal(row(e, a.id).owner_decision, 'approved', 'inside the limit it works');
  const b = await ask(env({LICENCE_APPROVAL_HOURS: '1'}));
  assert.ok(b.id);
});

test('junk is answered calmly and changes nothing: bad data, unknown request, not JSON, a list, a huge body, other updates', async () => {
  const e = env();
  const a = await ask(e);
  for (const data of ['', 'ok:', 'ok:' + a.id.toUpperCase(), 'approve:' + a.id, 'ok:' + a.id + ':x', `ok:${a.id}\nno:${a.id}`, 123, null, {x: 1}]) {
    assert.equal((await press(e, data)).status, 200, JSON.stringify(data));
  }
  assert.equal((await press(e, ok(randomUUID()))).status, 200, 'an unknown request');
  assert.equal(calls('answerCallbackQuery').at(-1).body.text, 'الطلب ده مش موجود');
  const raw = (body, headers = {}) => call(e, '/telegram', {method: 'POST', body, headers: {'x-telegram-bot-api-secret-token': SECRET, ...headers}});
  assert.equal((await raw('not json')).status, 200);
  assert.equal((await raw('[]')).status, 200);
  assert.equal((await raw('null')).status, 200);
  assert.equal((await raw('x'.repeat(9000))).status, 200);
  assert.equal((await raw(JSON.stringify({update_id: 3, message: {text: '/start', chat: {id: 42}}}))).status, 200, 'chat messages are ignored');
  assert.equal((await raw(JSON.stringify({callback_query: 'x'}))).status, 200);
  assert.equal((await raw(JSON.stringify({callback_query: {id: 'c', from: null, message: null, data: ok(a.id)}}))).status, 200);
  assert.equal(row(e, a.id).owner_decision, null);
  assert.equal(row(e, a.id).status, 'pending');
});

test('a button press touches D1 at most three times (four for a refusal) and the log never holds a code or a secret', async () => {
  const e = env();
  const a = await ask(e);
  const b = await ask(e, {device: 'AAAAA-BBBBB', machine: 'b'.repeat(64)});
  e.DB.log.length = 0;
  await press(e, ok(a.id));
  assert.ok(e.DB.log.length <= 3, `approve used ${e.DB.log.length} queries`);
  e.DB.log.length = 0;
  await press(e, no(b.id), {id: 'b'});
  assert.ok(e.DB.log.length <= 4, `refuse used ${e.DB.log.length} queries`);
  await call(e, '/licence/decide', json({id: a.id, action: 'issue', code: CODE}, admin));
  const text = JSON.stringify(events(e)) + JSON.stringify(sent);
  assert.ok(!text.includes(CODE) && !text.includes(SECRET) && !text.includes('BOT-SECRET') && !text.includes(a.poll_token) && !text.includes('Test shop'));
});

test('the owner\'s program can ask what became of requests it still holds as waiting (admin only, at most 50 ids)', async () => {
  const e = env();
  const a = await ask(e);
  const b = await ask(e, {device: 'AAAAA-BBBBB', machine: 'b'.repeat(64)});
  await press(e, no(b.id));
  const ask_ = (ids, headers = admin) => call(e, '/licence/states', json({ids}, headers));
  const got = await (await ask_([a.id, b.id, randomUUID()])).json();
  assert.equal(got.states[a.id].status, 'pending');
  assert.equal(got.states[b.id].status, 'refused');
  assert.equal(got.states[b.id].reason, 'owner_refused');
  assert.equal(Object.keys(got.states).length, 2, 'an unknown id is simply absent');
  assert.equal((await ask_([a.id], {})).status, 401);
  assert.equal((await ask_([a.id], {authorization: 'Bearer wrong'})).status, 401);
  assert.equal((await ask_([])).status, 400);
  assert.equal((await ask_('x')).status, 400);
  assert.equal((await ask_(['not-a-uuid'])).status, 400);
  e.DB.log.length = 0;
  await ask_(Array.from({length: 80}, () => randomUUID()));
  assert.equal(e.DB.log.length, 1, 'one query, at most 50 ids');
});

test('the template holds no webhook secret', async () => {
  const {readFileSync} = await import('node:fs');
  const toml = readFileSync(new URL('../wrangler.toml', import.meta.url), 'utf8');
  assert.doesNotMatch(toml, /TELEGRAM_WEBHOOK_SECRET\s*=/);
  assert.match(toml, /LICENCE_APPROVAL_HOURS/);
});
