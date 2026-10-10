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
// The owner's buttons (POST /telegram, the bot's webhook): every alert carries «✅ موافق» and «❌ رفض». The webhook is trusted only when
// it carries the secret token Telegram was told to send AND the press comes from the owner's own private chat. «رفض» closes the request
// at once (the shop sees the refusal). «موافق» only RECORDS the owner's decision (table `licence_owner`); it is not a licence: the owner's
// trusted PC (Licence Studio) still has to sign, and a paid kind still needs proof of payment there. The owner may take an approval
// back (press «رفض») until the code has been signed. A denial is final. Nothing about the code or the key is ever in a button.
//
// Secrets (wrangler secret put, never in git): LICENCE_ADMIN_TOKEN (required for the owner's side),
//   TELEGRAM_BOT_TOKEN and TELEGRAM_OWNER_CHAT_ID (optional: the owner's phone is told about every new request),
//   TELEGRAM_WEBHOOK_SECRET (required for the buttons: the same value is given to Telegram's setWebhook as secret_token).
// Vars: LICENCE_PRODUCTS, LICENCE_PER_SOURCE_DAY, LICENCE_PER_DEVICE_DAY, LICENCE_PENDING_MAX, LICENCE_APPROVAL_HOURS.
//
// D1 Free plan: a request uses at most 9 queries, a status poll 1, a decision 2, a button 3, clean-up 5. No query reads the whole table.

import {bearer, num, reply, same, sha256hex} from './common.js';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const HASH = /^[0-9a-f]{64}$/;
const DEVICE = /^[0-9A-HJKMNP-TV-Z]{5}-[0-9A-HJKMNP-TV-Z]{5}$/;              // Crockford base32: no I, L, O, U
const CODE = /^([0-9A-HJKMNP-TV-Z]{6}-){23}[0-9A-HJKMNP-TV-Z]{6}$/;           // 144 characters in 24 groups of 6
const PRODUCT = /^[a-z][a-z0-9-]{2,39}$/;
const REASON = /^[a-z][a-z_]{1,39}$/;
export const KINDS = ['trial', 'monthly', 'permanent'];
export const MAX_REQUEST_BODY = 2048;
const KIND_AR = {trial: 'تجربة', monthly: 'اشتراك شهري', permanent: 'تفعيل دائم'};
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

// The owner's chat id as pasted into the secret: a space or a line break around it is not part of it.
const ownerId = (env) => String(env.TELEGRAM_OWNER_CHAT_ID || '').trim();

// The owner's phone. The text carries only the kind, the product, the first 8 characters of the request id and the device code:
// never what the shop typed. A failing Telegram never fails the request.
export async function tgCall(env, method, payload) {
  if (!env.TELEGRAM_BOT_TOKEN) return null;
  try {
    const r = await fetch(`https://api.telegram.org/bot${env.TELEGRAM_BOT_TOKEN}/${method}`, {
      method: 'POST', headers: {'content-type': 'application/json'}, body: JSON.stringify(payload),
    });
    return r.ok ? await r.json().catch(() => ({ok: true})) : null;
  } catch {
    return null;
  }
}

export async function telegram(env, text, extra = {}) {
  if (!env.TELEGRAM_BOT_TOKEN || !ownerId(env)) return false;
  return !!(await tgCall(env, 'sendMessage', {chat_id: ownerId(env), text, disable_web_page_preview: true, ...extra}));
}

// `buttons`: the owner's buttons are switched on (TELEGRAM_WEBHOOK_SECRET is set). Without them the alert says what the Studio will do.
export const alertText = (row, buttons = true) => `🔔 طلب ${KIND_AR[row.kind]} جديد (${row.product})\nالجهاز: ${row.device}\nرقم الطلب: ${row.id.slice(0, 8)}\n`
  + (!buttons ? (row.kind === 'trial' ? 'برنامج التراخيص هيراجعه ويصدر الكود لو السياسة تسمح.' : 'محتاج تأكيد الدفع وموافقتك في برنامج التراخيص.')
    : row.kind === 'trial' ? 'دوس ✅ موافق عشان برنامج التراخيص على جهازك يصدر الكود، أو ❌ رفض.'
      : 'الموافقة هنا بتسجل قرارك بس: الكود محتاج تأكيد الدفع في برنامج التراخيص.');
