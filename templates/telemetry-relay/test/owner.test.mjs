// Run: node --experimental-sqlite --test test/owner.test.mjs   (Node 22.13+). The owner's read-only routes (src/owner.js) and the
// cursor added to GET /licence/events. Admin token only; nothing private in any answer.
import test from 'node:test';
import assert from 'node:assert/strict';
import {randomUUID} from 'node:crypto';
import {d1} from './d1.mjs';
import worker from '../src/worker.js';

const NOW = 1_800_000_000;
const ADMIN = 'admin-secret-' + 'x'.repeat(20);
const PULL = 'pull-secret-' + 'y'.repeat(20);
const admin = {authorization: 'Bearer ' + ADMIN};
const env = (extra = {}) => ({DB: d1(), LICENCE_ADMIN_TOKEN: ADMIN, RELAY_PULL_TOKEN: PULL, ...extra});
const call = (e, path, init = {}, now = NOW) => worker.fetch(new Request('https://relay.example' + path, init), e, {}, now);
const get = (e, path, headers = admin) => call(e, path, {headers});
const hex = (n) => n.toString(16).padStart(8, '0') + '-0000-4000-8000-000000000000';

function seedInstalls(e, n) {
  for (let i = 1; i <= n; i++) e.DB.raw.prepare('INSERT INTO installs (id, token_hash, gen) VALUES (?,?,?)').run(hex(i), 'f'.repeat(64), 'g');
}
function seedRequest(e, i, over = {}) {
  const id = hex(0x100 + i);
  const r = {product: 'al-store', kind: 'trial', device: '7KD2M-QX9TP', status: 'pending', created_at: NOW - 1000 + i, ...over};
  e.DB.raw.prepare('INSERT INTO licence_requests (id, product, kind, device, machine, nonce, poll_hash, shop, ref, version, src, status, reason, code, created_at, decided_at, delivered_at) '
    + 'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').run(id, r.product, r.kind, r.device, 'm'.repeat(64), 'n' + i, 'POLLHASH' + i, 'Private Shop Name', 'PAYREF-123', '1.0', 'SRCHASH', r.status, r.reason ?? '', r.code ?? null, r.created_at, r.decided_at ?? null, r.delivered_at ?? null);
  return id;
}

test('every owner route needs the admin token; the pull token and strangers never reach D1', async () => {
  for (const path of ['/installs', '/licence/history', '/owner/capabilities']) {
    for (const headers of [{}, {authorization: 'Bearer '}, {authorization: 'Bearer nope'}, {authorization: 'Bearer ' + PULL}]) {
      const e = env();
      assert.equal((await get(e, path, headers)).status, 401, path);
      assert.equal(e.DB.log.length, 0);
    }
  }
  const none = env({LICENCE_ADMIN_TOKEN: ''});
  assert.equal((await get(none, '/owner/capabilities', {authorization: 'Bearer '})).status, 401);
  assert.equal((await call(env(), '/licence/history', {method: 'POST', headers: admin, body: '{}'})).status, 405);
  assert.equal((await call(env(), '/owner/capabilities', {method: 'DELETE', headers: admin})).status, 405);
  assert.equal((await call(env(), '/owner/capabilities', {method: 'DELETE'})).status, 401);
});

test('POST /installs still belongs to the pull token and the admin token cannot replace the registry', async () => {
  const e = env();
  const body = JSON.stringify({installs: [{id: hex(1), token_hash: 'a'.repeat(64)}]});
  assert.equal((await call(e, '/installs', {method: 'POST', headers: admin, body})).status, 401);
  assert.equal((await call(e, '/installs', {method: 'POST', headers: {authorization: 'Bearer ' + PULL}, body})).status, 200);
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM installs').get().n, 1);
});

test('GET /installs lists ids only, in pages, with a cursor, and omits every hash', async () => {
  const e = env();
  seedInstalls(e, 5);
  const first = await (await get(e, '/installs?limit=2')).json();
  assert.deepEqual(first.installs, [{id: hex(1)}, {id: hex(2)}]);
  assert.deepEqual(first.nextCursor, {afterId: hex(2)});
  assert.equal(first.coverage, 'registry');
  const rest = await (await get(e, `/installs?afterId=${hex(2)}&limit=100`)).json();
  assert.deepEqual(rest.installs.map((x) => x.id), [hex(3), hex(4), hex(5)]);
  assert.equal(rest.nextCursor, null);
  const text = JSON.stringify([first, rest]);
  assert.ok(!text.includes('token_hash') && !text.includes('ffffffff') && !text.includes('"gen"'));
  assert.equal((await get(e, '/installs?afterId=nope')).status, 400);
  assert.equal((await get(e, '/installs?limit=100000')).status, 200);
});

test('GET /installs pages are stable across more than one hundred rows with no repeat and no gap', async () => {
  const e = env();
  seedInstalls(e, 230);
  const seen = [];
  let url = '/installs?limit=100';
  for (let i = 0; i < 5; i++) {
    const page = await (await get(e, url)).json();
    seen.push(...page.installs.map((x) => x.id));
    if (!page.nextCursor) break;
    url = `/installs?limit=100&afterId=${page.nextCursor.afterId}`;
  }
  assert.equal(seen.length, 230);
  assert.equal(new Set(seen).size, 230);
  assert.deepEqual(seen, [...seen].sort());
});

