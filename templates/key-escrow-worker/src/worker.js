// Key escrow + off-site backup worker (Cloudflare Worker + D1 + R2). Template only — not deployed.
// Accepts escrow JSON sealed to the vendor public key (worker never sees private keys).
// Auth: X-AF-Company-Token header hashed against companies.token_hash.
// Never store or accept private keys.

import {
  reply,
  num,
  sha256hex,
  same,
  bearer,
  backupHasMagic,
  readBodyCapped,
} from './common.js';

export const MAX_ESCROW_BODY = 64 * 1024;
export const MAX_BACKUP_BODY = 50 * 1024 * 1024;

async function companyOk(env, companyId, token) {
  if (!companyId || !token || token.length < 16 || token.length > 200) return false;
  const salt = env.COMPANY_TOKEN_SALT || '';
  const hashed = await sha256hex(token, salt);
  const row = await env.DB.prepare('SELECT token_hash FROM companies WHERE id = ?').bind(companyId).first();
  return row && same(row.token_hash, hashed);
}

async function readJsonFromBytes(raw, limit) {
  if (!raw.length) return {error: 'empty', status: 400};
  if (raw.length > limit) return {error: 'too large', status: 413};
  try {
    return {json: JSON.parse(new TextDecoder().decode(raw))};
  } catch {
    return {error: 'bad json', status: 400};
  }
}

async function handleEscrow(request, env, now) {
  const companyId = request.headers.get('x-af-company-id') || '';
  const token = request.headers.get('x-af-company-token') || '';
  if (!await companyOk(env, companyId, token)) return reply({error: 'auth'}, 401, now);
  const limit = num(env.MAX_ESCROW_BODY, MAX_ESCROW_BODY);
  const bodyRead = await readBodyCapped(request, limit);
  if (bodyRead.error) return reply({error: bodyRead.error}, bodyRead.status, now);
  const read = await readJsonFromBytes(bodyRead.bytes, limit);
  if (read.error) return reply({error: read.error}, read.status, now);
  const pkg = read.json;
  if (!pkg || pkg.v !== 1 || typeof pkg.sealed_key !== 'string' || typeof pkg.device_code !== 'string') {
    return reply({error: 'package'}, 400, now);
  }
  if (pkg.company_id && pkg.company_id !== companyId) return reply({error: 'company mismatch'}, 400, now);
  const id = crypto.randomUUID();
  await env.DB.prepare(
    'INSERT INTO escrow_packages (id, company_id, device_code, sealed_key, received_at) VALUES (?, ?, ?, ?, ?) '
    + 'ON CONFLICT(company_id, device_code) DO UPDATE SET sealed_key=excluded.sealed_key, received_at=excluded.received_at'
  ).bind(id, companyId, pkg.device_code, pkg.sealed_key, now).run();
  return reply({ok: true, id}, 201, now);
}

async function handleBackup(request, env, now) {
  const companyId = request.headers.get('x-af-company-id') || '';
  const deviceCode = request.headers.get('x-af-device-code') || '';
  const token = request.headers.get('x-af-company-token') || '';
  if (!await companyOk(env, companyId, token)) return reply({error: 'auth'}, 401, now);
  if (!deviceCode || deviceCode.length > 128) return reply({error: 'device'}, 400, now);
  const limit = num(env.MAX_BACKUP_BODY, MAX_BACKUP_BODY);
  const bodyRead = await readBodyCapped(request, limit);
  if (bodyRead.error) return reply({error: bodyRead.error}, bodyRead.status, now);
  const body = bodyRead.bytes;
  if (!body.length) return reply({error: 'empty'}, 400, now);
  if (!backupHasMagic(body)) return reply({error: 'not encrypted backup'}, 400, now);
  if (!env.BACKUPS) return reply({error: 'r2 not bound'}, 503, now);
  const key = `backups/${companyId}/${deviceCode}/${now}.bin`;
  await env.BACKUPS.put(key, body);
  return reply({ok: true, key, bytes: body.length}, 201, now);
}

async function handleRegister(request, env, now) {
  const admin = bearer(request.headers);
  const expected = env.ADMIN_TOKEN || '';
  if (!admin || !expected || !same(admin, expected)) return reply({error: 'admin'}, 401, now);
  const readBody = await readBodyCapped(request, 65536);
  if (readBody.error) return reply({error: readBody.error}, readBody.status, now);
  const read = await readJsonFromBytes(readBody.bytes, 65536);
  if (read.error) return reply({error: read.error}, read.status, now);
  const list = read.json?.companies;
  if (!Array.isArray(list)) return reply({error: 'companies'}, 400, now);
  for (const row of list.slice(0, 100)) {
    if (!row?.id || !row?.token_hash) continue;
    await env.DB.prepare(
      'INSERT INTO companies (id, token_hash, created_at) VALUES (?, ?, ?) ON CONFLICT(id) DO UPDATE SET token_hash=excluded.token_hash'
    ).bind(row.id, row.token_hash, now).run();
  }
  return reply({ok: true, count: list.length}, 200, now);
}

export default {
  async fetch(request, env, ctx) {
    const now = Math.floor(Date.now() / 1000);
    const url = new URL(request.url);
    if (request.method === 'POST' && url.pathname === '/escrow') return handleEscrow(request, env, now);
    if (request.method === 'POST' && url.pathname === '/backup') return handleBackup(request, env, now);
    if (request.method === 'POST' && url.pathname === '/companies') return handleRegister(request, env, now);
    return reply({error: 'not found'}, 404, now);
  },
};
