import fs from 'node:fs';
import assert from 'node:assert/strict';
const file = new URL('./sources.json', import.meta.url);
const data = JSON.parse(fs.readFileSync(file, 'utf8'));
assert.equal(data.version, 1);
assert.ok(Array.isArray(data.sources));
assert.equal(new Set(data.sources.map(s => s.id)).size, data.sources.length);
for (const source of data.sources) {
  assert.ok(source.id);
  assert.ok(source.url.startsWith('https://'));
  assert.ok(source.category);
  assert.ok(source.license);
  assert.equal(typeof source.enabled, 'boolean');
}
assert.equal(data.sources.find(s => s.id === 'inspora')?.enabled, false);
console.log('Design source registry: PASS (' + data.sources.length + ' sources)');
