// The owner's phone audit mirror (Pixel Plus Owner M05): `/audit/*`, admin token only.
//
//   POST /audit/append  {entry, previousHash, entryHash}   one entry of the phone's hash chain
//   GET  /audit/recent  ?chainId=&beforeSequence=&limit=    newest first, with the chain head and a cursor
//
// `entry` is a STRING: the exact canonical bytes the phone hashed (a JSON array of 27 fields, UTF-8, keys sorted inside nested maps,
// no whitespace, integers only). The Worker never re-serialises what it stores: it hashes those bytes, parses them, checks every
// field, and refuses an entry whose canonical form differs from the bytes it was given. entryHash = sha256(previousHash as 32 raw
// bytes || entry bytes), the same rule as the phone (AuditCanonical in Mobile-App). The golden entry in the tests is the phone's.
//
// The chain can only grow: one conditional INSERT checks the predecessor (sequence n-1 with entryHash = previousHash and the same
// device) and the unique (chain_id, sequence) index settles a race, so two writers cannot fork a chain. An identical retry answers 200
// `replay: true`; anything different for a known event, a gap, a fork or a wrong predecessor answers 409 with the current head. There
// is no UPDATE or DELETE route and the daily clean-up never touches this table. Strangers never reach D1: the token is checked first.
//
// The mirror holds no customer name, phone, note, amount, token or code: unknown keys in the before/after maps, secret-looking text and
// long hex strings are refused (the phone already redacts; this is the second wall). A shared admin token is not a cryptographic
// identity: a stolen token can append to a chain that has no row yet, but cannot rewrite or extend a chain it cannot predict.
//
// D1 Free plan: append touches D1 at most 4 times; recent touches it 2 times; nothing counts a whole table.

import {adminOk, num, reply} from './common.js';

export const MAX_ENTRY_BYTES = 16 * 1024;          // the phone refuses a bigger canonical entry too
const MAX_BODY = 40 * 1024;                          // the entry is a JSON string inside JSON: escapes can double its size
const FIELD_COUNT = 27;
export const GENESIS = '0'.repeat(64);
const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;
const WORD = /^[a-z][a-z0-9_]{0,39}$/;
const RESULTS = ['intent', 'success', 'failure', 'cancelled', 'conflict'];
const SAFE_INT = (v) => Number.isSafeInteger(v);
const REDACTED = '[redacted]';

// Keys the phone may name in beforeSafe / afterSafe (AuditRedaction.ALLOWED_KEYS), and keys it keeps only to say "this changed".
const SAFE_KEYS = new Set(['revision', 'deleted', 'localStatus', 'fromStatus', 'toStatus', 'currency', 'productCode', 'displayName',
  'localTrialDays', 'remoteTrialDays', 'policyVersion', 'source', 'originEpoch', 'normalizedUrl', 'isDefault', 'remoteType', 'remoteId',
  'customerId', 'branchId', 'productId', 'hubProfileId', 'linkId', 'workspaceId', 'capabilitiesChanged', 'renamed', 'tested', 'reversal',
  'op', 'status', 'attempts', 'credentialEpoch', 'queuedCount', 'confirmedCount', 'blockedCount']);
const SENSITIVE_KEYS = new Set(['name', 'phone', 'note', 'body', 'text', 'reference', 'amount', 'amountminor', 'token', 'secret',
  'password', 'bearer', 'cookie', 'session', 'credential', 'authorization', 'code', 'licencecode', 'licensecode', 'key', 'privatekey',
  'exception', 'stack', 'message', 'email', 'address', 'searchtoken', 'normalizedsearchtoken', 'ciphertext']);
const LICENCE_CODE = /[0-9A-Z]{6}(?:-[0-9A-Z]{6}){3,}/;
const SECRET_TEXT = /bearer\s|begin [a-z ]*private|private key|lp_[0-9a-f]{16}/i;

