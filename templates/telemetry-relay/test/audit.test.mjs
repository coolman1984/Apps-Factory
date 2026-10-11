// Run: node --experimental-sqlite --test test/audit.test.mjs   (Node 22.13+). The owner's phone audit mirror (src/audit.js):
// admin token only, hash chain checked on arrival, append-only, bounded, nothing private. D1 is the node:sqlite shim of d1.mjs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash, randomUUID} from 'node:crypto';
import {d1} from './d1.mjs';
import worker from '../src/worker.js';
import {GENESIS, canonical} from '../src/audit.js';
import {cleanup} from '../src/worker.js';
import {cleanupLicence} from '../src/licence.js';

const NOW = 1_800_000_000;
const ADMIN = 'admin-secret-' + 'x'.repeat(20);
const PULL = 'pull-secret-' + 'y'.repeat(20);
const admin = {authorization: 'Bearer ' + ADMIN};

const env = (extra = {}) => ({DB: d1(), LICENCE_ADMIN_TOKEN: ADMIN, RELAY_PULL_TOKEN: PULL, ...extra});
const call = (e, path, init = {}, now = NOW) => worker.fetch(new Request('https://relay.example' + path, init), e, {}, now);
const post = (e, body, headers = admin, now = NOW) => call(e, '/audit/append', {method: 'POST', body: typeof body === 'string' ? body : JSON.stringify(body), headers: {'content-type': 'application/json', ...headers}}, now);
const recent = (e, query = '', headers = admin) => call(e, '/audit/recent' + query, {headers});

const sha = (previousHex, text) => createHash('sha256').update(Buffer.from(previousHex, 'hex')).update(Buffer.from(text, 'utf8')).digest('hex');

// An entry in the phone's fixed 27-field order (AuditCanonical.bytes).
const entryFields = (o = {}) => [
  1, o.eventId ?? randomUUID(), o.chainId, o.sequence, o.device, 'owner', o.workspace ?? randomUUID(), null, o.at ?? 1700000000000,
  '2023-11-15T00:13:20+02:00', 7200, 'Africa/Cairo', o.screen ?? 'notebook', o.action ?? 'create', o.entityType ?? 'customer', o.entityId ?? randomUUID(),
  o.before ?? {}, o.after ?? {revision: 1}, o.result ?? 'success', o.reason ?? null,
  o.ar ?? 'تم إنشاء العميل.', o.en ?? 'Customer was created.', 1, o.correlation ?? randomUUID(), null, null, 1,
];
const chain = () => ({chainId: randomUUID(), device: randomUUID(), last: GENESIS, sequence: 0});
// Builds the request body for the next entry of a chain; `over` can break any field.
function next(c, over = {}, commit = true) {
  const sequence = over.sequence ?? c.sequence + 1;
  const text = over.text ?? canonical(entryFields({chainId: c.chainId, device: c.device, sequence, ...over}));
  const previousHash = over.previousHash ?? c.last;
  const entryHash = over.entryHash ?? sha(previousHash, text);
  if (commit) { c.last = entryHash; c.sequence = sequence; }
  return {entry: text, previousHash, entryHash};
}
const rows = (e) => e.DB.raw.prepare('SELECT COUNT(*) AS n FROM owner_audit').get().n;

test('the phone\'s golden entry is accepted byte for byte, and a replay answers 200', async () => {
  const e = env();
  const golden = JSON.parse((await import('node:fs')).readFileSync(new URL('./audit-golden-v1.json', import.meta.url), 'utf8'));
  assert.equal(canonical(JSON.parse(golden.canonical)), golden.canonical);
  assert.equal(sha(golden.previousHash, golden.canonical), golden.entryHash);
  const body = {entry: golden.canonical, previousHash: golden.previousHash, entryHash: golden.entryHash};
  const r = await post(e, body);
  assert.equal(r.status, 201);
  const a = await r.json();
  assert.deepEqual([a.sequence, a.entryHash, a.replay, a.receivedAt], [1, golden.entryHash, false, NOW]);
  const again = await post(e, body, admin, NOW + 50);
  assert.equal(again.status, 200);
  const b = await again.json();
  assert.deepEqual([b.replay, b.receivedAt], [true, NOW]);
  assert.equal(rows(e), 1);
});

