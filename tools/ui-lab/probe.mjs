#!/usr/bin/env node
// Apps Factory UI Lab — measures what a person feels: how fast a page shows, how smooth it moves, whether it fits the
// screen, whether everyone can use it. On a slow PC (CPU throttled) because shop PCs are old. Fails against budgets.
//
//   node probe.mjs --config <product>/ui-lab.config.json [--out report-dir] [--routes home,pos] [--cpu 4] [--quick]
//
// Config: { "base": "http://127.0.0.1:8096", "login": {"steps": [["fill","#username","owner"], ...], "ready": ".shell"},
//           "routes": ["home", "pos"], "route_prefix": "/#/", "viewports": [[1366,768],[390,844]],
//           "interact": {"pos": [["fill","#pos-q","x"],["press","#pos-q","Enter"]]}, "budgets": "../factory/ui-budgets.json" }
import fs from 'node:fs';
import path from 'node:path';
import { createRequire } from 'node:module';

const require = createRequire(import.meta.url);
let chromium;
try { ({ chromium } = await import('playwright')); } catch { ({ chromium } = await import('/opt/node22/lib/node_modules/playwright/index.mjs')); }

const args = Object.fromEntries(process.argv.slice(2).reduce((a, x, i, all) => (x.startsWith('--') ? [...a, [x.slice(2), all[i + 1] && !all[i + 1].startsWith('--') ? all[i + 1] : true]] : a), []));
if (!args.config) { console.error('usage: node probe.mjs --config ui-lab.config.json [--out dir] [--routes a,b] [--cpu 4] [--quick]'); process.exit(2); }
const cfgPath = path.resolve(args.config);
const cfg = JSON.parse(fs.readFileSync(cfgPath, 'utf8'));
const here = path.dirname(new URL(import.meta.url).pathname);
const budgets = JSON.parse(fs.readFileSync(path.resolve(path.dirname(cfgPath), cfg.budgets || path.join(here, '../../factory/ui-budgets.json')), 'utf8'));
const routes = args.routes ? String(args.routes).split(',') : cfg.routes;
const viewports = args.quick ? [cfg.viewports[0]] : cfg.viewports;
const cpu = Number(args.cpu || budgets.cpu_throttle || 4);
const outDir = path.resolve(args.out || path.join(path.dirname(cfgPath), 'ui-lab-report'));
fs.mkdirSync(outDir, { recursive: true });
let axeSource = null;
try { axeSource = fs.readFileSync(require.resolve('axe-core/axe.min.js'), 'utf8'); } catch { /* accessibility check skipped and reported */ }

// Collected inside the page from the first byte (buffered observers).
const OBSERVE = () => {
  window.__lab = { lcp: 0, cls: 0, long: [], events: [] };
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lab.lcp = e.startTime; }).observe({ type: 'largest-contentful-paint', buffered: true }); } catch {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (!e.hadRecentInput) window.__lab.cls += e.value; }).observe({ type: 'layout-shift', buffered: true }); } catch {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) window.__lab.long.push([e.startTime, e.duration]); }).observe({ type: 'longtask', buffered: true }); } catch {}
  try { new PerformanceObserver((l) => { for (const e of l.getEntries()) if (e.interactionId) window.__lab.events.push(e.duration); }).observe({ type: 'event', buffered: true, durationThreshold: 16 }); } catch {}
};
const OVERFLOW = () => {
  const vw = document.documentElement.clientWidth, out = [];
  if (document.documentElement.scrollWidth > vw + 1) out.push(`page ${document.documentElement.scrollWidth}px > screen ${vw}px`);
  for (const el of document.querySelectorAll('main *, .page *')) {
    const r = el.getBoundingClientRect();
    if (!r.width || el.closest('.table-wrap, [data-lab-scroll]')) continue;
    if (r.right > vw + 1 || r.left < -1) out.push(`${el.tagName.toLowerCase()}.${String(el.className).split(' ')[0]} outside the screen`);
  }
  return [...new Set(out)].slice(0, 6);
};
// Frame times while the page scrolls (smoothness under the throttled CPU).
const FRAMES = async (ms) => {
  const times = [];
  let last = performance.now();
  const end = last + ms;
  const scroller = document.scrollingElement;
  const max = Math.max(0, scroller.scrollHeight - innerHeight);
  await new Promise((res) => {
    const tick = (now) => {
      times.push(now - last); last = now;
      if (max) scroller.scrollTop = ((now % 1200) / 1200) * max;
      if (now < end) requestAnimationFrame(tick); else res();
    };
    requestAnimationFrame(tick);
  });
  scroller.scrollTop = 0;
  times.shift();
  times.sort((a, b) => a - b);
  const pct = (p) => times[Math.min(times.length - 1, Math.floor(p * times.length))] || 0;
  return { frames: times.length, p50: +pct(0.5).toFixed(1), p95: +pct(0.95).toFixed(1), dropped: +(times.filter((t) => t > 20).length / Math.max(1, times.length)).toFixed(3),
    fps: +(1000 / (times.reduce((a, b) => a + b, 0) / Math.max(1, times.length))).toFixed(1) };
};