const hex = (bytes) => Array.from(bytes, (b) => b.toString(16).padStart(2, '0')).join('');
const fromHex = (h) => Uint8Array.from(h.match(/../g), (x) => parseInt(x, 16));

export async function entryHash(previousHash, canonicalBytes) {
  const joined = new Uint8Array(32 + canonicalBytes.length);
  joined.set(fromHex(previousHash), 0);
  joined.set(canonicalBytes, 32);
  return hex(new Uint8Array(await crypto.subtle.digest('SHA-256', joined)));
}

// The phone's canonical form: arrays and objects with sorted keys, no whitespace, NFC strings, integers only.
export function canonical(v) {
  if (v === null) return 'null';
  if (typeof v === 'boolean') return v ? 'true' : 'false';
  if (typeof v === 'number') return String(v);
  if (typeof v === 'string') return JSON.stringify(v.normalize('NFC'));
  if (Array.isArray(v)) return `[${v.map(canonical).join(',')}]`;
  return `{${Object.keys(v).map((k) => k.normalize('NFC')).sort().map((k) => `${JSON.stringify(k)}:${canonical(v[k])}`).join(',')}}`;
}

const isText = (v, max) => typeof v === 'string' && v.length >= 1 && v.length <= max;
const isTextOrNull = (v, max) => v === null || isText(v, max);

function safeText(s) {
  return s.length <= 200 && !LICENCE_CODE.test(s) && !SECRET_TEXT.test(s) && !/^[0-9a-fA-F]{32,}$/.test(s);
}

// before/after: only allowlisted keys with plain values, or a sensitive key whose value is the marker; never nested.
function safeMap(m) {
  if (!m || typeof m !== 'object' || Array.isArray(m)) return false;
  const keys = Object.keys(m);
  if (keys.length > 24) return false;
  return keys.every((k) => {
    const v = m[k];
    if (SENSITIVE_KEYS.has(k.toLowerCase())) return v === REDACTED;
    if (!SAFE_KEYS.has(k)) return false;
    if (v === null || typeof v === 'boolean') return true;
    if (typeof v === 'number') return SAFE_INT(v);
    return typeof v === 'string' && safeText(v);
  });
}

// Checks the 27 fields in the phone's fixed order. Returns the parsed facts, or a short reason.
export function checkEntry(a) {
  if (!Array.isArray(a) || a.length !== FIELD_COUNT) return 'shape';
  const [schemaVersion, eventId, chainId, sequence, device, actor, workspace, profile, at, cairoIso, offset, zone, screen, action,
    entityType, entityId, before, after, result, reason, ar, en, templateVersion, correlation, original, operation, canonicalVersion] = a;
  if (schemaVersion !== 1 || canonicalVersion !== 1 || templateVersion !== 1) return 'version';
  if (![eventId, chainId, device, workspace, correlation].every((x) => typeof x === 'string' && UUID.test(x))) return 'ids';
  if (![profile, original, operation].every((x) => x === null || (typeof x === 'string' && UUID.test(x)))) return 'ids';
  if (!SAFE_INT(sequence) || sequence < 1 || !SAFE_INT(at) || at < 0 || !SAFE_INT(offset) || Math.abs(offset) > 18 * 3600) return 'numbers';
  if (actor !== 'owner' || zone !== 'Africa/Cairo') return 'actor';
  if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[+-]\d{2}:\d{2}$/.test(cairoIso)) return 'time';
  if (![screen, action, entityType].every((x) => typeof x === 'string' && WORD.test(x))) return 'words';
  if (!isTextOrNull(entityId, 80) || (entityId !== null && !safeText(entityId))) return 'entity';
  if (!safeMap(before) || !safeMap(after)) return 'unsafe';
  if (!RESULTS.includes(result)) return 'result';
  if (reason !== null && !(typeof reason === 'string' && /^[a-z0-9_]{1,40}$/.test(reason))) return 'reason';
  if (!isText(ar, 400) || !isText(en, 400) || !safeText(ar) || !safeText(en)) return 'explanation';
  return {eventId, chainId, sequence, device, at, screen, action, entityType, entityId, result};
}