test('a chain grows one entry at a time and is read back newest first with a cursor', async () => {
  const e = env();
  const c = chain();
  for (let i = 0; i < 5; i++) assert.equal((await post(e, next(c))).status, 201);
  const page = await (await recent(e, `?chainId=${c.chainId}&limit=2`)).json();
  assert.deepEqual(page.entries.map((x) => x.sequence), [5, 4]);
  assert.deepEqual(page.head, {sequence: 5, entryHash: c.last});
  assert.deepEqual(page.nextCursor, {beforeSequence: 4});
  const rest = await (await recent(e, `?chainId=${c.chainId}&beforeSequence=4&limit=50`)).json();
  assert.deepEqual(rest.entries.map((x) => x.sequence), [3, 2, 1]);
  assert.equal(rest.nextCursor, null);
  // the stored bytes hash to the stored hash, and each link points at the one before it
  const all = [...page.entries, ...rest.entries].reverse();
  all.forEach((x, i) => {
    assert.equal(sha(x.previousHash, x.entry), x.entryHash);
    assert.equal(x.previousHash, i === 0 ? GENESIS : all[i - 1].entryHash);
  });
  const empty = await (await recent(e, `?chainId=${randomUUID()}`)).json();
  assert.deepEqual([empty.entries, empty.head, empty.nextCursor], [[], {sequence: 0, entryHash: GENESIS}, null]);
});

test('every audit route needs the admin token: missing, empty, wrong, and the pull token are all refused before D1 is touched', async () => {
  const c = chain();
  for (const headers of [{}, {authorization: 'Bearer '}, {authorization: 'Bearer nope'}, {authorization: 'Bearer ' + PULL}, {authorization: ADMIN}]) {
    const e = env();
    assert.equal((await post(e, next(c, {}, false), headers)).status, 401);
    assert.equal((await recent(e, `?chainId=${c.chainId}`, headers)).status, 401);
    assert.equal(e.DB.log.length, 0, 'a stranger never reaches D1');
  }
  // an unset admin secret refuses everyone, even a request with an empty bearer
  const none = env({LICENCE_ADMIN_TOKEN: ''});
  assert.equal((await post(none, next(c, {}, false), {authorization: 'Bearer '})).status, 401);
  assert.equal((await post(none, next(c, {}, false), admin)).status, 401);
  // and the admin token does not open the pull routes
  assert.equal((await call(env(), '/pull', {headers: admin})).status, 401);
});

test('wrong methods and unknown routes', async () => {
  const e = env();
  assert.equal((await call(e, '/audit/append', {headers: admin})).status, 405);
  assert.equal((await call(e, '/audit/recent', {method: 'POST', headers: admin, body: '{}'})).status, 405);
  assert.equal((await call(e, '/audit/recent', {method: 'DELETE', headers: admin})).status, 405);
  assert.equal((await call(e, '/audit/other', {headers: admin})).status, 404);
  assert.equal((await call(e, '/audit/', {headers: admin})).status, 404);
});

test('bodies: bad JSON, unknown keys, missing fields, oversize and chunked oversize are refused', async () => {
  const e = env();
  const c = chain();
  const ok = next(c, {}, false);
  assert.equal((await post(e, '{not json')).status, 400);
  assert.equal((await post(e, '[]')).status, 400);
  assert.equal((await post(e, {...ok, extra: 1})).status, 400);
  assert.equal((await post(e, {entry: ok.entry, previousHash: ok.previousHash})).status, 400);
  assert.equal((await post(e, {...ok, previousHash: 'AB'.repeat(32)})).status, 400);
  assert.equal((await post(e, {...ok, entry: 5})).status, 400);
  assert.equal((await post(e, 'x'.repeat(41 * 1024))).status, 413);
  const stream = new ReadableStream({start(ctl) { for (let i = 0; i < 50; i++) ctl.enqueue(new Uint8Array(1024).fill(120)); ctl.close(); }});
  const chunked = await call(e, '/audit/append', {method: 'POST', body: stream, duplex: 'half', headers: admin});
  assert.equal(chunked.status, 413);
  const big = next(chain(), {before: {}, ar: 'ا'.repeat(300), en: 'e'.repeat(300)}, false);
  assert.equal(JSON.parse(big.entry).length, 27);
  assert.equal(rows(e), 0);
});

