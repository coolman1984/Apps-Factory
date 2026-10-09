// node --test packages/af-telemetry/tests/core.test.mjs : browser half keeps only ids and counts, no error text.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const T = createRequire(import.meta.url)('../af-telemetry.js');

test('safe() keeps machine ids, numbers and booleans only', () => {
  assert.deepEqual(T.safe({page: 'sell', count: 2.6, ok: true, name: 'Ahmed Ali', phone: '01012345678', mail: 'a@b.com', obj: {a: 1}}),
    {page: 'sell', count: 3, ok: true});
});

test('client errors: file and line, never the message or the query string', () => {
  const e = T.errorEvent('https://pc/js/app.js?v=3#x', 120, 7, 'TypeError');
  assert.deepEqual(Object.keys(e).sort(), ['code', 'fingerprint', 'where']);
  assert.equal(e.where, 'app.js:120');
  assert.equal(e.code, 'TypeError');
  assert.equal(e.fingerprint, T.errorEvent('https://other/js/app.js', 120, 7, 'TypeError').fingerprint);
  assert.notEqual(e.fingerprint, T.errorEvent('app.js', 121, 7).fingerprint);
  for (let line = 1; line < 3000; line++) {   // never a long digit run, which the server would refuse as a number
    assert.match(T.errorEvent('app.js', line, 1).fingerprint, /^[a-p]{8}$/);
  }
});

test('words exist in both languages', () => {
  assert.deepEqual(Object.keys(T.WORDS.ar).sort(), Object.keys(T.WORDS.en).sort());
});
