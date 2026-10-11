// Read-only routes for the owner's phone (Pixel Plus Owner M13), admin token only. Nothing here writes, signs or deletes.
//
//   GET /installs?afterId=&limit=     the registered installs: ids only (never token_hash), 100 per page, a cursor
//   GET /licence/history?status=&after=&limit=   safe metadata of every request state; never a code, poll hash, shop text, payment ref or address
//   GET /owner/capabilities           which optional routes this Worker has, so an older Worker is told apart from a broken one
//
// POST /installs (the Control Center replacing the registry) keeps the pull token and is untouched: the phone must never use it.
// Coverage is honest: the installs list says `coverage: "registry"` (only what the Control Center pushed) and nothing here claims to be
// the lifetime history of the business.

import {adminOk, num, reply} from './common.js';
import {approvalSeconds} from './licence.js';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const STATUSES = ['pending', 'issued', 'refused', 'delivered', 'expired'];
export const PROTOCOL = 1;
export const ROUTES = ['GET /installs', 'GET /licence/history', 'GET /licence/events?beforeId', 'POST /audit/append', 'GET /audit/recent'];

const pageSize = (url, d) => Math.min(100, Math.max(1, Math.floor(num(url.searchParams.get('limit'), d)) || d));

async function installs(env, url, now) {
  const limit = pageSize(url, 100);
  const after = url.searchParams.get('afterId') || '';
  if (after && !UUID.test(after)) return reply({error: 'afterId'}, 400, now);
  const {results} = await env.DB.prepare('SELECT id FROM installs WHERE id > ? ORDER BY id LIMIT ?').bind(after, limit + 1).all();
  const page = results.slice(0, limit);
  return reply({installs: page.map((r) => ({id: r.id})), nextCursor: results.length > limit ? {afterId: page[page.length - 1].id} : null, coverage: 'registry'}, 200, now);
}

async function history(env, url, now) {
  const status = url.searchParams.get('status');
  if (status !== null && !STATUSES.includes(status)) return reply({error: 'status'}, 400, now);
  const limit = pageSize(url, 50);
  const [at, aid] = String(url.searchParams.get('after') || '').split(':');
  if ((at && !/^\d{1,12}$/.test(at)) || (aid && !UUID.test(aid))) return reply({error: 'after'}, 400, now);
  const afterAt = at ? Number(at) : -1;
  // the effective owner decision is `expired` once an approval is older than the window, exactly as GET /licence/pending computes it
  const {results} = await env.DB.prepare("SELECT r.id, r.product, r.kind, r.device, r.status, r.reason, r.created_at, r.decided_at, r.delivered_at, "
    + "CASE WHEN o.decision = 'approved' AND r.status = 'pending' AND ? - o.decided_at > ? THEN 'expired' ELSE o.decision END AS owner_decision, o.decided_at AS owner_decided_at "
    + 'FROM licence_requests r LEFT JOIN licence_owner o ON o.request_id = r.id '
    + 'WHERE (? IS NULL OR r.status = ?) AND (r.created_at > ? OR (r.created_at = ? AND r.id > ?)) ORDER BY r.created_at, r.id LIMIT ?')
    .bind(now, approvalSeconds(env), status, status, afterAt, afterAt, aid || '', limit + 1).all();
  const page = results.slice(0, limit);
  const last = page[page.length - 1];
  return reply({requests: page, nextCursor: results.length > limit ? {after: `${last.created_at}:${last.id}`} : null, coverage: 'retained'}, 200, now);
}

// Returns a Response for the routes above, or null for everything else. The method is checked after the token, so a stranger learns nothing.
export async function handleOwner(request, env, now, url) {
  const route = `${request.method} ${url.pathname}`;
  const known = ['GET /installs', 'GET /licence/history', 'GET /owner/capabilities'];
  if (!known.includes(route)) {
    if (!['/licence/history', '/owner/capabilities'].includes(url.pathname)) return null;   // /installs POST belongs to the pull-token code
    return adminOk(request, env) ? reply({error: 'method'}, 405, now) : reply({error: 'unauthorised'}, 401);
  }
  if (!adminOk(request, env)) return reply({error: 'unauthorised'}, 401);
  if (route === 'GET /installs') return installs(env, url, now);
  if (route === 'GET /licence/history') return history(env, url, now);
  return reply({protocol: PROTOCOL, routes: ROUTES, limits: {page: 100, events: 200}}, 200, now);
}