async function readBounded(request, limit) {
  if (Number(request.headers.get('content-length') || 0) > limit) return null;
  if (!request.body) return new Uint8Array(0);
  const reader = request.body.getReader();
  const parts = [];
  let size = 0;
  for (;;) {
    const {done, value} = await reader.read();
    if (done) break;
    size += value.length;
    if (size > limit) { await reader.cancel(); return null; }   // a chunked body with no length is cut off as soon as it is too big
    parts.push(value);
  }
  const out = new Uint8Array(size);
  let at = 0;
  for (const p of parts) { out.set(p, at); at += p.length; }
  return out;
}

const headOf = (env, chainId) => env.DB.prepare('SELECT sequence, entry_hash FROM owner_audit WHERE chain_id = ? ORDER BY sequence DESC LIMIT 1').bind(chainId).first();
const headBody = (h) => (h ? {sequence: h.sequence, entryHash: h.entry_hash} : {sequence: 0, entryHash: GENESIS});

async function append(request, env, now) {
  const raw = await readBounded(request, MAX_BODY);
  if (raw === null) return reply({error: 'too large'}, 413, now);
  let d;
  try { d = JSON.parse(new TextDecoder('utf-8', {fatal: true}).decode(raw)); } catch { return reply({error: 'json'}, 400, now); }
  if (!d || typeof d !== 'object' || Array.isArray(d)) return reply({error: 'fields'}, 400, now);
  const keys = Object.keys(d).sort().join(',');
  if (keys !== 'entry,entryHash,previousHash' || typeof d.entry !== 'string' || !HASH.test(d.previousHash) || !HASH.test(d.entryHash)) {
    return reply({error: 'fields'}, 400, now);
  }
  const bytes = new TextEncoder().encode(d.entry);
  if (bytes.length > MAX_ENTRY_BYTES) return reply({error: 'entry too large'}, 413, now);
  let parsed;
  try { parsed = JSON.parse(d.entry); } catch { return reply({error: 'entry'}, 400, now); }
  if (canonical(parsed) !== d.entry) return reply({error: 'not canonical'}, 400, now);   // floats, spaces, unsorted keys: refused, never fixed
  const facts = checkEntry(parsed);
  if (typeof facts === 'string') return reply({error: 'entry', reason: facts}, 400, now);
  if (await entryHash(d.previousHash, bytes) !== d.entryHash) return reply({error: 'hash'}, 400, now);
  if (facts.sequence === 1 && d.previousHash !== GENESIS) return reply({error: 'genesis'}, 400, now);
  if (facts.sequence > num(env.AUDIT_MAX_SEQUENCE, 200000)) return reply({error: 'full'}, 507, now);

  // query 1: a known event is a replay (identical) or a conflict (anything else)
  const known = await env.DB.prepare('SELECT chain_id, sequence, entry_hash, received_at FROM owner_audit WHERE event_id = ?').bind(facts.eventId).first();
  if (known) {
    const same = known.chain_id === facts.chainId && known.sequence === facts.sequence && known.entry_hash === d.entryHash;
    if (!same) return reply({error: 'conflict', head: headBody(await headOf(env, facts.chainId))}, 409, now);
    return reply({eventId: facts.eventId, sequence: known.sequence, entryHash: known.entry_hash, receivedAt: known.received_at, replay: true}, 200, now);
  }
  if (facts.sequence === 1) {
    // a new chain: the number of chains is capped, counted on a small partial index (rows with sequence 1), never on the table
    const chains = await env.DB.prepare('SELECT COUNT(*) AS n FROM owner_audit WHERE sequence = 1').first();
    if (chains.n >= num(env.AUDIT_MAX_CHAINS, 50)) return reply({error: 'full'}, 507, now);
  }
  // query 2: one conditional insert. Sequence 1 needs a chain with no rows; n > 1 needs row n-1 from the same device whose hash is previousHash.
  let added;
  try {
    added = await env.DB.prepare('INSERT INTO owner_audit (event_id, chain_id, sequence, device_instance_id, occurred_at_utc_ms, received_at, screen, action, '
      + 'entity_type, entity_id, result, canonical_json, previous_hash, entry_hash) '
      + 'SELECT ?,?,?,?,?,?,?,?,?,?,?,?,?,? WHERE (? = 1 AND NOT EXISTS (SELECT 1 FROM owner_audit WHERE chain_id = ?)) '
      + 'OR (? > 1 AND EXISTS (SELECT 1 FROM owner_audit WHERE chain_id = ? AND sequence = ? - 1 AND entry_hash = ? AND device_instance_id = ?))')
      .bind(facts.eventId, facts.chainId, facts.sequence, facts.device, facts.at, now, facts.screen, facts.action, facts.entityType, facts.entityId,
        facts.result, d.entry, d.previousHash, d.entryHash,
        facts.sequence, facts.chainId, facts.sequence, facts.chainId, facts.sequence, d.previousHash, facts.device).run();
  } catch {
    added = {meta: {changes: 0}};   // the unique index (chain_id, sequence) or the event id lost a race: the loser reads the head and retries
  }
  if (!added.meta.changes) return reply({error: 'conflict', head: headBody(await headOf(env, facts.chainId))}, 409, now);
  return reply({eventId: facts.eventId, sequence: facts.sequence, entryHash: d.entryHash, receivedAt: now, replay: false}, 201, now);
}

