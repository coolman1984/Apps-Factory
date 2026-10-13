import test from 'node:test';
import assert from 'node:assert/strict';
import {createHash} from 'node:crypto';
import {d1, FakeR2} from './d1.mjs';
import worker from '../src/worker.js';

const NOW = 1_900_000_000;
const COMPANY = 'co-demo';
const TOKEN = 'tok_' + 'b'.repeat(32);
const SALT = 'test-salt';
const hash = (t) => createHash('sha256').update(SALT + t).digest('hex');

const env = (extra = {}) => ({
  DB: d1(),
  BACKUPS: new FakeR2(),
  ADMIN_TOKEN: 'admin-secret',
  COMPANY_TOKEN_SALT: SALT,
  ...extra,
});

async function register(e) {
  const r = await worker.fetch(new Request('https://x/companies', {
    method: 'POST',
    headers: {authorization: 'Bearer admin-secret', 'content-type': 'application/json'},
    body: JSON.stringify({companies: [{id: COMPANY, token_hash: hash(TOKEN)}]}),
  }), e, {}, NOW);
  assert.equal(r.status, 200);
}

const call = (e, path, init = {}) => worker.fetch(new Request('https://x' + path, init), e, {}, NOW);

test('escrow stores sealed package', async () => {
  const e = env();
  await register(e);
  const pkg = {v: 1, company_id: COMPANY, device_code: 'PC-1', sealed_key: 'c2VhbGVk'};
  const r = await call(e, '/escrow', {
    method: 'POST',
    headers: {
      'content-type': 'application/json',
      'x-af-company-id': COMPANY,
      'x-af-company-token': TOKEN,
    },
    body: JSON.stringify(pkg),
  });
  assert.equal(r.status, 201);
  const row = e.DB.raw.prepare('SELECT sealed_key FROM escrow_packages WHERE company_id = ?').get(COMPANY);
  assert.equal(row.sealed_key, 'c2VhbGVk');
});

test('wrong token refused', async () => {
  const e = env();
  await register(e);
  const r = await call(e, '/escrow', {
    method: 'POST',
    headers: {'content-type': 'application/json', 'x-af-company-id': COMPANY, 'x-af-company-token': 'wrong'},
    body: JSON.stringify({v: 1, device_code: 'x', sealed_key: 'a'}),
  });
  assert.equal(r.status, 401);
});

test('backup lands in R2', async () => {
  const e = env();
  await register(e);
  const body = new Uint8Array([...new TextEncoder().encode('AFAEAD1'), 1, 2, 3]);
  const r = await call(e, '/backup', {
    method: 'POST',
    headers: {
      'x-af-company-id': COMPANY,
      'x-af-company-token': TOKEN,
      'x-af-device-code': 'PC-1',
    },
    body,
  });
  assert.equal(r.status, 201);
  assert.equal(e.BACKUPS.objects.size, 1);
});

test('backup rejects plaintext without AFAEAD1 magic', async () => {
  const e = env();
  await register(e);
  const r = await call(e, '/backup', {
    method: 'POST',
    headers: {
      'x-af-company-id': COMPANY,
      'x-af-company-token': TOKEN,
      'x-af-device-code': 'PC-1',
    },
    body: new Uint8Array([1, 2, 3]),
  });
  assert.equal(r.status, 400);
});

test('backup rejects oversized content-length before body read', async () => {
  const e = env({MAX_BACKUP_BODY: 16});
  await register(e);
  const r = await call(e, '/backup', {
    method: 'POST',
    headers: {
      'x-af-company-id': COMPANY,
      'x-af-company-token': TOKEN,
      'x-af-device-code': 'PC-1',
      'content-length': String(1024),
    },
    body: new Uint8Array(32),
  });
  assert.equal(r.status, 413);
});
