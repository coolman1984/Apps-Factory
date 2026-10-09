/* The demo shop: hash routing, a few forms, and the af-guide wiring a product needs (about 20 lines). */
(async function () {
  'use strict';
  const get = n => fetch('/guide/' + n + '.json').then(r => r.json());
  const [catalogue, ar, en, uiAr, uiEn] = await Promise.all(['catalogue', 'ar', 'en', 'ui-ar', 'ui-en'].map(get));
  const ui = {ar: uiAr, en: uiEn};
  const $ = s => document.querySelector(s);
  const route = () => (location.hash.slice(1) || 'home');
  const role = (document.cookie.match(/demo_role=(\w+)/) || [])[1] || 'cashier';
  document.querySelectorAll('[data-ui]').forEach(n => { n.textContent = uiAr[n.dataset.ui]; });
  const nav = $('#nav');
  for (const p of ['home', 'sell', 'shift', 'stock', 'people', 'help']) {
    const a = document.createElement('a');
    a.href = '#' + p; a.textContent = uiAr['nav.' + p] || p; a.dataset.nav = p;
    nav.append(a, ' ');
  }
  const post = (url, body) => fetch(url, {method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)}).then(r => r.json());

  // ---- af-guide wiring ----
  const guide = window.AFGuide.init({
    catalogue, texts: {ar, en}, ui: (k, l) => ui[l][k], uiLang: 'ar', role, route,
    go: p => { location.hash = p; }, can: () => true,
    track: (type, data) => { (window.__events = window.__events || []).push({type, data}); },
    onReport: ctx => { window.__report = ctx; }
  });
  window.__afguide = guide;   // testing/walk_guides.py drives it through this handle
  $('#help-slot').append(guide.helpButton());
  // -------------------------

  function show() {
    document.querySelectorAll('[data-page]').forEach(s => { s.hidden = s.dataset.page !== route(); });
    guide.routeChanged();
  }
  addEventListener('hashchange', show);
  show();
  let mode = null;
  $('[data-guide="shift.open"]').onclick = () => { mode = 'open'; $('#shift-form').hidden = false; $('[data-guide="shift.cash"]').hidden = false; $('[data-guide="shift.counted"]').hidden = true; };
  $('[data-guide="shift.close"]').onclick = () => { mode = 'close'; $('#shift-form').hidden = false; $('[data-guide="shift.cash"]').hidden = true; $('[data-guide="shift.counted"]').hidden = false; };
  $('[data-guide="shift.save"]').onclick = async () => {
    $('#shift-form').hidden = true;
    if (mode === 'open') { $('#shift-status').textContent = 'مفتوحة'; await post('/api/demo/state', {state: 'shift.open'}); guide.signal('shift.opened'); }
    else { $('#shift-status').textContent = 'مغلقة'; guide.signal('shift.closed'); }
  };
  $('[data-guide="sell.pay"]').onclick = () => { $('[data-guide="sell.done"]').hidden = false; };
  $('[data-guide="sell.done"]').onclick = async () => { $('[data-guide="sell.done"]').hidden = true; await post('/api/demo/state', {state: 'sale.first'}); guide.signal('sale.done'); };
  $('[data-guide="stock.new"]').onclick = () => { $('#stock-form').hidden = false; };
  $('[data-guide="stock.save"]').onclick = () => { $('#stock-form').hidden = true; };
  $('[data-guide="people.new"]').onclick = () => { $('#people-form').hidden = false; };
  $('[data-guide="people.save"]').onclick = () => { $('#people-form').hidden = true; guide.signal('person.saved'); };
  $('#sell-without-shift').onclick = () => {
    const box = $('#error');
    box.replaceChildren('لا توجد وردية مفتوحة. ');
    const b = guide.errorButton('sale.no_shift');
    if (b) box.append(b);
  };
})();