test('an entry is accepted only in the phone\'s exact canonical form', async () => {
  const e = env();
  const c = chain();
  const fields = entryFields({chainId: c.chainId, device: c.device, sequence: 1});
  const good = canonical(fields);
  const variants = {
    spaces: JSON.stringify(fields, null, 1),
    float: good.replace('1700000000000', '1700000000000.0'),
    exponent: good.replace('1700000000000', '17e11'),
    negativeZero: good.replace(',7200,', ',-0,'),
    hugeInt: good.replace('1700000000000', '9007199254740993'),
    unsortedKeys: good.replace('{"revision":1}', '{"revision":1,"deleted":false}'),
    duplicateKey: good.replace('{"revision":1}', '{"revision":1,"revision":2}'),
    escapedAscii: good.replace('"owner"', '"\\u006fwner"'),
  };
  for (const [name, text] of Object.entries(variants)) {
    const r = await post(e, {entry: text, previousHash: GENESIS, entryHash: sha(GENESIS, text)});
    assert.equal(r.status, 400, name);
  }
  assert.equal(rows(e), 0);
  // NFC: a decomposed string is refused, because the phone would have hashed the composed one
  const decomposed = good.replace('تم إنشاء العميل.', 'Café');
  assert.equal((await post(e, {entry: decomposed, previousHash: GENESIS, entryHash: sha(GENESIS, decomposed)})).status, 400);
});

test('the entry must be a well-formed audit entry: shape, versions, ids, words, results, actor, zone', async () => {
  const c = chain();
  const mutate = (i, value) => { const f = entryFields({chainId: c.chainId, device: c.device, sequence: 1}); f[i] = value; return canonical(f); };
  const cases = {
    shortArray: canonical(entryFields({chainId: c.chainId, device: c.device, sequence: 1}).slice(0, 26)),
    notArray: '{"a":1}',
    schemaVersion: mutate(0, 2), canonicalVersion: mutate(26, 2), templateVersion: mutate(22, 2),
    badEventId: mutate(1, 'not-a-uuid'), badDevice: mutate(4, 'X'), badCorrelation: mutate(23, null),
    sequenceZero: mutate(3, 0), sequenceFloat: mutate(3, 1.5), negativeTime: mutate(8, -1),
    actor: mutate(5, 'admin'), zone: mutate(11, 'UTC'), cairoTime: mutate(9, 'yesterday'),
    screenUpper: mutate(12, 'Notebook'), actionEmpty: mutate(13, ''), entityLong: mutate(14, 'a'.repeat(41)),
    result: mutate(18, 'ok'), reason: mutate(19, 'Bad Reason!'), emptyArabic: mutate(20, ''), longEnglish: mutate(21, 'e'.repeat(401)),
  };
  for (const [name, text] of Object.entries(cases)) {
    const e = env();
    const r = await post(e, {entry: text, previousHash: GENESIS, entryHash: sha(GENESIS, text)});
    assert.equal(r.status, 400, name);
    assert.equal(rows(e), 0, name);
  }
});

