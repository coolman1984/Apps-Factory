// TEST ONLY. Runs the real Worker (src/worker.js) behind a plain HTTP server on 127.0.0.1, with the node:sqlite D1 shim and a recording
// Telegram stub, so that other programs' tests (the Licence Studio's, Al-Store's) can talk to the real code over real HTTP.
//   node --experimental-sqlite test/serve.mjs [port]      prints {"port": N} when ready
// Extra test-only paths (never part of the Worker): GET /__test/telegram → the messages the Worker tried to send.
import http from 'node:http';
import {d1} from './d1.mjs';
import worker from '../src/worker.js';

const sent = [];
globalThis.fetch = async (url, init) => {   // the Worker's only outgoing call is Telegram
  sent.push({url: String(url).replace(/bot[^/]+/, 'bot***'), body: JSON.parse(init.body)});
  return new Response('{"ok":true}', {status: 200});
};
const env = {
  DB: d1(), RELAY_PULL_TOKEN: process.env.RELAY_PULL_TOKEN || 'pull-secret-for-tests', LICENCE_ADMIN_TOKEN: process.env.LICENCE_ADMIN_TOKEN || 'licence-admin-secret-for-tests',
  TELEGRAM_BOT_TOKEN: '1:TEST', TELEGRAM_OWNER_CHAT_ID: '7', LICENCE_PER_SOURCE_DAY: process.env.LICENCE_PER_SOURCE_DAY || '50',
  LICENCE_PER_DEVICE_DAY: process.env.LICENCE_PER_DEVICE_DAY || '20',
};
const pending = [];
const server = http.createServer(async (req, res) => {
  if (req.url === '/__test/telegram') {
    res.setHeader('content-type', 'application/json');
    return res.end(JSON.stringify(sent));
  }
  const chunks = [];
  for await (const c of req) chunks.push(c);
  const body = chunks.length ? Buffer.concat(chunks) : undefined;
  const headers = {...req.headers, 'cf-connecting-ip': req.headers['x-test-ip'] || '203.0.113.9'};
  const request = new Request('http://relay.test' + req.url, {method: req.method, headers, body: ['GET', 'HEAD'].includes(req.method) ? undefined : body});
  const ctx = {waitUntil: (p) => { pending.push(p); }};
  const r = await worker.fetch(request, env, ctx);
  await Promise.all(pending.splice(0));
  res.writeHead(r.status, Object.fromEntries(r.headers));
  res.end(Buffer.from(await r.arrayBuffer()));
});
server.listen(Number(process.argv[2] || 0), '127.0.0.1', () => console.log(JSON.stringify({port: server.address().port})));
