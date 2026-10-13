export function reply(body, status, now) {
  const out = typeof body === 'object' && body !== null ? {...body, server_time: now} : {server_time: now};
  return new Response(JSON.stringify(out), {status, headers: {'content-type': 'application/json'}});
}

export function num(v, fallback) {
  const n = Number(v);
  return Number.isFinite(n) ? n : fallback;
}

export function bearer(h) {
  const a = h.get('authorization') || '';
  const m = /^Bearer\s+(.+)$/i.exec(a);
  return m ? m[1].trim() : '';
}

export async function sha256hex(text, salt = '') {
  const data = new TextEncoder().encode(String(salt) + text);
  const hash = await crypto.subtle.digest('SHA-256', data);
  return [...new Uint8Array(hash)].map((b) => b.toString(16).padStart(2, '0')).join('');
}

export function same(a, b) {
  if (typeof a !== 'string' || typeof b !== 'string' || a.length !== b.length) return false;
  let v = 0;
  for (let i = 0; i < a.length; i++) v |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return v === 0;
}

const BACKUP_MAGIC = new TextEncoder().encode('AFAEAD1');

export function backupHasMagic(bytes) {
  if (!bytes || bytes.length < BACKUP_MAGIC.length) return false;
  for (let i = 0; i < BACKUP_MAGIC.length; i++) {
    if (bytes[i] !== BACKUP_MAGIC[i]) return false;
  }
  return true;
}

export async function readBodyCapped(request, limit) {
  const cl = request.headers.get('content-length');
  if (cl !== null && cl !== '') {
    const n = Number(cl);
    if (Number.isFinite(n) && n > limit) return {error: 'too large', status: 413};
  }
  if (!request.body) return {bytes: new Uint8Array(0)};
  const reader = request.body.getReader();
  const chunks = [];
  let total = 0;
  while (true) {
    const {done, value} = await reader.read();
    if (done) break;
    if (!value || !value.length) continue;
    total += value.length;
    if (total > limit) {
      try {
        await reader.cancel();
      } catch {
        // ignore
      }
      return {error: 'too large', status: 413};
    }
    chunks.push(value);
  }
  const out = new Uint8Array(total);
  let off = 0;
  for (const c of chunks) {
    out.set(c, off);
    off += c.length;
  }
  return {bytes: out};
}