test('nothing private gets in: unknown keys, nested values, secrets, licence codes and long hex are refused; redacted markers are fine', async () => {
  const c = chain();
  const tryAfter = async (after, over = {}) => {
    const e = env();
    return (await post(e, next(chain(), {after, ...over}, false))).status;
  };
  assert.equal(await tryAfter({revision: 2, localStatus: 'active', phone: '[redacted]', name: '[redacted]', amountMinor: '[redacted]'}), 201);
  assert.equal(await tryAfter({phone: '01001234567'}), 400);
  assert.equal(await tryAfter({token: 'abc'}), 400);
  assert.equal(await tryAfter({customerName: 'Mohamed'}), 400);
  assert.equal(await tryAfter({revision: 1.5}), 400);
  assert.equal(await tryAfter({revision: {deep: 1}}), 400);
  assert.equal(await tryAfter({status: ['a']}), 400);
  assert.equal(await tryAfter({status: 'Bearer abcdefghijklmnop'}), 400);
  assert.equal(await tryAfter({status: '-----BEGIN PRIVATE KEY-----'}), 400);
  assert.equal(await tryAfter({source: 'ABCDEF-GHJKMN-PQRSTV-WXYZ23-ABCDEF'}), 400);
  assert.equal(await tryAfter({status: 'ab'.repeat(40)}), 400);
  assert.equal(await tryAfter({status: 'x'.repeat(201)}), 400);
  assert.equal(await tryAfter({}, {before: {key: 'visible'}}), 400);
  assert.equal(await tryAfter({}, {ar: 'ABCDEF-GHJKMN-PQRSTV-WXYZ23-ABCDEF'}), 400);
  assert.equal(await tryAfter({}, {entityId: 'lp_' + 'a'.repeat(48)}), 400);
  assert.equal(c.sequence, 0);
});

test('hashes: a wrong, swapped or mutated hash is refused; sequence 1 needs the genesis hash', async () => {
  const e = env();
  const c = chain();
  const a = next(c, {}, false);
  assert.equal((await post(e, {...a, entryHash: '0'.repeat(64)})).status, 400);
  assert.equal((await post(e, {...a, entry: a.entry.replace('success', 'failure')})).status, 400);
  const other = 'ab'.repeat(32);
  assert.equal((await post(e, next(c, {previousHash: other}, false))).status, 400, 'sequence 1 with a non-genesis previous hash');
  assert.equal((await post(e, a)).status, 201);
  assert.equal(rows(e), 1);
});

test('no gap, no fork, no wrong predecessor, and a different device cannot extend a chain', async () => {
  const e = env();
  const c = chain();
  const first = next(c);
  assert.equal((await post(e, first)).status, 201);
  const second = next(c);
  // a gap: sequence 3 before 2
  const skipping = {...c};
  const gap = next(skipping, {sequence: 3});
  const r = await post(e, gap);
  assert.equal(r.status, 409);
  assert.deepEqual((await r.json()).head, {sequence: 1, entryHash: first.entryHash});
  assert.equal((await post(e, second)).status, 201);
  // a fork: another entry for sequence 2 with the right predecessor but a different event
  const forkChain = {chainId: c.chainId, device: c.device, last: first.entryHash, sequence: 1};
  const fork = next(forkChain);
  const forked = await post(e, fork);
  assert.equal(forked.status, 409);
  assert.deepEqual((await forked.json()).head, {sequence: 2, entryHash: second.entryHash});
  // a wrong predecessor hash for sequence 3
  const wrong = next({...c}, {previousHash: first.entryHash});
  assert.equal((await post(e, wrong)).status, 409);
  // a different device (same chain id) cannot extend the chain even with the right hash
  const thief = next({...c, device: randomUUID()});
  assert.equal((await post(e, thief)).status, 409);
  // a new chain id must start at sequence 1
  const lonely = chain();
  assert.equal((await post(e, next(lonely, {sequence: 2, previousHash: first.entryHash}))).status, 409);
  assert.equal(rows(e), 2);
});

test('a known event id with different content is a conflict, an identical one is a replay', async () => {
  const e = env();
  const c = chain();
  const a = next(c);
  const eventId = JSON.parse(a.entry)[1];
  assert.equal((await post(e, a)).status, 201);
  assert.equal((await post(e, a)).status, 200);
  const other = chain();
  const reuse = next(other, {eventId});
  assert.equal((await post(e, reuse)).status, 409);
  const sameChainReuse = next({...c, last: a.entryHash, sequence: 1}, {eventId});
  assert.equal((await post(e, sameChainReuse)).status, 409);
  assert.equal(rows(e), 1);
});

