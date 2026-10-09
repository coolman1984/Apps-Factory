// Run: node --experimental-sqlite --test test/relay.test.mjs   (Node 22+). D1 is replaced by a tiny shim over node:sqlite
// that also records every statement, so the tests can hold the Worker to the D1 Free-plan limits.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gzipSync} from 'node:zlib';
import {createHash, randomBytes, randomUUID} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import worker, {cleanup, same, sha256hex, MAX_BODY, PENDING_MAX_BODY} from '../src/worker.js';

function d1() {
  const db = new DatabaseSync(':memory:');
  db.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  const log = [];
  const stmt = (sql, args = []) => ({
    bind: (...a) => {
      assert.ok(a.length <= 100, `D1 allows at most 100 bound parameters (got ${a.length})`);
      return stmt(sql, a);
    },
    first: async () => { log.push(sql); return db.prepare(sql).get(...args) ?? null; },
    all: async () => { log.push(sql); return {results: db.prepare(sql).all(...args).map((r) => ({...r}))}; },
    run: async () => { log.push(sql); return {meta: {changes: Number(db.prepare(sql).run(...args).changes)}}; },
  });
  return {prepare: (sql) => stmt(sql), log, raw: db};
}

const NOW = 1_800_000_000;
const INSTALL = '01a11f49-8c0e-71e2-96f1-4ecf7b7751ca';
const TOKEN = 'ins_' + 'a'.repeat(40);
const hash = (t) => createHash('sha256').update(t).digest('hex');
const env = (extra = {}) => ({DB: d1(), RELAY_PULL_TOKEN: 'pull-secret', ...extra});
const body = () => gzipSync(Buffer.from(JSON.stringify([{type: 'hb'}])));
const call = (e, path, init = {}, now = NOW) => worker.fetch(new Request('https://relay.example' + path, init), e, {}, now);
const auth = (t = 'pull-secret') => ({authorization: 'Bearer ' + t, 'content-type': 'application/json'});
const post = (e, opts = {}, now = NOW) => call(e, '/ingest', {
  method: 'POST', body: opts.body ?? body(),
  headers: {'x-af-install': opts.install ?? INSTALL, authorization: 'Bearer ' + (opts.token ?? TOKEN),
    ...(opts.sentAt === undefined ? {'x-af-sent-at': String(now)} : opts.sentAt === null ? {} : {'x-af-sent-at': String(opts.sentAt)}),
    ...(opts.headers || {})},
}, now);
const register = (e, list) => call(e, '/installs', {method: 'POST', headers: auth(), body: JSON.stringify({installs: list})});
const known = async (e, extra = []) => {
  assert.equal((await register(e, [{id: INSTALL, token_hash: hash(TOKEN)}, ...extra])).status, 200);
};
const pullAll = async (e) => (await (await call(e, '/pull?limit=100', {headers: auth()})).json()).batches;

test('ingest stores a batch; pull returns it; ack deletes it', async () => {
  const e = env();
  await known(e);
  const b = body();
  const r = await post(e, {body: b, sentAt: NOW - 7200});
  assert.equal(r.status, 202);
  assert.equal((await r.json()).server_time, NOW, 'every answer carries the server clock');
  const [row] = await pullAll(e);
  assert.deepEqual(Object.keys(row).sort(), ['body', 'id', 'install_id', 'known', 'received_at', 'sent_at', 'size', 'token_hash']);
  assert.deepEqual(Buffer.from(row.body, 'base64'), b, 'bytes kept exactly');
  assert.equal(row.token_hash, hash(TOKEN));
  assert.equal(row.sent_at, NOW - 7200);
  assert.equal(row.known, 1);
  const acked = await (await call(e, '/ack', {method: 'POST', headers: auth(), body: JSON.stringify({ids: [row.id]})})).json();
  assert.equal(acked.deleted, 1);
  assert.equal((await pullAll(e)).length, 0);
});

test('a wrong PC clock is never a refusal (fix 2: no time window)', async () => {
  const e = env();
  await known(e);
  for (const skew of [-86400, -3600, 0, 3600, 86400 * 30]) {
    const r = await post(e, {sentAt: NOW + skew});
    assert.equal(r.status, 202, `skew ${skew}`);
  }
  assert.equal((await post(e, {sentAt: null})).status, 202, 'X-AF-Sent-At is optional');
  const bad = await post(e, {sentAt: 'yesterday'});
  assert.equal(bad.status, 400);
  assert.equal((await bad.json()).server_time, NOW);
});

