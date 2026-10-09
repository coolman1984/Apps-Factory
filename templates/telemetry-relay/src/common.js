// Small helpers shared by the telemetry mailbox (worker.js) and the licence mailbox (licence.js).

export const reply = (body, status = 200, now = null) => new Response(JSON.stringify(now === null ? body : {...body, server_time: now}), {
  status, headers: {'content-type': 'application/json', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff'},
});
export const num = (v, d) => (Number.isFinite(Number(v)) && Number(v) >= 0 && String(v).trim() !== '' ? Number(v) : d);

// Constant-time comparison of two strings (no early exit on the first difference).
export function same(a, b) {
  const x = new TextEncoder().encode(String(a)), y = new TextEncoder().encode(String(b));
  let diff = x.length ^ y.length;
  for (let i = 0; i < Math.max(x.length, y.length); i++) diff |= (x[i] | 0) ^ (y[i] | 0);
  return diff === 0;
}

export async function sha256hex(text) {
  const d = new Uint8Array(await crypto.subtle.digest('SHA-256', new TextEncoder().encode(text)));
  return Array.from(d, (b) => b.toString(16).padStart(2, '0')).join('');
}

export function bearer(h) {
  const auth = h.get('authorization') || '';
  return auth.slice(0, 7).toLowerCase() === 'bearer ' ? auth.slice(7).trim() : '';
}