async function recent(env, url, now) {
  const chainId = url.searchParams.get('chainId') || '';
  if (!UUID.test(chainId)) return reply({error: 'chainId'}, 400, now);
  const limit = Math.min(100, Math.max(1, Math.floor(num(url.searchParams.get('limit'), 50)) || 50));
  const beforeRaw = url.searchParams.get('beforeSequence');
  const before = beforeRaw === null ? Number.MAX_SAFE_INTEGER : Number(beforeRaw);
  if (!Number.isSafeInteger(before) || before < 1 || (beforeRaw !== null && !/^\d{1,15}$/.test(beforeRaw))) return reply({error: 'beforeSequence'}, 400, now);
  // query 1 and 2: the head, then one page; limit + 1 rows tell whether there is a next page without counting anything
  const head = await headOf(env, chainId);
  const {results} = await env.DB.prepare('SELECT event_id, sequence, canonical_json, previous_hash, entry_hash, received_at FROM owner_audit '
    + 'WHERE chain_id = ? AND sequence < ? ORDER BY sequence DESC LIMIT ?').bind(chainId, before, limit + 1).all();
  const page = results.slice(0, limit);
  return reply({
    chainId, head: headBody(head),
    entries: page.map((r) => ({eventId: r.event_id, sequence: r.sequence, entry: r.canonical_json, previousHash: r.previous_hash, entryHash: r.entry_hash, receivedAt: r.received_at})),
    nextCursor: results.length > limit ? {beforeSequence: page[page.length - 1].sequence} : null,
  }, 200, now);
}

// Returns a Response for /audit/* paths, or null for everything else.
export async function handleAudit(request, env, now, url) {
  if (!url.pathname.startsWith('/audit/')) return null;
  const route = `${request.method} ${url.pathname}`;
  const known = ['POST /audit/append', 'GET /audit/recent'];
  if (!['/audit/append', '/audit/recent'].includes(url.pathname)) return reply({error: 'not found'}, 404);
  if (!adminOk(request, env)) return reply({error: 'unauthorised'}, 401);   // before the method: a stranger learns nothing
  if (!known.includes(route)) return reply({error: 'method'}, 405);
  return route === 'POST /audit/append' ? append(request, env, now) : recent(env, url, now);
}