async function act(page, steps = []) {
  for (const [kind, sel, value] of steps) {
    if (kind === 'fill') await page.fill(sel, value);
    else if (kind === 'click') await page.click(sel);
    else if (kind === 'press') await page.press(sel, value);
    else if (kind === 'wait') await page.waitForSelector(sel, { timeout: 15000 });
    else if (kind === 'sleep') await page.waitForTimeout(Number(sel));
  }
}

const browser = await chromium.launch({ executablePath: process.env.CHROMIUM || (fs.existsSync('/opt/pw-browsers/chromium') ? '/opt/pw-browsers/chromium' : undefined) });
const results = [];
for (const [w, h] of viewports) {
  const ctx = await browser.newContext({ viewport: { width: w, height: h } });
  if (cfg.init_storage) await ctx.addInitScript((s) => { for (const [k, v] of Object.entries(s)) localStorage.setItem(k, v); }, cfg.init_storage);
  await ctx.addInitScript(OBSERVE);
  const page = await ctx.newPage();
  const errors = [];
  page.on('pageerror', (e) => errors.push(String(e)));
  page.on('console', (m) => { if (m.type() === 'error' && !/status of 4\d\d/.test(m.text())) errors.push(m.text()); });
  const cdp = await ctx.newCDPSession(page);
  await page.goto(cfg.base);
  if (cfg.login) { await act(page, cfg.login.steps); await page.waitForSelector(cfg.login.ready, { timeout: 20000 }); }
  for (const route of routes) {
    const bytes = { script: 0, stylesheet: 0, font: 0, document: 0, fetch: 0, other: 0 };
    const onResp = async (r) => {
      const type = r.request().resourceType();
      const len = Number((await r.headerValue('content-length').catch(() => 0)) || 0);
      bytes[type in bytes ? type : 'other'] += len;
    };
    page.on('response', onResp);
    await cdp.send('Network.clearBrowserCache').catch(() => {});
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: cpu });
    const t0 = Date.now();
    await page.goto(cfg.base + (cfg.route_prefix || '/#/') + route, { waitUntil: 'load' });
    await page.reload({ waitUntil: 'load' });  // a cold load of this exact page, not an in-app hop
    if (cfg.login?.ready) await page.waitForSelector(cfg.login.ready, { timeout: 30000 });
    await page.waitForTimeout(args.quick ? 600 : 1500);
    const loadMs = Date.now() - t0;
    const nav = await page.evaluate(() => { const n = performance.getEntriesByType('navigation')[0] || {}; const p = performance.getEntriesByName('first-contentful-paint')[0];
      return { ttfb: Math.round(n.responseStart || 0), dcl: Math.round(n.domContentLoadedEventEnd || 0), fcp: Math.round(p ? p.startTime : 0) }; });
    if (cfg.interact?.[route]) await act(page, cfg.interact[route]).catch((e) => errors.push('interaction: ' + e.message.split('\n')[0]));
    const frames = await page.evaluate(FRAMES, args.quick ? 1000 : 2000);
    await cdp.send('Emulation.setCPUThrottlingRate', { rate: 1 });
    const lab = await page.evaluate(() => ({ ...window.__lab, dom: document.getElementsByTagName('*').length,
      heap: performance.memory ? Math.round(performance.memory.usedJSHeapSize / 1048576) : null }));
    const tbt = lab.long.reduce((a, [, d]) => a + Math.max(0, d - 50), 0);
    const inp = lab.events.length ? Math.max(...lab.events) : 0;
    const overflow = await page.evaluate(OVERFLOW);
    let a11y = { skipped: !axeSource, serious: 0, critical: 0, ids: [] };
    if (axeSource) {
      // through DevTools, so the page's own Content-Security-Policy stays exactly as shipped
      await cdp.send('Runtime.evaluate', { expression: axeSource }).catch(() => { a11y.skipped = 'injection failed'; });
      if (!a11y.skipped) {
        const r = await page.evaluate(async () => window.axe ? (await window.axe.run(document, { resultTypes: ['violations'] })).violations.map((v) => [v.id, v.impact, v.nodes.length]) : null);
        if (r) { a11y = { skipped: false, serious: r.filter((v) => v[1] === 'serious').length, critical: r.filter((v) => v[1] === 'critical').length, ids: r.map((v) => `${v[0]}(${v[1]},${v[2]})`) }; }
      }
    }
    page.off('response', onResp);
    const shot = path.join(outDir, `${route.replace(/[^\w]+/g, '_')}-${w}.png`);
    await page.screenshot({ path: shot });
    results.push({ route, viewport: `${w}x${h}`, cpu, load_ms: loadMs, ...nav, lcp: Math.round(lab.lcp), cls: +lab.cls.toFixed(3), tbt: Math.round(tbt), inp: Math.round(inp),
      ...Object.fromEntries(Object.entries(frames).map(([k, v]) => ['frame_' + k, v])), dom: lab.dom, heap_mb: lab.heap,
      kb: Object.fromEntries(Object.entries(bytes).map(([k, v]) => [k, Math.round(v / 1024)])), overflow, a11y, errors: [...errors], screenshot: path.basename(shot) });
    errors.length = 0;
  }
  await ctx.close();
}
await browser.close();