// The buttons are on only when the webhook can really answer them: its secret, the bot, and a private chat (a positive number; a group is refused).
// One predicate for the alert (shows buttons) and the webhook (accepts presses), so an alert never carries buttons that cannot work.
export const buttonsReady = (env) => !!env.TELEGRAM_WEBHOOK_SECRET && !!env.TELEGRAM_BOT_TOKEN && /^\d{1,20}$/.test(ownerId(env));
// How long an approval counts (hours). The relay is the only judge of it: the owner's PC is told `expired` and never uses its own clock.
const approvalSeconds = (env) => Math.max(1, num(env.LICENCE_APPROVAL_HOURS, 72)) * 3600;

// The owner's two buttons. The data is only an action and the opaque request id (39 bytes, Telegram allows 64). After an approval the
// only button left is «سحب الموافقة»: the owner can change their mind until the code is signed.
export const keyboard = (id, approved = false) => ({inline_keyboard: [approved
  ? [{text: '❌ سحب الموافقة', callback_data: `no:${id}`}]
  : [{text: '✅ موافق', callback_data: `ok:${id}`}, {text: '❌ رفض', callback_data: `no:${id}`}]]});

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
  const told = telegram(env, alertText(row, buttonsReady(env)), buttonsReady(env) ? {reply_markup: keyboard(row.id)} : {});
  if (ctx && typeof ctx.waitUntil === 'function') ctx.waitUntil(told); else await told;
  return reply({id: row.id, poll_token: pollToken, status: 'pending'}, 202, now);
}

// Only the holder of the poll token may read a request. An unknown id and a wrong token look the same.
async function ownRequest(request, env, id) {
  const token = bearer(request.headers);
  if (!UUID.test(id || '') || token.length < 20 || token.length > 200) return null;
  const r = await env.DB.prepare('SELECT r.id, r.status, r.reason, r.code, r.poll_hash, r.kind, o.decision AS owner_decision, o.decided_at AS owner_decided_at '
    + 'FROM licence_requests r LEFT JOIN licence_owner o ON o.request_id = r.id WHERE r.id = ?').bind(id).first();
  if (!r || !same(r.poll_hash, await sha256hex(token))) return null;
  return r;
}

