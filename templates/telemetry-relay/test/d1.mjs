// A tiny D1 shim over node:sqlite (Node 22.13+) that also records every statement, so the tests can hold the Worker to the D1
// Free-plan limits (50 queries per invocation, 100 bound parameters per query).
import assert from 'node:assert/strict';
import {readFileSync} from 'node:fs';
import {DatabaseSync} from 'node:sqlite';

export function d1() {
  const db = new DatabaseSync(':memory:');
  db.exec(readFileSync(new URL('../schema.sql', import.meta.url), 'utf8'));
  const log = [];
  const stmt = (sql, args = []) => ({
    bind: (...a) => {
      assert.ok(a.length <= 100, `D1 allows at most 100 bound parameters (got ${a.length})`);
      return stmt(sql, a);
    },
    first: async () => { log.push(sql); return db.prepare(sql).get(...args) ?? null; },
    all: async () => { log.push(sql); return {results: db.prepare(sql).all(...args).map((r) => ({...r}))}; },
    run: async () => { log.push(sql); return {meta: {changes: Number(db.prepare(sql).run(...args).changes)}}; },
  });
  return {prepare: (sql) => stmt(sql), log, raw: db};
}