// ---------------------------------------------------------------- verdicts
const B = budgets.page;
const checks = (r) => [
  ['FCP', r.fcp, B.fcp_ms, 'ms'], ['LCP', r.lcp || r.fcp, B.lcp_ms, 'ms'], ['CLS', r.cls, B.cls, ''], ['TBT (CPU ×' + r.cpu + ')', r.tbt, B.tbt_ms, 'ms'],
  ['INP', r.inp, B.inp_ms, 'ms'], ['frame p95', r.frame_p95, B.frame_p95_ms, 'ms'], ['dropped frames', r.frame_dropped, B.dropped_ratio, ''],
  ['DOM nodes', r.dom, B.dom_nodes, ''], ['JS heap', r.heap_mb ?? 0, B.heap_mb, 'MB'], ['overflow', r.overflow.length, 0, ''],
  ['a11y serious+critical', r.a11y.skipped ? 0 : r.a11y.serious + r.a11y.critical, B.a11y_serious, ''], ['console errors', r.errors.length, 0, ''],
].map(([name, v, max, unit]) => ({ name, value: v, max, unit, ok: v <= max }));
let failed = 0;
const lines = [`# UI Lab report — ${new Date().toISOString().slice(0, 16)}`, '', `Base: ${cfg.base} · CPU throttle ×${cpu} · budgets: ${budgets.version}`, '',
  '| Page | Screen | FCP | LCP | CLS | TBT | INP | p95 frame | FPS | DOM | JS kB | Fits | a11y | Verdict |', '|---|---|---|---|---|---|---|---|---|---|---|---|---|---|'];
for (const r of results) {
  const c = checks(r);
  r.checks = c;
  r.pass = c.every((x) => x.ok);
  if (!r.pass) failed++;
  lines.push(`| ${r.route} | ${r.viewport} | ${r.fcp} | ${r.lcp} | ${r.cls} | ${r.tbt} | ${r.inp} | ${r.frame_p95} | ${r.frame_fps} | ${r.dom} | ${r.kb.script} | ${r.overflow.length ? '✗' : '✓'} | ${r.a11y.skipped ? 'skipped' : r.a11y.serious + r.a11y.critical} | ${r.pass ? 'PASS' : 'FAIL: ' + c.filter((x) => !x.ok).map((x) => `${x.name} ${x.value}${x.unit}>${x.max}`).join(', ')} |`);
}
const totalJs = Math.max(...results.map((r) => r.kb.script));
lines.push('', `Largest JS transfer of one page: ${totalJs} kB (budget ${budgets.bundle.js_kb} kB).`, '', '## Accessibility findings', '');
for (const r of results) if (r.a11y.ids?.length) lines.push(`- ${r.route} ${r.viewport}: ${r.a11y.ids.join(', ')}`);
for (const r of results) if (r.overflow.length || r.errors.length) lines.push(`- ${r.route} ${r.viewport}: ${[...r.overflow, ...r.errors].join(' · ')}`);
if (totalJs > budgets.bundle.js_kb) failed++;
fs.writeFileSync(path.join(outDir, 'report.json'), JSON.stringify({ when: new Date().toISOString(), cpu, budgets: budgets.version, results }, null, 1));
fs.writeFileSync(path.join(outDir, 'REPORT.md'), lines.join('\n') + '\n');
console.log(lines.join('\n'));
console.log(failed ? `\n${failed} page(s) over budget.` : '\nAll pages within budget.');
process.exit(failed ? 1 : 0);