test('strangers are refused cheaply and cannot fill the relay (fix 5)', async () => {
  const e = env();
  await known(e);
  e.DB.log.length = 0;
  const wrong = await post(e, {token: 'ins_' + 'x'.repeat(40)});
  assert.equal(wrong.status, 401);
  assert.equal(e.DB.log.length, 1, 'one lookup and done: no count, no write');
  assert.equal((await post(e, {token: 'short'})).status, 401);
  assert.equal((await post(e, {install: 'not-a-uuid'})).status, 400);
  // unknown installs park a few SMALL batches in a capped shared area
  const pe = env({PENDING_MAX_ROWS: '6', PENDING_PER_INSTALL: '2', PENDING_PER_SOURCE: '4'});
  const ip = (n) => ({'cf-connecting-ip': `203.0.113.${n}`});
  const stranger = () => randomUUID();
  const s1 = stranger();
  assert.equal((await post(pe, {install: s1, headers: ip(1)})).status, 202);
  assert.equal((await post(pe, {install: s1, headers: ip(1)})).status, 202);
  assert.equal((await post(pe, {install: s1, headers: ip(1)})).status, 429, 'per unknown install');
  assert.equal((await post(pe, {install: stranger(), headers: ip(1)})).status, 202);
  assert.equal((await post(pe, {install: stranger(), headers: ip(1)})).status, 202);
  assert.equal((await post(pe, {install: stranger(), headers: ip(1)})).status, 429, 'per network address');
  assert.equal((await post(pe, {install: stranger(), headers: ip(2)})).status, 202);
  assert.equal((await post(pe, {install: stranger(), headers: ip(3)})).status, 202);
  assert.equal((await post(pe, {install: stranger(), headers: ip(4)})).status, 503, 'the whole pending area is capped');
  const big = Buffer.concat([Buffer.from([0x1f, 0x8b]), randomBytes(PENDING_MAX_BODY)]);
  assert.equal((await post(env(), {install: stranger(), body: big})).status, 413, 'unknown installs: small batches only');
  assert.equal((await post(env({PENDING_MAX_ROWS: '0'}), {install: stranger()})).status, 401, 'pending area can be off');
  const rows = await pullAll(pe);
  assert.ok(rows.every((r) => r.known === 0 && r.token_hash.length === 64));
});

test('per-install caps: rate, rows and bytes, without counting the whole table (fixes 4 and 5)', async () => {
  const e = env({RATE_PER_HOUR: '3', MAX_ROWS_PER_INSTALL: '4', MAX_BYTES_PER_INSTALL: '100000'});
  const other = '01a11f49-8c0e-71e2-96f1-000000000001';
  await known(e, [{id: other, token_hash: hash(TOKEN + 'b')}]);
  for (let i = 0; i < 3; i++) assert.equal((await post(e)).status, 202);
  assert.equal((await post(e)).status, 429);
  assert.equal((await post(e, {}, NOW + 3601)).status, 202, 'the next hour');
  assert.equal((await post(e, {}, NOW + 3602)).status, 503, 'rows cap for this install only');
  assert.equal((await post(e, {install: other, token: TOKEN + 'b'})).status, 202, 'other installs are not affected');
  const big = Buffer.concat([Buffer.from([0x1f, 0x8b]), randomBytes(99990)]);
  assert.equal((await post(e, {install: other, token: TOKEN + 'b', body: big})).status, 503, 'bytes cap');
  e.DB.log.length = 0;
  await post(e, {install: other, token: TOKEN + 'b'}, NOW + 7200);
  assert.ok(e.DB.log.length <= 3, 'ingest is at most 3 queries');
  for (const sql of e.DB.log) {
    assert.doesNotMatch(sql.replace(/\s+/g, ' '), /COUNT\(\*\)[^]*FROM inbox(?! WHERE)/i, 'never COUNT(*) over the whole table');
  }
  const plan = e.DB.raw.prepare('EXPLAIN QUERY PLAN SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS bytes, '
    + 'COALESCE(SUM(received_at > ?), 0) AS hour FROM inbox WHERE install_id = ?').all(1, other);
  assert.match(JSON.stringify(plan), /inbox_install/, 'the per-install count uses the index');
});

