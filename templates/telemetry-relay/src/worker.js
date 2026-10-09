// Telemetry relay (Cloudflare Worker + D1). A mailbox between installed products and the Control Center:
// products POST gzip batches to /ingest with their install token; the Control Center pulls them with GET /pull and
// deletes them with POST /ack. The relay never opens a batch. The Control Center checks every token, every event id
// (duplicates are ignored) and every privacy rule again when it pulls.
//
// Protocol 2 (Apps-Factory 0.9.0): `Authorization: Bearer <install token>` over HTTPS, `X-AF-Install` (UUID),
// optional `X-AF-Sent-At` (the PC's clock, seconds). No signature, nonce or time window: a wrong PC clock is never a
// refusal, and every answer carries `server_time` so the PC can correct itself.
//
// Strangers are refused cheaply. The Control Center pushes the list of installs (id + sha256 of the token, never the
// token) with POST /installs. A known install with the right token gets per-install caps (rate, rows, bytes); a wrong
// token is refused after ONE lookup. An unknown install (a new PC nobody registered yet) may park a few small batches
// in a small shared "pending" area, so a new PC loses nothing; the owner approves it on the dashboard.
//
// D1 Free plan: at most 50 queries per invocation and 100 bound parameters per query. /ingest uses 3 queries, /ack
// deletes 100 ids per statement, /installs writes 25 rows per statement (at most 1000 installs per call), and nothing
// counts the whole table.
//
// Bindings (wrangler.toml): DB (D1). Secret (wrangler secret put, never in git): RELAY_PULL_TOKEN (required).
// Vars: RATE_PER_HOUR, MAX_ROWS_PER_INSTALL, MAX_BYTES_PER_INSTALL, PENDING_MAX_ROWS, PENDING_PER_INSTALL,
// PENDING_PER_SOURCE, KEEP_DAYS.

import {reply, num, same, sha256hex, bearer} from './common.js';
import {cleanupLicence, handleLicence} from './licence.js';
export {same, sha256hex};

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;
export const MAX_BODY = 512 * 1024;            // same limit as the Control Center
export const PENDING_MAX_BODY = 64 * 1024;     // an unregistered PC may only park small batches
export const MAX_INSTALLS_PER_SYNC = 1000;     // 40 upserts of 25 rows + 2 statements < 50 queries
const UPSERT_ROWS = 25;                        // 3 parameters per row: 75 < 100
const ACK_CHUNK = 100;

