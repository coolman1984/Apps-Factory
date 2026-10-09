// Telemetry relay (Cloudflare Worker + D1). A mailbox between installed products and the Control Center:
// products POST signed gzip batches to /ingest; the Control Center pulls them with GET /pull and deletes them with
// POST /ack. The relay never opens a batch and holds no install secrets: the Control Center verifies every signature
// (HMAC keyed by sha256(install token)), every privacy rule and every nonce again when it pulls.
//
// Bindings (wrangler.toml): DB (D1). Secrets (wrangler secret put, never in git): RELAY_PULL_TOKEN (required),
// RELAY_INGEST_KEY (optional shared key products send as X-AF-Relay-Key). Vars: RATE_PER_HOUR, MAX_ROWS, KEEP_DAYS.

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const NONCE = /^[0-9a-f]{16,64}$/;
const SIG = /^[0-9a-f]{64}$/;
export const MAX_BODY = 512 * 1024;   // same limit as the Control Center
export const WINDOW_S = 300;

const json = (body, status = 200) => new Response(JSON.stringify(body), {
  status, headers: {'content-type': 'application/json', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff'},
});
const num = (v, d) => (Number.isFinite(Number(v)) && Number(v) > 0 ? Number(v) : d);

// Constant-time comparison of two strings (no early exit on the first difference).
export function same(a, b) {
  const x = new TextEncoder().encode(String(a)), y = new TextEncoder().encode(String(b));
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] | 0) ^ (y[i] | 0);
  return diff === 0;
}

function b64(bytes) {
  let s = '';
  for (let i = 0; i < bytes.length; i += 0x8000) s += String.fromCharCode.apply(null, bytes.subarray(i, i + 0x8000));
  return btoa(s);
}

async function ingest(request, env, now) {
  const h = request.headers;
  if (env.RELAY_INGEST_KEY && !same(h.get('x-af-relay-key') || '', env.RELAY_INGEST_KEY)) return json({error: 'key'}, 401);
  const install = h.get('x-af-install') || '', nonce = h.get('x-af-nonce') || '', sig = h.get('x-af-signature') || '';
  const ts = Number(h.get('x-af-timestamp'));
  if (!UUID.test(install) || !NONCE.test(nonce) || !SIG.test(sig) || !Number.isInteger(ts)) return json({error: 'headers'}, 400);
  if (Math.abs(now - ts) > WINDOW_S) return json({error: 'clock'}, 401);
  const declared = Number(h.get('content-length') || 0);
  if (declared > MAX_BODY) return json({error: 'too large'}, 413);
  const body = new Uint8Array(await request.arrayBuffer());
  if (!body.length || body.length > MAX_BODY) return json({error: body.length ? 'too large' : 'empty'}, body.length ? 413 : 400);
  if (body[0] !== 0x1f || body[1] !== 0x8b) return json({error: 'not gzip'}, 400);
  const hour = await env.DB.prepare('SELECT COUNT(*) AS n FROM batches WHERE install_id = ? AND received_at > ?')
    .bind(install, now - 3600).first();
  if (hour.n >= num(env.RATE_PER_HOUR, 120)) return json({error: 'rate'}, 429);
  const all = await env.DB.prepare('SELECT COUNT(*) AS n FROM batches').first();
  if (all.n >= num(env.MAX_ROWS, 50000)) return json({error: 'full'}, 503);   // product keeps it in its outbox, retries later
  try {
    await env.DB.prepare('INSERT INTO batches (id, install_id, ts, nonce, sig, body, received_at) VALUES (?,?,?,?,?,?,?)')
      .bind(crypto.randomUUID(), install, ts, nonce, sig, b64(body), now).run();
  } catch (e) {
    if (String(e && e.message).includes('UNIQUE')) return json({error: 'nonce already used'}, 409);
    throw e;
  }
  return json({ok: true}, 202);
}

function pullAuth(request, env) {
  const auth = request.headers.get('authorization') || '';
  return !!env.RELAY_PULL_TOKEN && auth.startsWith('Bearer ') && same(auth.slice(7), env.RELAY_PULL_TOKEN);
}

async function pull(url, env) {
  const limit = Math.min(500, Math.max(1, Math.floor(num(url.searchParams.get('limit'), 100))));
  const {results} = await env.DB.prepare('SELECT id, install_id, ts, nonce, sig, body FROM batches ORDER BY received_at LIMIT ?')
    .bind(limit).all();
  return json({batches: results});
}

async function ack(request, env) {
  let ids;
  try { ({ids} = await request.json()); } catch { return json({error: 'json'}, 400); }
  if (!Array.isArray(ids) || ids.length > 500 || ids.some((i) => typeof i !== 'string' || i.length > 64)) return json({error: 'ids'}, 400);
  let deleted = 0;
  for (const id of ids) deleted += (await env.DB.prepare('DELETE FROM batches WHERE id = ?').bind(id).run()).meta.changes;
  return json({deleted});
}

export async function cleanup(env, now) {
  const keep = num(env.KEEP_DAYS, 14);
  return (await env.DB.prepare('DELETE FROM batches WHERE received_at < ?').bind(now - Math.min(keep, 14) * 86400).run()).meta.changes;
}

export default {
  async fetch(request, env, ctx, nowOverride) {
    const now = nowOverride ?? Math.floor(Date.now() / 1000);
    const url = new URL(request.url);
    if (request.method === 'POST' && url.pathname === '/ingest') return ingest(request, env, now);
    if (url.pathname === '/pull' || url.pathname === '/ack') {
      if (!pullAuth(request, env)) return json({error: 'unauthorised'}, 401);
      if (request.method === 'GET' && url.pathname === '/pull') return pull(url, env);
      if (request.method === 'POST' && url.pathname === '/ack') return ack(request, env);
    }
    if (request.method === 'GET' && url.pathname === '/health') return json({ok: true});
    return json({error: 'not found'}, 404);
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(cleanup(env, Math.floor(Date.now() / 1000)));
  },
};
