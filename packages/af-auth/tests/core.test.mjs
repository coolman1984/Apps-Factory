import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const src = readFileSync(join(here, '..', 'af-auth.js'), 'utf8');

test('af-auth.js is product-agnostic and wires standard API paths', () => {
  assert.match(src, /DEFAULT_PATHS/);
  assert.match(src, /\/api\/auth\/register/);
  assert.match(src, /auth\.link\.signup/);
  assert.doesNotMatch(src, /Trip Orders|Yousef|TO\./);
});