async function status(request, env, url, now) {
  const r = await ownRequest(request, env, url.searchParams.get('id'));
  if (!r) return reply({error: 'unauthorised'}, 401, now);
  // `stage: 'approved'` (a trial, while the approval counts) lets the shop say "the company agreed, the code is on its way"; it is never a licence
  const approved = r.status === 'pending' && r.kind === 'trial' && r.owner_decision === 'approved' && now - r.owner_decided_at <= approvalSeconds(env);
  return reply({status: r.status, reason: r.reason, ...(approved ? {stage: 'approved'} : {}),
    ...(r.status === 'issued' ? {code: r.code} : {})}, 200, now);
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
  // `owner_decision` is `expired` once an approval is older than the window: the owner's PC trusts the relay's clock, not its own
  const {results} = await env.DB.prepare("SELECT r.id, r.product, r.kind, r.device, r.machine, r.shop, r.ref, r.version, r.src, r.created_at, "
    + "CASE WHEN o.decision = 'approved' AND ? - o.decided_at > ? THEN 'expired' ELSE o.decision END AS owner_decision, o.decided_at AS owner_decided_at "
    + "FROM licence_requests r LEFT JOIN licence_owner o ON o.request_id = r.id "
    + "WHERE r.status = 'pending' AND (r.created_at > ? OR (r.created_at = ? AND r.id > ?)) ORDER BY r.created_at, r.id LIMIT ?")
    .bind(now, approvalSeconds(env), afterAt, afterAt, aid || '', limit).all();
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

// What became of requests the owner's program still holds as waiting (a button closed them while it was away): at most 50 ids, one query.
async function states(request, env, now) {
  let d;
  try { d = await request.json(); } catch { return reply({error: 'json'}, 400, now); }
  const ids = d && Array.isArray(d.ids) ? d.ids.filter((x) => typeof x === 'string' && UUID.test(x)).slice(0, 50) : null;
  if (!ids || !ids.length) return reply({error: 'fields'}, 400, now);
  const {results} = await env.DB.prepare('SELECT r.id, r.status, r.reason, o.decision AS owner_decision FROM licence_requests r LEFT JOIN licence_owner o ON o.request_id = r.id '
    + `WHERE r.id IN (${ids.map(() => '?').join(',')})`).bind(...ids).all();
  return reply({states: Object.fromEntries(results.map((r) => [r.id, {status: r.status, reason: r.reason, owner_decision: r.owner_decision}]))}, 200, now);
}

async function events(env, url, now) {
  const limit = Math.min(200, Math.max(1, Math.floor(num(url.searchParams.get('limit'), 100)) || 100));
  const {results} = await env.DB.prepare('SELECT id, at, request_id, event, detail FROM licence_events ORDER BY id DESC LIMIT ?').bind(limit).all();
  return reply({events: results}, 200, now);
}

// ---------------------------------------------------------------------------------------------------------------------------------
// The bot's webhook: the owner's two buttons. Telegram is told (setWebhook) to send `X-Telegram-Bot-Api-Secret-Token: <secret>` with
// every update. Anything else is refused. Even with the secret, only a press by the owner's own private chat counts: the press must
// come FROM the owner's id and be made on a message IN the owner's chat (a forwarded or copied message in some other chat never
// works). The button data is only `ok:<request id>` or `no:<request id>`; the server decides what it means, not the label.
const BUTTON = /^(ok|no):([0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12})$/;
const MAX_UPDATE_BODY = 8192;
const WRONG_PRESSES_PER_HOUR = 50;   // the log of refused presses is capped: strangers cannot fill the database

async function pressRefused(env, now, detail) {
  // one statement: writes nothing once the hour's cap is reached
  await env.DB.prepare("INSERT INTO licence_events (at, request_id, event, detail) SELECT ?, NULL, 'tg_refused', ? WHERE "
    + "(SELECT COUNT(*) FROM licence_events WHERE event = 'tg_refused' AND at > ?) < ?").bind(now, String(detail).slice(0, 60), now - 3600, WRONG_PRESSES_PER_HOUR).run();
}

export async function handleTelegram(request, env, ctx, now) {
  const wait = (p) => (ctx && typeof ctx.waitUntil === 'function' ? (ctx.waitUntil(p), undefined) : p);   // in the Worker the owner's phone is told after the answer; in a test it is awaited
  if (request.method !== 'POST' || !buttonsReady(env)) {
    return reply({error: 'not found'}, 404);   // not switched on (or the owner's chat is a group, whose presses are never accepted)
  }
  if (!same(request.headers.get('x-telegram-bot-api-secret-token') || '', env.TELEGRAM_WEBHOOK_SECRET)) {
    // Not written to D1: the address is public, and a flood of wrong secrets must not cost the free plan's quota. (`wrangler tail` shows it.)
    console.warn('telegram webhook: wrong or missing secret token');
    return reply({error: 'unauthorised'}, 401);
  }
  const declared = Number(request.headers.get('content-length') || 0);
  const raw = declared > MAX_UPDATE_BODY ? '' : await request.text();
  let update;
  try { update = JSON.parse(raw); } catch { update = null; }
  if (!raw || raw.length > MAX_UPDATE_BODY || !update || typeof update !== 'object') {
    await pressRefused(env, now, 'bad_body');
    return reply({ok: true});                  // authentic but not ours: Telegram must not retry it
  }
  const cb = update.callback_query;
  if (!cb || typeof cb !== 'object') return reply({ok: true});    // ordinary messages, edits and so on are ignored
  const owner = ownerId(env);
  const answer = (text) => wait(tgCall(env, 'answerCallbackQuery', {callback_query_id: String(cb.id || '').slice(0, 64), text, show_alert: false}));
  if (String(cb.from && cb.from.id) !== owner || String(cb.message && cb.message.chat && cb.message.chat.id) !== owner) {
    await pressRefused(env, now, 'not_owner');
    await answer('مش مسموح');
    return reply({ok: true});
  }
  const m = BUTTON.exec(typeof cb.data === 'string' ? cb.data : '');
  if (!m) {
    await pressRefused(env, now, 'bad_data');
    await answer('الزرار ده مش مفهوم');
    return reply({ok: true});
  }
  const [, action, id] = m;
  const row = await env.DB.prepare('SELECT r.id, r.product, r.kind, r.device, r.status, r.reason, r.created_at, o.decision AS owner_decision, o.decided_at AS owner_decided_at '
    + 'FROM licence_requests r LEFT JOIN licence_owner o ON o.request_id = r.id WHERE r.id = ?').bind(id).first();
  const message = cb.message && Number.isInteger(cb.message.message_id) ? cb.message.message_id : null;
  // Show the outcome on the message itself (and drop the buttons it no longer needs). Rebuilt from our own row, never from the
  // message text, so repeated presses cannot make it grow.
  const show = (label, approved = false) => (message === null || !row ? null : wait(tgCall(env, 'editMessageText', {
    chat_id: owner, message_id: message, text: `${alertText(row, true)}\n\n${label}`, disable_web_page_preview: true,
    reply_markup: approved ? keyboard(row.id, true) : {inline_keyboard: []},
  })));
  if (!row) {
    await answer('الطلب ده مش موجود');
    return reply({ok: true});
  }
  const closed = async () => {
    await answer(row.status === 'refused' ? 'الطلب اترفض قبل كده' : 'الطلب اتقفل خلاص');
    await show(row.status === 'refused' ? '❌ الطلب اترفض' : `ℹ️ الطلب اتقفل (${row.status})`);
    return reply({ok: true});
  };
  if (action === 'no') {
    if (row.status !== 'pending') return closed();
    const done = await env.DB.prepare("UPDATE licence_requests SET status = 'refused', reason = 'owner_refused', decided_at = ? WHERE id = ? AND status = 'pending'").bind(now, id).run();
    if (!done.meta.changes) return closed();      // the owner's program closed it a moment ago
    await env.DB.prepare("INSERT INTO licence_owner (request_id, decision, decided_at) VALUES (?, 'denied', ?) "
      + "ON CONFLICT(request_id) DO UPDATE SET decision = 'denied', decided_at = excluded.decided_at").bind(id, now).run();
    await note(env, now, id, 'refused', row.owner_decision === 'approved' ? 'owner_refused telegram (approval withdrawn)' : 'owner_refused telegram');
    await answer('اترفض ❌');
    await show('❌ رفضت الطلب');
    return reply({ok: true});
  }
  // action === 'ok'
  if (row.status !== 'pending') return closed();
  if (row.owner_decision === 'approved' && now - row.owner_decided_at > approvalSeconds(env)) {  // an approval nobody used for days no longer counts: do not say the program will issue it
    await env.DB.prepare("INSERT INTO licence_events (at, request_id, event, detail) SELECT ?, ?, 'tg_stale', 'approval' WHERE NOT EXISTS "
      + "(SELECT 1 FROM licence_events WHERE request_id = ? AND event = 'tg_stale')").bind(now, id, id).run();  // once per request, however often the button is pressed
    await answer('الموافقة قديمة: وافق من برنامج التراخيص بنفسك أو خلي المحل يطلب تاني');
    await show('⌛ الموافقة قديمة ومابقتش تنفع: وافق من برنامج التراخيص بنفسك أو خلي المحل يطلب تاني');
    return reply({ok: true});
  }
  if (row.owner_decision === 'approved') {
    await answer('وافقت قبل كده ✅');
    await show('✅ وافقت: برنامج التراخيص هيصدر الكود', true);
    return reply({ok: true});
  }
  if (now - row.created_at > approvalSeconds(env)) {  // an old button: the shop should ask again
    await note(env, now, id, 'tg_refused', 'stale');
    await answer('الطلب قديم: خلي المحل يطلب تاني');
    await show('⌛ الطلب قديم: خلي المحل يطلب تاني');
    return reply({ok: true});
  }
  // one statement: it records the approval only while the request is still waiting, and only once (the key is the request id)
  const done = await env.DB.prepare("INSERT OR IGNORE INTO licence_owner (request_id, decision, decided_at) "
    + "SELECT ?, 'approved', ? WHERE EXISTS (SELECT 1 FROM licence_requests WHERE id = ? AND status = 'pending')").bind(id, now, id).run();
  if (!done.meta.changes) return closed();
  await note(env, now, id, 'approved', 'telegram');
  await answer('تمت الموافقة ✅');
  await show(row.kind === 'trial' ? '✅ وافقت: برنامج التراخيص هيصدر الكود لما يكون مفتوح'
    : '✅ وافقت: ناقص تأكيد الدفع في برنامج التراخيص', true);
  return reply({ok: true});
}

// Returns a Response for /licence/* paths, or null for everything else.
export async function handleLicence(request, env, ctx, now, url) {
  if (!url.pathname.startsWith('/licence/')) return null;
  const route = `${request.method} ${url.pathname}`;
  if (route === 'POST /licence/request') return create(request, env, ctx, now);
  if (route === 'GET /licence/status') return status(request, env, url, now);
  if (route === 'POST /licence/ack') return ack(request, env, now);
  if (['GET /licence/pending', 'POST /licence/decide', 'POST /licence/states', 'GET /licence/events'].includes(route)) {
    if (!adminOk(request, env)) return reply({error: 'unauthorised'}, 401);
    if (route === 'GET /licence/pending') return pending(env, url, now);
    if (route === 'POST /licence/decide') return decide(request, env, now);
    if (route === 'POST /licence/states') return states(request, env, now);
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
  n += (await env.DB.prepare('DELETE FROM licence_owner WHERE decided_at < ?').bind(now - MEMORY_DAYS * DAY).run()).meta.changes;
  return n;
}
