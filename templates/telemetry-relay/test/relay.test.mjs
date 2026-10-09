// Run: node --experimental-sqlite --test test/   (Node 22+). D1 is replaced by a tiny shim over node:sqlite.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {gzipSync} from 'node:zlib';
import {randomBytes} from 'node:crypto';
import {DatabaseSync} from 'node:sqlite';
import worker, {cleanup, same, MAX_BODY} from '../src/worker.js';

function d1() {
  const db = new DatabaseSync(':memory:');
  db.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  const stmt = (sql, args = []) => ({
    bind: (...a) => stmt(sql, a),
    first: async () => db.prepare(sql).get(...args) ?? null,
    all: async () => ({results: db.prepare(sql).all(...args).map((r) => ({...r}))}),
    run: async () => ({meta: {changes: Number(db.prepare(sql).run(...args).changes)}}),
  });
  return {prepare: (sql) => stmt(sql)};
}

const NOW = 1_800_000_000;
const INSTALL = '01a11f49-8c0e-71e2-96f1-4ecf7b7751ca';
const env = (extra = {}) => ({DB: d1(), RELAY_PULL_TOKEN: 'pull-secret', ...extra});
const body = () => gzipSync(Buffer.from(JSON.stringify([{type: 'hb'}])));
const call = (e, path, init = {}, now = NOW) => worker.fetch(new Request('https://relay.example' + path, init), e, {}, now);
const post = (e, opts = {}) => call(e, '/ingest', {
  method: 'POST', body: opts.body ?? body(),
  headers: {'x-af-install': opts.install ?? INSTALL, 'x-af-timestamp': String(opts.ts ?? NOW),
    'x-af-nonce': opts.nonce ?? randomBytes(12).toString('hex'), 'x-af-signature': opts.sig ?? 'a'.repeat(64),
    ...(opts.headers || {})},
});
const auth = (t = 'pull-secret') => ({authorization: 'Bearer ' + t});

test('ingest stores a batch; pull returns it; ack deletes it', async () => {
  const e = env();
  const b = body();
  assert.equal((await post(e, {body: b, nonce: 'ab'.repeat(12)})).status, 202);
  const pulled = await (await call(e, '/pull?limit=10', {headers: auth()})).json();
  assert.equal(pulled.batches.length, 1);
  const row = pulled.batches[0];
  assert.deepEqual(Object.keys(row).sort(), ['body', 'id', 'install_id', 'nonce', 'sig', 'ts']);
  assert.deepEqual(Buffer.from(row.body, 'base64'), b, 'bytes kept exactly, so the signature still verifies');
  assert.equal(row.ts, NOW);
  const acked = await (await call(e, '/ack', {method: 'POST', headers: {...auth(), 'content-type': 'application/json'},
    body: JSON.stringify({ids: [row.id]})})).json();
  assert.equal(acked.deleted, 1);
  assert.equal((await (await call(e, '/pull', {headers: auth()})).json()).batches.length, 0);
});

test('ingest refuses bad headers, old clocks, non-gzip, oversize and replayed nonces', async () => {
  const e = env();
  assert.equal((await post(e, {install: 'not-a-uuid'})).status, 400);
  assert.equal((await post(e, {sig: 'xyz'})).status, 400);
  assert.equal((await post(e, {nonce: 'short'})).status, 400);
  assert.equal((await post(e, {ts: NOW - 301})).status, 401);
  assert.equal((await post(e, {body: Buffer.from('plain json')})).status, 400);
  const big = Buffer.concat([Buffer.from([0x1f, 0x8b]), randomBytes(MAX_BODY)]);
  assert.equal((await post(e, {body: big})).status, 413);
  assert.equal((await post(e, {nonce: 'cd'.repeat(12)})).status, 202);
  assert.equal((await post(e, {nonce: 'cd'.repeat(12)})).status, 409);
});

test('optional ingest key, per-install rate limit and a full mailbox', async () => {
  const keyed = env({RELAY_INGEST_KEY: 'k1'});
  assert.equal((await post(keyed)).status, 401);
  assert.equal((await post(keyed, {headers: {'x-af-relay-key': 'k1'}})).status, 202);
  const e = env({RATE_PER_HOUR: '3', MAX_ROWS: '4'});
  for (let i = 0; i < 3; i++) assert.equal((await post(e)).status, 202);
  assert.equal((await post(e)).status, 429);
  assert.equal((await post(e, {install: '01a11f49-8c0e-71e2-96f1-000000000001'})).status, 202);
  assert.equal((await post(e, {install: '01a11f49-8c0e-71e2-96f1-000000000002'})).status, 503);
});

test('pull and ack need the bearer token; ack validates ids', async () => {
  const e = env();
  assert.equal((await call(e, '/pull')).status, 401);
  assert.equal((await call(e, '/pull', {headers: auth('wrong')})).status, 401);
  assert.equal((await call(env({RELAY_PULL_TOKEN: ''}), '/pull', {headers: auth('')})).status, 401, 'no token set: closed');
  assert.equal((await call(e, '/ack', {method: 'POST', headers: auth(), body: '{"ids": "x"}'})).status, 400);
  assert.equal((await call(e, '/nope')).status, 404);
  assert.equal(same('abc', 'abc'), true);
  assert.equal(same('abc', 'abd'), false);
  assert.equal(same('abc', 'abcd'), false);
});

test('clean-up removes anything older than 14 days, even if KEEP_DAYS says more', async () => {
  const e = env({KEEP_DAYS: '90'});
  assert.equal((await post(e, {}, NOW)).status, 202);
  assert.equal(await cleanup(e, NOW + 13 * 86400), 0);
  assert.equal(await cleanup(e, NOW + 15 * 86400), 1);
});

test('no secrets in the template', () => {
  const toml = readFileSync(new URL('../wrangler.toml', import.meta.url), 'utf8');
  assert.match(toml, /REPLACE_WITH_YOUR_D1_DATABASE_ID/);
  assert.doesNotMatch(toml, /RELAY_PULL_TOKEN\s*=|RELAY_INGEST_KEY\s*=/);
});
