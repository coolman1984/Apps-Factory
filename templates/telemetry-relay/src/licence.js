// Licence mailbox (Cloudflare Worker + D1), the second job of the relay. A shop's program asks for a trial (or a paid code);
// the owner's trusted licensing program (Licence Studio, the ONLY place a signing key exists) pulls the request, decides, and
// hands the signed code back; the shop's program collects it and checks it itself with the vendor's PUBLIC key.
//
//   shop (Al-Store)  --POST /licence/request-->  relay (D1)  --Telegram: "طلب جديد"-->  owner's phone
//   shop             <--GET  /licence/status---  relay       <--GET /licence/pending, POST /licence/decide--  Licence Studio
//   shop             --POST /licence/ack------>  relay       (the code leaves the relay as soon as the shop has it)
//
// This file never signs, never verifies a signature, and never stores a private key. A leaked relay can refuse service or
// show who asked for a trial; it cannot make a code. Codes are bound to one device code, so a code read by a stranger is
// useless on any other PC.
//
// Shop side (no secret in the program): POST /licence/request  {product, kind, device, machine?, nonce, shop?, ref?, version?}
//   - `nonce` is the shop's own id for the request: sending it again finds the same request (a replay creates nothing).
//   - the answer to a NEW request carries `poll_token`, shown once; only its hash is stored. Status and ack need it.
//   - `machine` is sha256 of the PC's identity (never the identity itself); a second trial for the same machine or device is
//     refused here (`already_used`) without waking the owner. The Licence Studio keeps the permanent record and decides again.
// Owner side: Authorization: Bearer <LICENCE_ADMIN_TOKEN> (a different secret from RELAY_PULL_TOKEN: a leak of one never opens the other).
//
// Secrets (wrangler secret put, never in git): LICENCE_ADMIN_TOKEN (required for the owner's side),
//   TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_CHAT_ID (optional: the owner's phone is told about every new request).
// Vars: LICENCE_PRODUCTS, LICENCE_PER_SOURCE_DAY, LICENCE_PER_DEVICE_DAY, LICENCE_PENDING_MAX.
//
// D1 Free plan: a request uses at most 9 queries, a status poll 1, a decision 2, clean-up 5. No query reads the whole table.

import {bearer, num, reply, same, sha256hex} from './common.js';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;
const DEVICE = /^[0-9A-HJKMNP-TV-Z]{5}-[0-9A-HJKMNP-TV-Z]{5}$/;              // Crockford base32: no I, L, O, U
const CODE = /^([0-9A-HJKMNP-TV-Z]{6}-){23}[0-9A-HJKMNP-TV-Z]{6}$/;           // 144 characters in 24 groups of 6
const PRODUCT = /^[a-z][a-z0-9-]{2,39}$/;
const REASON = /^[a-z][a-z_]{1,39}$/;
export const KINDS = ['trial', 'monthly', 'permanent'];
export const MAX_REQUEST_BODY = 2048;
const KIND_AR = {trial: 'تجربة 14 يوم', monthly: 'اشتراك شهري', permanent: 'تفعيل دائم'};
const DAY = 86400;
const PENDING_DAYS = 14;           // a request nobody decided in two weeks is closed
const MEMORY_DAYS = 400;           // who already had a trial is remembered for more than a year
const EVENT_DAYS = 90;

// Text typed by a shop is untrusted: no control characters, no direction overrides, short.
// Free text from a shop is not kept in the cloud beyond what the owner needs to recognise the shop: no payment references (the
// payment is confirmed by the owner in the Studio, not here) and no runs of digits that could be a phone or account number.
const plain = (v, n) => clean(v, n).replace(/\d[\d\s-]{5,}\d/g, '…');
const clean = (v, n) => String(v ?? '').replace(/[\u0000-\u001f\u007f‎‏‪-‮⁦-⁩]/g, ' ').replace(/\s+/g, ' ').trim().slice(0, n);