test('GET /licence/history shows safe metadata for every state and nothing private', async () => {
  const e = env();
  const pending = seedRequest(e, 1);
  seedRequest(e, 2, {status: 'issued', code: 'SECRET-CODE-DO-NOT-LEAK', decided_at: NOW - 500});
  seedRequest(e, 3, {status: 'refused', reason: 'owner_refused', decided_at: NOW - 400});
  seedRequest(e, 4, {status: 'delivered', delivered_at: NOW - 100, decided_at: NOW - 300});
  e.DB.raw.prepare("INSERT INTO licence_owner (request_id, decision, decided_at) VALUES (?, 'approved', ?)").run(pending, NOW - 10);
  const all = await (await get(e, '/licence/history')).json();
  assert.equal(all.requests.length, 4);
  assert.deepEqual(all.requests.map((r) => r.status), ['pending', 'issued', 'refused', 'delivered']);
  assert.equal(all.requests[0].owner_decision, 'approved');
  assert.equal(all.coverage, 'retained');
  const text = JSON.stringify(all);
  for (const secret of ['SECRET-CODE', 'POLLHASH', 'PAYREF', 'Private Shop', 'SRCHASH', 'mmmmmmmm']) assert.ok(!text.includes(secret), secret);
  assert.deepEqual(Object.keys(all.requests[0]).sort(), ['created_at', 'decided_at', 'delivered_at', 'device', 'id', 'kind', 'owner_decided_at', 'owner_decision', 'product', 'reason', 'status']);
  const refused = await (await get(e, '/licence/history?status=refused')).json();
  assert.deepEqual(refused.requests.map((r) => r.status), ['refused']);
  assert.equal((await get(e, '/licence/history?status=all')).status, 400);
});

test('an approval older than the window is shown as expired, like GET /licence/pending', async () => {
  const e = env();
  const id = seedRequest(e, 1);
  e.DB.raw.prepare("INSERT INTO licence_owner (request_id, decision, decided_at) VALUES (?, 'approved', ?)").run(id, NOW - 73 * 3600);
  assert.equal((await (await get(e, '/licence/history')).json()).requests[0].owner_decision, 'expired');
  const pending = (await (await get(e, '/licence/pending')).json()).requests[0];
  assert.equal(pending.owner_decision, 'expired');
});

test('history pages past one hundred rows, with tied timestamps, lose and repeat nothing', async () => {
  const e = env();
  for (let i = 0; i < 230; i++) seedRequest(e, i, {created_at: NOW - 5000 + Math.floor(i / 7)});   // seven rows share each second
  const seen = [];
  let url = '/licence/history?limit=100';
  for (let i = 0; i < 6; i++) {
    const page = await (await get(e, url)).json();
    seen.push(...page.requests.map((r) => r.id));
    if (!page.nextCursor) break;
    url = `/licence/history?limit=100&after=${page.nextCursor.after}`;
  }
  assert.equal(seen.length, 230);
  assert.equal(new Set(seen).size, 230);
  assert.equal((await get(e, '/licence/history?after=abc')).status, 400);
  assert.equal((await get(e, '/licence/history?after=1:zzz')).status, 400);
});

test('GET /licence/events keeps its latest-page behaviour and gains an optional cursor', async () => {
  const e = env();
  for (let i = 1; i <= 250; i++) e.DB.raw.prepare('INSERT INTO licence_events (at, request_id, event, detail) VALUES (?,?,?,?)').run(NOW - i, null, 'created', '');
  const latest = await (await get(e, '/licence/events')).json();
  assert.equal(latest.events.length, 100);
  assert.equal(latest.events[0].id, 250);
  assert.deepEqual(latest.nextCursor, {beforeId: 151});
  const older = await (await get(e, '/licence/events?beforeId=151&limit=200')).json();
  assert.equal(older.events.length, 150);
  assert.equal(older.events[0].id, 150);
  assert.equal(older.nextCursor, null);
  const small = await (await get(e, '/licence/events?limit=3')).json();
  assert.deepEqual(small.events.map((x) => x.id), [250, 249, 248]);
  assert.equal((await get(e, '/licence/events?beforeId=-1')).status, 400);
  assert.equal((await get(e, '/licence/events?beforeId=x')).status, 400);
  assert.equal((await call(e, '/licence/events')).status, 401);
});

test('capabilities name the protocol and the optional routes, and nothing else', async () => {
  const body = await (await get(env(), '/owner/capabilities')).json();
  assert.equal(body.protocol, 1);
  assert.ok(body.routes.includes('GET /installs') && body.routes.includes('POST /audit/append'));
  assert.deepEqual(Object.keys(body).sort(), ['limits', 'protocol', 'routes', 'server_time']);
  const text = JSON.stringify(body);
  assert.ok(!text.includes(ADMIN) && !text.includes(PULL));
});

test('query counts stay inside the D1 Free plan', async () => {
  const e = env();
  seedInstalls(e, 3); seedRequest(e, 1);
  e.DB.log.length = 0;
  await get(e, '/installs'); assert.equal(e.DB.log.length, 1);
  e.DB.log.length = 0;
  await get(e, '/licence/history'); assert.equal(e.DB.log.length, 1);
  e.DB.log.length = 0;
  await get(e, '/licence/events'); assert.equal(e.DB.log.length, 1);
  e.DB.log.length = 0;
  await get(e, '/owner/capabilities'); assert.equal(e.DB.log.length, 0);
});