function b64(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

async function readBody(request, limit) {
  const declared = Number(request.headers.get('content-length') || 0);
  if (declared > limit) return {error: 'too large', status: 413};
  const body = new Uint8Array(await request.arrayBuffer());
  if (!body.length) return {error: 'empty', status: 400};
  if (body.length > limit) return {error: 'too large', status: 413};
  if (body[0] !== 0x1f || body[1] !== 0x8b) return {error: 'not gzip', status: 400};
  return {body};
}

async function ingest(request, env, now) {
  const h = request.headers;
  const install = h.get('x-af-install') || '', token = bearer(h);
  const sentRaw = h.get('x-af-sent-at');
  const sentAt = sentRaw === null ? null : Number(sentRaw);
  if (!UUID.test(install) || (sentAt !== null && !Number.isInteger(sentAt))) return reply({error: 'headers'}, 400, now);
  if (token.length < 16 || token.length > 200) return reply({error: 'install token required'}, 401, now);
  const hashed = await sha256hex(token);
  // query 1: who is this?
  const known = await env.DB.prepare('SELECT token_hash FROM installs WHERE id = ?').bind(install).first();
  if (known && !same(known.token_hash, hashed)) return reply({error: 'token'}, 401, now);   // stranger: one lookup, done
  const read = await readBody(request, known ? MAX_BODY : PENDING_MAX_BODY);
  if (read.error) return reply({error: read.error}, read.status, now);
  const size = read.body.length;
  if (known) {
    // query 2: this install's own rows only (index install_id, received_at); never the whole table
    const mine = await env.DB.prepare('SELECT COUNT(*) AS n, COALESCE(SUM(size), 0) AS bytes, '
      + 'COALESCE(SUM(received_at > ?), 0) AS hour FROM inbox WHERE install_id = ?').bind(now - 3600, install).first();
    if (mine.hour >= num(env.RATE_PER_HOUR, 120)) return reply({error: 'rate'}, 429, now);
    if (mine.n >= num(env.MAX_ROWS_PER_INSTALL, 2000) || mine.bytes + size > num(env.MAX_BYTES_PER_INSTALL, 20 * 1024 * 1024)) {
      return reply({error: 'full'}, 503, now);   // the product keeps it in its outbox and tries later
    }
  } else {
    const cap = num(env.PENDING_MAX_ROWS, 200);
    if (cap === 0) return reply({error: 'unknown install'}, 401, now);
    const src = await sha256hex(`${h.get('cf-connecting-ip') || '-'}|${Math.floor(now / 86400)}`);   // daily-salted
    // query 2: the small pending area only (index known, src)
    const p = await env.DB.prepare('SELECT COUNT(*) AS n, COALESCE(SUM(install_id = ?), 0) AS mine, '
      + 'COALESCE(SUM(src = ?), 0) AS here FROM inbox WHERE known = 0').bind(install, src.slice(0, 16)).first();
    if (p.n >= cap) return reply({error: 'pending area full'}, 503, now);
    if (p.mine >= num(env.PENDING_PER_INSTALL, 5) || p.here >= num(env.PENDING_PER_SOURCE, 10)) return reply({error: 'rate'}, 429, now);
    await env.DB.prepare('INSERT INTO inbox (id, install_id, known, token_hash, src, sent_at, size, body, received_at) '
      + 'VALUES (?,?,0,?,?,?,?,?,?)').bind(crypto.randomUUID(), install, hashed, src.slice(0, 16), sentAt, size, b64(read.body), now).run();
    return reply({ok: true, pending: true}, 202, now);
  }
  // query 3
  await env.DB.prepare('INSERT INTO inbox (id, install_id, known, token_hash, src, sent_at, size, body, received_at) '
    + 'VALUES (?,?,1,?,NULL,?,?,?,?)').bind(crypto.randomUUID(), install, hashed, sentAt, size, b64(read.body), now).run();
  return reply({ok: true}, 202, now);
}

function pullAuth(request, env) {
  return !!env.RELAY_PULL_TOKEN && same(bearer(request.headers), env.RELAY_PULL_TOKEN);
}

async function pull(url, env) {
  const limit = Math.min(100, Math.max(1, Math.floor(num(url.searchParams.get('limit'), 100)) || 100));
  const {results} = await env.DB.prepare('SELECT id, install_id, known, token_hash, sent_at, received_at, size, body '
    + 'FROM inbox ORDER BY received_at LIMIT ?').bind(limit).all();
  return reply({batches: results});
}

async function ack(request, env) {
  let ids;
  try { ({ids} = await request.json()); } catch { return reply({error: 'json'}, 400); }
  if (!Array.isArray(ids) || ids.length > 500 || ids.some((i) => typeof i !== 'string' || i.length > 64)) return reply({error: 'ids'}, 400);
  let deleted = 0;
  for (let i = 0; i < ids.length; i += ACK_CHUNK) {   // at most 5 statements, 100 parameters each
    const part = ids.slice(i, i + ACK_CHUNK);
    deleted += (await env.DB.prepare(`DELETE FROM inbox WHERE id IN (${part.map(() => '?').join(',')})`).bind(...part).run()).meta.changes;
  }
  return reply({deleted});
}

async function syncInstalls(request, env) {
  let installs;
  try { ({installs} = await request.json()); } catch { return reply({error: 'json'}, 400); }
  if (!Array.isArray(installs) || installs.some((i) => !i || !UUID.test(i.id) || !HASH.test(i.token_hash))) {
    return reply({error: 'installs'}, 400);
  }
  if (installs.length > MAX_INSTALLS_PER_SYNC) return reply({error: `at most ${MAX_INSTALLS_PER_SYNC} installs`}, 413);
  const gen = crypto.randomUUID();
  for (let i = 0; i < installs.length; i += UPSERT_ROWS) {
    const part = installs.slice(i, i + UPSERT_ROWS);
    await env.DB.prepare(`INSERT INTO installs (id, token_hash, gen) VALUES ${part.map(() => '(?,?,?)').join(',')} `
      + 'ON CONFLICT(id) DO UPDATE SET token_hash = excluded.token_hash, gen = excluded.gen')
      .bind(...part.flatMap((x) => [x.id, x.token_hash, gen])).run();
  }
  const removed = (await env.DB.prepare('DELETE FROM installs WHERE gen <> ?').bind(gen).run()).meta.changes;
  // parked batches of PCs that are now registered leave the small pending area
  await env.DB.prepare('UPDATE inbox SET known = 1 WHERE known = 0 AND install_id IN (SELECT id FROM installs)').run();
  return reply({installs: installs.length, removed});
}

export async function cleanup(env, now) {
  const keep = num(env.KEEP_DAYS, 14);
  return (await env.DB.prepare('DELETE FROM inbox WHERE received_at < ?').bind(now - Math.min(keep, 14) * 86400).run()).meta.changes;
}

export default {
  async fetch(request, env, ctx, nowOverride) {
    const now = nowOverride ?? Math.floor(Date.now() / 1000);
    const url = new URL(request.url);
    if (request.method === 'POST' && url.pathname === '/ingest') return ingest(request, env, now);
    if (['/pull', '/ack', '/installs'].includes(url.pathname)) {
      if (!pullAuth(request, env)) return reply({error: 'unauthorised'}, 401);
      if (request.method === 'GET' && url.pathname === '/pull') return pull(url, env);
      if (request.method === 'POST' && url.pathname === '/ack') return ack(request, env);
      if (request.method === 'POST' && url.pathname === '/installs') return syncInstalls(request, env);
    }
    const licence = await handleLicence(request, env, ctx, now, url);
    if (licence) return licence;
    if (request.method === 'GET' && url.pathname === '/health') return reply({ok: true}, 200, now);
    return reply({error: 'not found'}, 404);
  },
  async scheduled(event, env, ctx) {
    const now = Math.floor(Date.now() / 1000);
    ctx.waitUntil(Promise.all([cleanup(env, now), cleanupLicence(env, now)]));
  },
};