async function note(env, now, requestId, event, detail = '') {
  await env.DB.prepare('INSERT INTO licence_events (at, request_id, event, detail) VALUES (?,?,?,?)').bind(now, requestId, event, String(detail).slice(0, 200)).run();
}

// The owner's phone. The text carries only the kind, the product, the first 8 characters of the request id and the device code:
// never what the shop typed. A failing Telegram never fails the request.
export async function telegram(env, text) {
  if (!env.TELEGRAM_BOT_TOKEN || !env.TELEGRAM_OWNER_CHAT_ID) return false;
  try {
    const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/sendMessage`, {
      method: 'POST', headers: {'content-type': 'application/json'},
      body: JSON.stringify({chat_id: env.TELEGRAM_OWNER_CHAT_ID, text, disable_web_page_preview: true}),
    });
    return r.ok;
  } catch {
    return false;
  }
}

export const alertText = (row) => `🔔 طلب ${KIND_AR[row.kind]} جديد (${row.product})\nالجهاز: ${row.device}\nرقم الطلب: ${row.id.slice(0, 8)}\n`
  + (row.kind === 'trial' ? 'برنامج التراخيص هيراجعه ويصدر الكود لو السياسة تسمح.' : 'محتاج تأكيد الدفع وموافقتك في برنامج التراخيص.');

async function create(request, env, ctx, now) {
  const declared = Number(request.headers.get('content-length') || 0);
  if (declared > MAX_REQUEST_BODY) return reply({error: 'too large'}, 413, now);
  const raw = await request.text();
  if (raw.length > MAX_REQUEST_BODY) return reply({error: 'too large'}, 413, now);
  let d;
  try { d = JSON.parse(raw); } catch { return reply({error: 'json'}, 400, now); }
  if (!d || typeof d !== 'object' || Array.isArray(d)) return reply({error: 'json'}, 400, now);
  const bad = (field) => reply({error: 'field', field}, 400, now);
  const products = String(env.LICENCE_PRODUCTS || 'al-store').split(',').map((x) => x.trim()).filter(Boolean);
  if (typeof d.product !== 'string' || !PRODUCT.test(d.product) || !products.includes(d.product)) return bad('product');
  if (!KINDS.includes(d.kind)) return bad('kind');
  if (typeof d.device !== 'string' || !DEVICE.test(d.device)) return bad('device');
  if (d.machine !== undefined && d.machine !== null && (typeof d.machine !== 'string' || !HASH.test(d.machine))) return bad('machine');
  if (d.kind === 'trial' && !d.machine) return bad('machine');
  if (typeof d.nonce !== 'string' || !UUID.test(d.nonce)) return bad('nonce');
  const row = {
    id: crypto.randomUUID(), product: d.product, kind: d.kind, device: d.device, machine: d.machine || null, nonce: d.nonce,
    shop: plain(d.shop, 60), ref: '', version: clean(d.version, 20),
  };
  const pollToken = 'lp_' + Array.from(crypto.getRandomValues(new Uint8Array(24)), (b) => b.toString(16).padStart(2, '0')).join('');
  const pollHash = await sha256hex(pollToken);
  const src = (await sha256hex(`${request.headers.get('cf-connecting-ip') || '-'}|${Math.floor(now / DAY)}`)).slice(0, 16);

  // 1. a replay finds the same request and creates nothing (and never learns the poll token)
  const same_ = await env.DB.prepare('SELECT id, status, reason FROM licence_requests WHERE product = ? AND device = ? AND nonce = ?')
    .bind(row.product, row.device, row.nonce).first();
  if (same_) return reply({id: same_.id, status: same_.status, reason: same_.reason, replay: true}, 200, now);
  // 2. rate limits (each reads one index range)
  const here = await env.DB.prepare('SELECT COUNT(*) AS n FROM licence_requests WHERE src = ? AND created_at > ?').bind(src, now - DAY).first();
  if (here.n >= num(env.LICENCE_PER_SOURCE_DAY, 10)) return reply({error: 'rate'}, 429, now);
  const dev = await env.DB.prepare('SELECT COUNT(*) AS n FROM licence_requests WHERE device = ? AND created_at > ?').bind(row.device, now - DAY).first();
  if (dev.n >= num(env.LICENCE_PER_DEVICE_DAY, 3)) return reply({error: 'rate'}, 429, now);
  const insert = (status, reason, code = null) => env.DB.prepare(
    'INSERT INTO licence_requests (id, product, kind, device, machine, nonce, poll_hash, shop, ref, version, src, status, reason, code, created_at, decided_at) '
    + 'VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)').bind(row.id, row.product, row.kind, row.device, row.machine, row.nonce, pollHash, row.shop, row.ref,
    row.version, src, status, reason, code, now, status === 'pending' ? null : now);
  const store = (status, reason, code = null) => insert(status, reason, code).run();
  // The limits and the insert of a new waiting request are ONE statement: concurrent requests cannot all pass the counts before any
  // of them is written (review of PR #33). It writes nothing when a limit is reached.
  const storeWithinLimits = () => env.DB.prepare(
    'INSERT INTO licence_requests (id, product, kind, device, machine, nonce, poll_hash, shop, ref, version, src, status, reason, code, created_at, decided_at) '
    + "SELECT ?,?,?,?,?,?,?,?,?,?,?,'pending','',NULL,?,NULL WHERE "
    + '(SELECT COUNT(*) FROM licence_requests WHERE src = ? AND created_at > ?) < ? AND '
    + '(SELECT COUNT(*) FROM licence_requests WHERE device = ? AND created_at > ?) < ? AND '
    + "(SELECT COUNT(*) FROM licence_requests WHERE status = 'pending') < ?")
    .bind(row.id, row.product, row.kind, row.device, row.machine, row.nonce, pollHash, row.shop, row.ref, row.version, src, now,
      src, now - DAY, num(env.LICENCE_PER_SOURCE_DAY, 10), row.device, now - DAY, num(env.LICENCE_PER_DEVICE_DAY, 3), num(env.LICENCE_PENDING_MAX, 300)).run();
  // 3. the code for this very device is already waiting (the shop lost its poll token): hand the same code to the new request
  const waiting = await env.DB.prepare("SELECT id, code FROM licence_requests WHERE product = ? AND device = ? AND kind = ? AND status = 'issued' "
    + 'ORDER BY created_at DESC LIMIT 1').bind(row.product, row.device, row.kind).first();
  if (waiting) {
    await store('issued', 'reissued', waiting.code);
    // the old request counts as delivered (to this very device): its machine tag stays in the memory that refuses a second trial
    await env.DB.prepare("UPDATE licence_requests SET status = 'delivered', reason = 'superseded', code = NULL, delivered_at = ? WHERE id = ?").bind(now, waiting.id).run();
    await note(env, now, row.id, 'reissued', `from ${waiting.id.slice(0, 8)}`);
    return reply({id: row.id, poll_token: pollToken, status: 'issued', reason: 'reissued'}, 202, now);
  }
  // 4. one trial per machine and per device: refused here, quietly (the owner is not woken)
  if (row.kind === 'trial') {
    const used = await env.DB.prepare("SELECT 1 AS x FROM licence_requests WHERE product = ? AND kind = 'trial' AND (status IN ('issued', 'delivered') OR (status = 'expired' AND reason = 'unacked')) "
      + 'AND (machine = ? OR device = ?) LIMIT 1').bind(row.product, row.machine, row.device).first();
    if (used) {
      await store('refused', 'already_used');
      await note(env, now, row.id, 'refused', 'already_used');
      return reply({id: row.id, poll_token: pollToken, status: 'refused', reason: 'already_used'}, 200, now);
    }
  }
  // 5. a new request for the same device and kind replaces the one still waiting (the shop lost its state)
  await env.DB.prepare("UPDATE licence_requests SET status = 'expired', reason = 'superseded' WHERE product = ? AND device = ? AND kind = ? AND status = 'pending'")
    .bind(row.product, row.device, row.kind).run();
  // 6. the waiting list is capped
  const pending = await env.DB.prepare("SELECT COUNT(*) AS n FROM licence_requests WHERE status = 'pending'").first();
  if (pending.n >= num(env.LICENCE_PENDING_MAX, 300)) return reply({error: 'full'}, 503, now);
  if (!(await storeWithinLimits()).meta.changes) return reply({error: 'rate'}, 429, now);  // another request took the last place meanwhile
  await note(env, now, row.id, 'created', `${row.kind} src ${src.slice(0, 6)}`);
  const told = telegram(env, alertText(row));
  if (ctx && typeof ctx.waitUntil === 'function') ctx.waitUntil(told); else await told;
  return reply({id: row.id, poll_token: pollToken, status: 'pending'}, 202, now);
}

// Only the holder of the poll token may read a request. An unknown id and a wrong token look the same.
async function ownRequest(request, env, id) {
  const token = bearer(request.headers);
  if (!UUID.test(id || '') || token.length < 20 || token.length > 200) return null;
  const r = await env.DB.prepare('SELECT id, status, reason, code, poll_hash FROM licence_requests WHERE id = ?').bind(id).first();
  if (!r || !same(r.poll_hash, await sha256hex(token))) return null;
  return r;
}

async function status(request, env, url, now) {
  const r = await ownRequest(request, env, url.searchParams.get('id'));
  if (!r) return reply({error: 'unauthorised'}, 401, now);
  return reply({status: r.status, reason: r.reason, ...(r.status === 'issued' ? {code: r.code} : {})}, 200, now);
}

async function ack(request, env, now) {
  let d;
  try { d = await request.json(); } catch { return reply({error: 'json'}, 400, now); }
  const r = await ownRequest(request, env, d && d.id);
  if (!r) return reply({error: 'unauthorised'}, 401, now);
  if (r.status === 'issued') {
    await env.DB.prepare("UPDATE licence_requests SET status = 'delivered', code = NULL, delivered_at = ? WHERE id = ? AND status = 'issued'").bind(now, r.id).run();
    await note(env, now, r.id, 'delivered');
  }
  return reply({status: r.status === 'issued' ? 'delivered' : r.status}, 200, now);
}

const adminOk = (request, env) => !!env.LICENCE_ADMIN_TOKEN && same(bearer(request.headers), env.LICENCE_ADMIN_TOKEN);

async function pending(env, url, now) {
  const limit = Math.min(100, Math.max(1, Math.floor(num(url.searchParams.get('limit'), 50)) || 50));
  // `after=<created_at>:<id>` reads the next page: requests that wait for the owner must not hide newer ones (review of PR #34)
  const [at, aid] = String(url.searchParams.get('after') || '').split(':');
  const afterAt = Number.isFinite(Number(at)) && at !== '' ? Number(at) : -1;
  const {results} = await env.DB.prepare("SELECT id, product, kind, device, machine, shop, ref, version, src, created_at FROM licence_requests "
    + "WHERE status = 'pending' AND (created_at > ? OR (created_at = ? AND id > ?)) ORDER BY created_at, id LIMIT ?")
    .bind(afterAt, afterAt, aid || '', limit).all();
  return reply({requests: results}, 200, now);
}

async function decide(request, env, now) {
  let d;
  try { d = await request.json(); } catch { return reply({error: 'json'}, 400, now); }
  if (!d || !UUID.test(d.id || '') || !['issue', 'refuse'].includes(d.action)) return reply({error: 'fields'}, 400, now);
  if (d.action === 'issue' && !CODE.test(d.code || '')) return reply({error: 'code'}, 400, now);
  const reason = d.action === 'refuse' ? (REASON.test(d.reason || '') ? d.reason : 'owner_refused') : '';
  const cur = await env.DB.prepare('SELECT status, code FROM licence_requests WHERE id = ?').bind(d.id).first();
  if (!cur) return reply({error: 'not found'}, 404, now);
  const target = d.action === 'issue' ? 'issued' : 'refused';
  if (cur.status === target && (target === 'refused' || cur.code === d.code)) return reply({status: cur.status, repeat: true}, 200, now);  // the owner's program may retry
  if (cur.status === 'delivered' && target === 'issued') return reply({status: 'delivered', repeat: true}, 200, now);
  if (cur.status !== 'pending') return reply({error: 'closed', status: cur.status}, 409, now);
  const done = await env.DB.prepare("UPDATE licence_requests SET status = ?, reason = ?, code = ?, decided_at = ? WHERE id = ? AND status = 'pending'")
    .bind(target, reason, d.action === 'issue' ? d.code : null, now, d.id).run();
  if (!done.meta.changes) return reply({error: 'closed'}, 409, now);
  await note(env, now, d.id, target, reason);
  return reply({status: target}, 200, now);
}

async function events(env, url, now) {
  const limit = Math.min(200, Math.max(1, Math.floor(num(url.searchParams.get('limit'), 100)) || 100));
  const {results} = await env.DB.prepare('SELECT id, at, request_id, event, detail FROM licence_events ORDER BY id DESC LIMIT ?').bind(limit).all();
  return reply({events: results}, 200, now);
}

// Returns a Response for /licence/* paths, or null for everything else.
export async function handleLicence(request, env, ctx, now, url) {
  if (!url.pathname.startsWith('/licence/')) return null;
  const route = `${request.method} ${url.pathname}`;
  if (route === 'POST /licence/request') return create(request, env, ctx, now);
  if (route === 'GET /licence/status') return status(request, env, url, now);
  if (route === 'POST /licence/ack') return ack(request, env, now);
  if (['GET /licence/pending', 'POST /licence/decide', 'GET /licence/events'].includes(route)) {
    if (!adminOk(request, env)) return reply({error: 'unauthorised'}, 401);
    if (route === 'GET /licence/pending') return pending(env, url, now);
    if (route === 'POST /licence/decide') return decide(request, env, now);
    return events(env, url, now);
  }
  return reply({error: 'not found'}, 404);
}

// Daily clean-up: a request nobody decided in two weeks is closed and its code dropped; old events go; a trial is remembered for a year.
export async function cleanupLicence(env, now) {
  let n = 0;
  // an issued code nobody collected still counts as a trial given (review of PR #33): it expires as 'unacked', not 'timeout'
  n += (await env.DB.prepare("UPDATE licence_requests SET status = 'expired', reason = 'unacked', code = NULL WHERE status = 'issued' AND created_at < ?")
    .bind(now - PENDING_DAYS * DAY).run()).meta.changes;
  n += (await env.DB.prepare("UPDATE licence_requests SET status = 'expired', reason = 'timeout', code = NULL WHERE status = 'pending' AND created_at < ?")
    .bind(now - PENDING_DAYS * DAY).run()).meta.changes;
  n += (await env.DB.prepare("DELETE FROM licence_requests WHERE status IN ('refused', 'expired') AND created_at < ?").bind(now - MEMORY_DAYS * DAY).run()).meta.changes;
  n += (await env.DB.prepare("DELETE FROM licence_requests WHERE status = 'delivered' AND created_at < ?").bind(now - MEMORY_DAYS * DAY).run()).meta.changes;
  n += (await env.DB.prepare('DELETE FROM licence_events WHERE at < ?').bind(now - EVENT_DAYS * DAY).run()).meta.changes;
  return n;
}