test('concurrent writers cannot fork a chain', async () => {
  const e = env();
  const c = chain();
  assert.equal((await post(e, next(c))).status, 201);
  const racers = [];
  for (let i = 0; i < 8; i++) racers.push(post(e, next({...c}, {}, false)));
  const statuses = (await Promise.all(racers)).map((r) => r.status).sort();
  assert.deepEqual(statuses, [201, 409, 409, 409, 409, 409, 409, 409]);
  assert.equal((await (await recent(e, `?chainId=${c.chainId}`)).json()).head.sequence, 2);
});

test('recent: chain id and cursor are validated, the limit is bounded, nothing is private in the answer', async () => {
  const e = env();
  const c = chain();
  for (let i = 0; i < 3; i++) await post(e, next(c));
  assert.equal((await recent(e)).status, 400);
  assert.equal((await recent(e, '?chainId=1')).status, 400);
  assert.equal((await recent(e, `?chainId=${c.chainId}&beforeSequence=0`)).status, 400);
  assert.equal((await recent(e, `?chainId=${c.chainId}&beforeSequence=-1`)).status, 400);
  assert.equal((await recent(e, `?chainId=${c.chainId}&beforeSequence=x`)).status, 400);
  const huge = await (await recent(e, `?chainId=${c.chainId}&limit=100000`)).json();
  assert.equal(huge.entries.length, 3);
  const one = await (await recent(e, `?chainId=${c.chainId}&limit=0`)).json();
  assert.equal(one.entries.length, 3, 'limit 0 falls back to the default, never to an unbounded read');
  const text = JSON.stringify(huge);
  for (const secret of [ADMIN, PULL, 'token_hash', 'poll_hash']) assert.ok(!text.includes(secret));
  assert.deepEqual(Object.keys(huge.entries[0]).sort(), ['entry', 'entryHash', 'eventId', 'previousHash', 'receivedAt', 'sequence']);
});

test('bounds: the number of chains and the length of one chain are capped', async () => {
  const e = env({AUDIT_MAX_CHAINS: '2', AUDIT_MAX_SEQUENCE: '3'});
  const [a, b, c] = [chain(), chain(), chain()];
  assert.equal((await post(e, next(a))).status, 201);
  assert.equal((await post(e, next(b))).status, 201);
  assert.equal((await post(e, next(c))).status, 507);
  assert.equal((await post(e, next(a))).status, 201);
  assert.equal((await post(e, next(a))).status, 201);
  assert.equal((await post(e, next(a))).status, 507);
  assert.equal(rows(e), 4);
});

test('append-only: the database refuses UPDATE and DELETE, and no clean-up touches the table', async () => {
  const e = env();
  const c = chain();
  assert.equal((await post(e, next(c))).status, 201);
  assert.throws(() => e.DB.raw.prepare("UPDATE owner_audit SET result = 'failure'").run(), /append-only/);
  assert.throws(() => e.DB.raw.prepare('DELETE FROM owner_audit').run(), /append-only/);
  const later = NOW + 400 * 86400;
  await cleanup(e, later);
  await cleanupLicence(e, later);
  assert.equal(await worker.scheduled({}, e, {waitUntil: () => {}}), undefined);
  assert.equal(rows(e), 1);
});

test('D1 Free plan: an append touches D1 at most 4 times and a read twice', async () => {
  const e = env();
  const c = chain();
  await post(e, next(c));
  assert.ok(e.DB.log.length <= 4, `append used ${e.DB.log.length}`);
  e.DB.log.length = 0;
  await post(e, next(c));
  assert.ok(e.DB.log.length <= 3, `append used ${e.DB.log.length}`);
  e.DB.log.length = 0;
  await recent(e, `?chainId=${c.chainId}`);
  assert.equal(e.DB.log.length, 2);
  // the existing owner routes are unchanged by the shared admin helper
  assert.equal((await call(e, '/licence/pending', {headers: admin})).status, 200);
  assert.equal((await call(e, '/licence/pending', {headers: {authorization: 'Bearer ' + PULL}})).status, 401);
});
