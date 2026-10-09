// node --test packages/af-guide/tests/core.test.mjs : the pure half of af-guide.js agrees with af_guide.py.
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
import {readFileSync} from 'node:fs';
const require = createRequire(import.meta.url);
const G = require('../af-guide.js');
const dir = new URL('../examples/shop/', import.meta.url);
const cat = JSON.parse(readFileSync(new URL('catalogue.json', dir)));
const ar = JSON.parse(readFileSync(new URL('ar.json', dir)));

test('[[ui]] references become labels quoted once', () => {
  const label = k => ({'shift.open': 'افتح الوردية'})[k] || k;
  assert.equal(G.plain(ar['guide.open-shift.2'], label), 'اضغط «افتح الوردية».');
  assert.deepEqual(G.parts('a [[x]] b', k => k.toUpperCase()), [{t: 'a '}, {ui: 'x', label: 'X'}, {t: ' b'}]);
});

test('course follows the role path, live states and requires', () => {
  let c = G.course(cat, 'cashier', {done: {}}, [], null);
  assert.deepEqual(c.items.map(i => [i.id, i.locked]), [['open-shift', false], ['first-sale', true], ['close-shift', true]]);
  assert.equal(c.next, 'open-shift');
  c = G.course(cat, 'cashier', {done: {}}, ['shift.open'], null);
  assert.equal(c.items[0].auto, true);
  assert.equal(c.next, 'first-sale');
  c = G.course(cat, 'owner', {done: {}}, [], p => p !== 'users.manage');
  assert.ok(!c.items.some(i => i.id === 'add-person'));
  assert.equal(G.course(cat, 'nobody', {}, [], null).total, 0);
});

test('auto-advance conditions', () => {
  const env = {route: 'shift', events: new Set(['shift.opened']), present: id => id === 'shift.cash', filled: id => id === 'shift.cash', dialog: () => false};
  assert.ok(G.untilMet({k: 'go', page: 'shift'}, env));
  assert.ok(!G.untilMet({k: 'go', page: 'sell'}, env));
  assert.ok(G.untilMet({k: 'click', until: {target: 'shift.cash'}}, env));
  assert.ok(G.untilMet({k: 'click', until: {gone: 'stock.name'}}, env));
  assert.ok(G.untilMet({k: 'type', until: {filled: 'shift.cash'}}, env));
  assert.ok(G.untilMet({k: 'click', until: {event: 'shift.opened'}}, env));
  assert.ok(!G.untilMet({k: 'tip'}, env));
});

test('page help and error links', () => {
  assert.deepEqual(G.guidesForPage(cat, 'shift', null).map(g => g.id), ['open-shift', 'close-shift']);
  assert.deepEqual(G.problemsForPage(cat, 'shift', 'cashier').map(p => p.id), ['no-shift', 'drawer-mismatch']);
  assert.equal(G.problemFor(cat, 'sale.no_shift').id, 'no-shift');
  assert.equal(G.problemFor(cat, 'nope'), null);
  assert.equal(G.stepPage(cat, cat.guides[0], 2), 'shift');
});

test('built-in words exist in both languages', () => {
  assert.deepEqual(Object.keys(G.WORDS.ar).sort(), Object.keys(G.WORDS.en).sort());
});