test('ack deletes in batched statements within D1 limits (fix 3)', async () => {
  const e = env({RATE_PER_HOUR: '1000', MAX_ROWS_PER_INSTALL: '1000'});
  await known(e);
  for (let i = 0; i < 250; i++) await post(e);
  const ids = e.DB.raw.prepare('SELECT id FROM inbox').all().map((r) => r.id);
  e.DB.log.length = 0;
  const r = await call(e, '/ack', {method: 'POST', headers: auth(), body: JSON.stringify({ids})});
  assert.equal((await r.json()).deleted, 250);
  assert.equal(e.DB.log.length, 3, '250 ids = 3 statements (100 + 100 + 50)');
  const max = ids.concat(Array.from({length: 250}, () => randomUUID()));
  e.DB.log.length = 0;
  await call(e, '/ack', {method: 'POST', headers: auth(), body: JSON.stringify({ids: max})});
  assert.ok(e.DB.log.length <= 50, 'the largest ack (500 ids) stays under 50 queries');
  assert.equal((await call(e, '/ack', {method: 'POST', headers: auth(), body: JSON.stringify({ids: max.concat(['x'])})})).status, 400);
});

test('the Control Center syncs installs within D1 limits; parked batches become known', async () => {
  const e = env();
  const s = randomUUID();
  assert.equal((await post(e, {install: s})).status, 202);
  const list = Array.from({length: 1000}, (_, i) => ({id: randomUUID(), token_hash: hash('t' + i)}));
  list.push({id: s, token_hash: hash(TOKEN)});
  assert.equal((await register(e, list)).status, 413, 'more than 1000 per call is refused');
  list.splice(0, 1);
  e.DB.log.length = 0;
  const r = await register(e, list);
  assert.equal(r.status, 200);
  assert.ok(e.DB.log.length <= 50, `sync used ${e.DB.log.length} queries`);
  assert.equal((await pullAll(e))[0].known, 1, 'the PC was registered: its parked batch left the pending area');
  assert.equal((await register(e, [{id: s, token_hash: hash(TOKEN)}])).status, 200);
  assert.equal(e.DB.raw.prepare('SELECT COUNT(*) AS n FROM installs').get().n, 1, 'removed installs disappear');
  assert.equal((await register(e, [{id: 'x', token_hash: 'y'}])).status, 400);
  assert.equal((await call(e, '/installs', {method: 'POST', body: '{}'})).status, 401);
});

test('pull, ack and installs need the bearer token; misc', async () => {
  const e = env();
  assert.equal((await call(e, '/pull')).status, 401);
  assert.equal((await call(e, '/pull', {headers: auth('wrong')})).status, 401);
  assert.equal((await call(env({RELAY_PULL_TOKEN: ''}), '/pull', {headers: auth('')})).status, 401, 'no token set: closed');
  assert.equal((await call(e, '/ack', {method: 'POST', headers: auth(), body: '{"ids": "x"}'})).status, 400);
  assert.equal((await call(e, '/nope')).status, 404);
  assert.equal((await post(e, {body: Buffer.from('plain json')})).status, 400);
  await known(e);
  const big = Buffer.concat([Buffer.from([0x1f, 0x8b]), randomBytes(MAX_BODY)]);
  assert.equal((await post(e, {body: big})).status, 413);
  assert.equal(same('abc', 'abc'), true);
  assert.equal(same('abc', 'abd'), false);
  assert.equal(same('abc', 'abcd'), false);
  assert.equal(await sha256hex('abc'), hash('abc'));
});

test('clean-up removes anything older than 14 days, even if KEEP_DAYS says more', async () => {
  const e = env({KEEP_DAYS: '90'});
  await known(e);
  assert.equal((await post(e, {}, NOW)).status, 202);
  assert.equal(await cleanup(e, NOW + 13 * 86400), 0);
  assert.equal(await cleanup(e, NOW + 15 * 86400), 1);
});

test('no secrets in the template', () => {
  const toml = readFileSync(new URL('../wrangler.toml', import.meta.url), 'utf8');
  assert.match(toml, /REPLACE_WITH_YOUR_D1_DATABASE_ID/);
  assert.doesNotMatch(toml, /RELAY_PULL_TOKEN\s*=/);
});
