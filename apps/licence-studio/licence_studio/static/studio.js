// Licence Studio page (owner only, this PC only). Arabic first, plain modules, no build step.
const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
class Raw { constructor(s) { this.s = s; } }
const raw = (s) => new Raw(String(s));
const enc = (v) => (v === null || v === undefined || v === false ? '' : v instanceof Raw ? v.s : Array.isArray(v) ? v.map(enc).join('') : String(v).replace(/[&<>"']/g, (c) => ESC[c]));
const html = (str, ...vals) => raw(str.reduce((a, s, i) => a + s + (i < vals.length ? enc(vals[i]) : ''), ''));
const put = (el, c) => { el.innerHTML = enc(c); return el; };
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const icon = (n) => raw(`<svg class="i" aria-hidden="true"><use href="/af-ui/img/icons.svg#${n}"/></svg>`);
const CUR = raw('aria-current="page"');

async function api(method, path, body) {
  const r = await fetch(path, { method, credentials: 'same-origin', headers: body ? { 'Content-Type': 'application/json' } : {}, body: body ? JSON.stringify(body) : undefined });
  const type = r.headers.get('Content-Type') || '';
  const data = type.includes('json') ? await r.json() : await r.text();
  if (!r.ok) { const e = new Error(data.error || 'error'); e.status = r.status; e.key = data.key; throw e; }
  return data;
}
const get = (p) => api('GET', p);
const post = (p, b = {}) => api('POST', p, b);

let toastBox;
function toast(text, bad = false) {
  toastBox = toastBox || document.body.appendChild(Object.assign(document.createElement('div'), { className: 'toasts' }));
  const el = document.createElement('div');
  el.className = 'toast' + (bad ? ' bad' : '');
  put(el, html`${icon(bad ? 'alert' : 'check-circle')}<span>${text}</span>`);
  toastBox.appendChild(el);
  setTimeout(() => el.remove(), bad ? 5000 : 2600);
}
async function copy(text) { try { await navigator.clipboard.writeText(text); toast('اتنسخ'); } catch { toast('انسخ يدويًا', true); } }
const today = () => new Date().toISOString().slice(0, 10);
const addDays = (d, n) => { const x = new Date(d + 'T12:00:00'); x.setDate(x.getDate() + n); return x.toISOString().slice(0, 10); };
const fmt = (d) => (d ? d.split('-').reverse().join('/') : '');
const STATUS = { active: 'شغال', grace: 'سماح', expired: 'خلص', not_started: 'لسه مبدأش' };
const EDITION = { trial: 'تجربة', standard: 'عادي', pro: 'برو', perpetual: 'دائم' };
// The three kinds a shop buys: [label, edition, days, grace days]. Days and grace stay editable after picking one.
const PRESETS = [['تجربة 14 يوم', 'trial', 14, 0], ['اشتراك شهري', 'standard', 30, 3], ['تفعيل دائم', 'perpetual', 0, 0]];
const until = (c) => (c.edition === 'perpetual' ? 'دائم، مش بيخلص' : fmt(c.last_day));

let ST = {}, PRODUCTS = [];

async function boot() {
  try { ST = await get('/api/status'); } catch { put(document.body, html`<div class="gate"><div class="card"><h1>مش قادر يوصل</h1></div></div>`); return; }
  if (!ST.key) return gateCreate();
  if (!ST.owner) return gateUnlock();
  PRODUCTS = await get('/api/products');
  shell();
}

function gateCreate() {
  put(document.body, html`<div class="gate"><form class="card" id="g">
    <div class="brand"><div class="brand-mark">${icon('key')}</div><div><div class="brand-name">برنامج الأكواد</div><div class="xs faint">Licence Studio</div></div></div>
    <h1>نعمل مفتاح التوقيع</h1>
    <p class="muted">المفتاح ده هو اللي بيطلّع الأكواد. بيتعمل مرة واحدة بس، ومتشفّر بكلمة سر طويلة إنت بس اللي تعرفها.</p>
    <div class="field"><label for="p1">كلمة السر (جملة قصيرة 12 حرف أو أكتر)</label><input id="p1" type="password" class="input big" autocomplete="new-password" autofocus></div>
    <div class="field"><label for="p2">اكتبها تاني</label><input id="p2" type="password" class="input big" autocomplete="new-password"></div>
    <div class="tip warn">${icon('alert')}<div>لو كلمة السر ضاعت، المفتاح بيضيع، وكل نسخ البرامج هتحتاج مفتاح جديد. اكتبها في ورقة وحطها في مكان آمن.</div></div>
    <p class="err small" id="e"></p><button class="btn volt lg">اعمل المفتاح</button></form></div>`);
  $('#g').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    if ($('#p1').value !== $('#p2').value) { $('#e').textContent = 'الكلمتين مش زي بعض.'; return; }
    try { const r = await post('/api/key/create', { passphrase: $('#p1').value }); toast('المفتاح اتعمل'); showKeyDone(r); } catch (e) { $('#e').textContent = e.message; }
  });
}

function showKeyDone(r) {
  put(document.body, html`<div class="gate"><div class="card"><h1>المفتاح جاهز ✓</h1>
    <p class="muted">ده <b>المفتاح العام</b>. بيتحط في كل برنامج عشان يتأكد إن الكود منك. ده مش سر.</p>
    <div class="code-out" id="pub">${r.public}</div><button class="btn" id="cp">${icon('clipboard')}انسخ المفتاح العام</button>
    <div class="tip warn">${icon('alert')}<div>اعمل نسختين من فولدر المفتاح على فلاشتين، وخليهم برة الكمبيوتر: <span class="mono">${r.file}</span></div></div>
    <button class="btn volt lg" id="go">ابدأ</button></div></div>`);
  $('#cp').addEventListener('click', () => copy(r.public));
  $('#go').addEventListener('click', boot);
}

function gateUnlock() {
  put(document.body, html`<div class="gate"><form class="card" id="g">
    <div class="brand"><div class="brand-mark">${icon('key')}</div><div><div class="brand-name">برنامج الأكواد</div><div class="xs faint">Licence Studio</div></div></div>
    <h1>افتح البرنامج</h1><p class="muted">اكتب كلمة سر المفتاح. البرنامج بيقفل نفسه لوحده بعد 30 دقيقة من غير استخدام.</p>
    <div class="field"><label for="pp">كلمة السر</label><input id="pp" type="password" class="input big" autocomplete="current-password" autofocus></div>
    <p class="err small" id="e"></p><button class="btn volt lg">افتح</button></form></div>`);
  $('#g').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    try { await post('/api/unlock', { passphrase: $('#pp').value }); boot(); } catch (e) { $('#e').textContent = e.status === 403 ? 'كلمة السر غلط.' : e.message; $('#pp').select(); }
  });
}

const PAGES = [['issue', 'key', 'طلّع كود'], ['codes', 'receipt', 'الأكواد'], ['requests', 'message', 'طلبات المحلات'], ['verify', 'shield', 'افحص كود'],
  ['products', 'box', 'المنتجات'], ['keys', 'lock', 'المفتاح'], ['agent', 'sparkle', 'الإيجنت والسجل']];

function shell() {
  put(document.body, html`<div class="shell"><aside class="rail"><div class="rail-in">
    <div class="brand"><div class="brand-mark">${icon('key')}</div><div class="grow"><div class="brand-name">برنامج الأكواد</div><div class="brand-shop">Licence Studio</div></div></div>
    <nav class="nav">${PAGES.map(([id, ic, label]) => html`<a href="#/${id}" data-route="${id}" class="${id === 'issue' ? 'hot' : ''}">${icon(ic)}<span class="grow">${label}</span>
      ${id === 'requests' && ST.pending_requests ? html`<span class="count">${ST.pending_requests}</span>` : ''}${id === 'codes' && ST.expiring_soon ? html`<span class="count">${ST.expiring_soon}</span>` : ''}</a>`)}</nav>
    <div class="rail-foot"><button class="btn block" id="lock">${icon('lock')}اقفل دلوقتي</button></div></div></aside>
    <div class="main"><main class="page" id="page"></main></div></div>`);
  $('#lock').addEventListener('click', async () => { await post('/api/lock'); boot(); });
  window.onhashchange = route;
  route();
}

async function route() {
  const [name, q] = (location.hash.replace(/^#\/?/, '') || 'issue').split('?');
  const params = Object.fromEntries(new URLSearchParams(q || ''));
  $$('[data-route]').forEach((a) => (a.dataset.route === name ? a.setAttribute('aria-current', 'page') : a.removeAttribute('aria-current')));
  const page = $('#page');
  page.className = 'page enter';
  try {
    await ({ issue, codes, requests, verify, products, keys, agent }[name] || issue)(page, params);
  } catch (e) {
    if (e.status === 401) return boot();
    toast(e.message, true);
  }
}

const head = (title, sub, actions = '') => html`<div class="page-head"><div class="titles"><h1>${title}</h1><p>${sub}</p></div><div class="actions">${actions}</div></div>`;

async function issue(page, p) {
  const prod = PRODUCTS.find((x) => x.id === p.product) || PRODUCTS[0];
  put(page, html`${head('طلّع كود', 'كود التجربة بيتربط بجهاز العميل ومدته 14 يوم. البرنامج اللي عند العميل بيوريه «رقم الجهاز» في الإعدادات ← الرخصة.')}
    <div class="two"><form class="card form" id="f">
      <div class="cols"><div class="field"><label for="pr">البرنامج</label><select id="pr" class="input">${PRODUCTS.map((x) => html`<option value="${x.id}" ${x.id === prod?.id ? raw('selected') : ''}>${x.name}</option>`)}</select></div>
        <div class="field"><span class="label">النوع</span><div class="seg" id="ed">${Object.entries(EDITION).map(([k, v]) => html`<button type="button" data-v="${k}" aria-pressed="${k === (p.edition || 'trial')}">${v}</button>`)}</div></div></div>
      <div class="field"><span class="label">اختيار سريع</span><div class="row wrap" id="ps">${PRESETS.map(([label], i) => html`<button type="button" class="chip" data-preset="${i}">${label}</button>`)}</div></div>
      <div class="field"><label for="dv">رقم الجهاز</label><input id="dv" class="input device-in" placeholder="XXXXX-XXXXX" value="${p.device || ''}" autocomplete="off" maxlength="11" autofocus>
        <span class="hint">10 حروف وأرقام. لو العميل كتب O بدل 0 أو I بدل 1 البرنامج بيصلحها لوحده.</span></div>
      <div class="cols"><div class="field"><label for="cu">اسم العميل / المحل</label><input id="cu" class="input" value="${p.customer || ''}"></div>
        <div class="field"><label for="ph">الموبايل (للواتساب)</label><input id="ph" class="input mono" value="${p.phone || ''}" inputmode="tel"></div></div>
      <div class="cols"><div class="field"><span class="label">المدة (أيام)</span><div class="row wrap" id="dz">${[14, 30, 90, 365].map((n) => html`<button type="button" class="chip" data-d="${n}">${n}</button>`)}
        <input id="days" class="input q-in mono" value="${p.days || prod?.trial_days || 14}" inputmode="numeric"></div></div>
        <div class="field"><label for="fd">من يوم</label><input id="fd" type="date" class="input" value="${today()}" min="${today()}"></div>
        <div class="field"><label for="gr">أيام سماح</label><input id="gr" class="input mono" value="0" inputmode="numeric"></div></div>
      <div class="field"><label for="nt">ملاحظة</label><input id="nt" class="input" value="${p.note || ''}"></div>
      <div class="preview-line" id="pv"></div>
      <p class="err small" id="e"></p>
      <button class="btn volt lg">${icon('key')}اعمل الكود</button></form>
      <div id="out" class="stack"><div class="card"><div class="empty">${icon('key')}<h3>الكود هيظهر هنا</h3><p>انسخه وابعته للعميل على واتساب.</p></div></div></div></div>`);
  let edition = p.edition || 'trial';
  const setEdition = (v) => {
    edition = v;
    $$('#ed button').forEach((x) => x.setAttribute('aria-pressed', String(x.dataset.v === v)));
    ['#days', '#gr'].forEach((s) => { $(s).disabled = v === 'perpetual'; });
  };
  const pv = () => {
    const d = +$('#days').value || 0;
    if (edition === 'perpetual') {
      put($('#pv'), html`${icon('calendar')}<span>${EDITION[edition]} · من <span class="mono">${fmt($('#fd').value)}</span> · <b>مش بيخلص</b>
        ${$('#dv').value ? html` · مربوط بجهاز <span class="mono">${$('#dv').value.toUpperCase()}</span>` : html` · <b>لازم رقم الجهاز</b>`}</span>`);
      return;
    }
    put($('#pv'), html`${icon('calendar')}<span>${EDITION[edition]} · <b>${d}</b> يوم · من <span class="mono">${fmt($('#fd').value)}</span> لحد <span class="mono">${fmt(addDays($('#fd').value, d - 1))}</span>
      ${$('#dv').value ? html` · مربوط بجهاز <span class="mono">${$('#dv').value.toUpperCase()}</span>` : html` · <b>مش مربوط بجهاز</b>`}</span>`);
  };
  $$('#ed button').forEach((b) => b.addEventListener('click', () => { setEdition(b.dataset.v); if (edition !== 'trial' && +$('#days').value === 14) $('#days').value = 365; pv(); }));
  $$('[data-preset]').forEach((b) => b.addEventListener('click', () => {
    const [, ed, days, grace] = PRESETS[+b.dataset.preset];
    setEdition(ed);
    if (days) $('#days').value = days;
    $('#gr').value = grace;
    pv();
  }));
  $$('[data-d]').forEach((b) => b.addEventListener('click', () => { $('#days').value = b.dataset.d; pv(); }));
  ['#days', '#fd', '#dv'].forEach((s) => $(s).addEventListener('input', pv));
  $('#dv').addEventListener('input', (e) => { const v = e.target.value.toUpperCase().replace(/[^0-9A-Z]/g, '').slice(0, 10); e.target.value = v.length > 5 ? v.slice(0, 5) + '-' + v.slice(5) : v; pv(); });
  $('#pr').addEventListener('change', (e) => { const x = PRODUCTS.find((y) => y.id === e.target.value); if (edition === 'trial') $('#days').value = x.trial_days; pv(); });
  setEdition(edition);
  pv();
  $('#f').addEventListener('submit', async (ev) => {
    ev.preventDefault();
    $('#e').textContent = '';
    const btn = ev.submitter; btn.setAttribute('aria-busy', 'true');
    try {
      const c = await post('/api/issue', { product: $('#pr').value, edition, device: $('#dv').value || null, customer: $('#cu').value, phone: $('#ph').value,
        days: +$('#days').value, first_day: $('#fd').value, grace_days: +$('#gr').value || 0, note: $('#nt').value });
      showCode($('#out'), c);
      toast('الكود اتعمل ✓');
    } catch (e) { $('#e').textContent = e.status === 423 ? 'البرنامج اتقفل. افتحه تاني.' : e.message; if (e.status === 401 || e.status === 423) setTimeout(boot, 1200); }
    btn.removeAttribute('aria-busy');
  });
}

function waLink(c) {
  const prod = PRODUCTS.find((x) => x.id === c.product)?.name || c.product;
  const text = `أهلًا ${c.customer || ''}\nده كود تشغيل ${prod} (${EDITION[c.edition]}) ${c.edition === 'perpetual' ? 'دائم' : 'لحد ' + fmt(c.last_day)}:\n\n${c.code}\n\nافتح البرنامج ← الإعدادات ← الرخصة، والصق الكود، ودوس «شغّل بالكود».`;
  let ph = (c.phone || '').replace(/\D/g, ''); if (ph.startsWith('0')) ph = '2' + ph;
  return `https://wa.me/${ph}?text=${encodeURIComponent(text)}`;
}

function showCode(box, c) {
  put(box, html`<div class="card volt-card"><div class="row between"><h2>${c.customer || 'كود جديد'}</h2><span class="badge">${EDITION[c.edition]}</span></div>
    <p class="small">لحد <b class="mono">${until(c)}</b> · رقم الكود <span class="mono">${c.serial}</span>${c.device ? html` · جهاز <span class="mono">${c.device}</span>` : ''}</p></div>
    <div class="card"><div class="code-out" id="code">${c.code}</div><div class="row wrap">
      <button class="btn primary" id="cp">${icon('clipboard')}انسخ الكود</button>
      <a class="btn" target="_blank" rel="noopener" href="${waLink(c)}">${icon('message')}ابعته واتساب</a></div></div>`);
  $('#cp', box).addEventListener('click', () => copy(c.code));
}

async function codes(page, p) {
  put(page, html`${head('الأكواد', 'كل كود اتعمل، وحالته، وفاضل له قد إيه. الكود مبيتمسحش، وعشان تجدّد بتعمل كود جديد.', html`<a class="btn" href="/api/export.csv">${icon('download')}إكسل</a>`)}
    <div class="toolbar"><input id="q" class="input" placeholder="اسم، موبايل، رقم جهاز، رقم كود…" value="${p.q || ''}">
    <div class="seg" id="st">${[['', 'الكل'], ['expiring', 'خلصان قريب'], ['active', 'شغال'], ['expired', 'خلص']].map(([k, v]) => html`<button type="button" data-v="${k}" aria-pressed="${k === (p.status || '')}">${v}</button>`)}</div></div>
    <div id="list"></div>`);
  let status = p.status || '';
  const load = async () => {
    const rows = await get('/api/codes?' + new URLSearchParams({ q: $('#q').value, status }));
    put($('#list'), rows.length ? html`<div class="card pad-0"><div class="table-wrap"><table class="t"><thead><tr><th>العميل</th><th>البرنامج</th><th>النوع</th><th>الجهاز</th>
      <th>لحد</th><th>الحالة</th><th>اتعمل بواسطة</th></tr></thead><tbody>${rows.map((c) => html`<tr class="click" data-s="${c.serial}"><td class="name">${c.customer || '—'}<div class="xs faint mono">${c.serial}</div></td>
      <td>${c.product}</td><td>${EDITION[c.edition]}</td><td class="mono">${c.device || '—'}</td><td class="mono">${until(c)}</td>
      <td><span class="badge status-${c.status}">${STATUS[c.status]}${c.status === 'active' && c.days_left !== null ? ' · ' + c.days_left + ' يوم' : ''}</span></td><td>${c.issued_by === 'agent' ? 'الإيجنت' : c.issued_by === 'telegram' ? 'موافقتك على تليجرام' : c.issued_by === 'auto-trial' ? 'السياسة التلقائية' : 'صاحب البرنامج'}</td></tr>`)}</tbody></table></div></div>`
      : html`<div class="card"><div class="empty">${icon('receipt')}<h3>مفيش أكواد</h3></div></div>`);
    $$('tr[data-s]').forEach((tr) => tr.addEventListener('click', () => codeFile(rows.find((r) => r.serial === tr.dataset.s))));
  };
  $$('#st button').forEach((b) => b.addEventListener('click', () => { status = b.dataset.v; $$('#st button').forEach((x) => x.setAttribute('aria-pressed', String(x === b))); load(); }));
  let t; $('#q').addEventListener('input', () => { clearTimeout(t); t = setTimeout(load, 200); });
  load();
}

function codeFile(c) {
  const scrim = document.createElement('div');
  scrim.className = 'scrim side';
  put(scrim, html`<div class="panel"><div class="dialog-head"><h2>${c.customer || c.serial}</h2><button class="icon-btn" data-x>${icon('x')}</button></div>
    <div class="dialog-body"><div class="grid kpis"><div class="kpi"><span class="label">الحالة</span><span class="value">${STATUS[c.status]}</span></div>
    <div class="kpi"><span class="label">لحد</span><span class="value mono">${until(c)}</span></div></div>
    <div class="stat-line"><span>البرنامج</span><b>${c.product}</b></div><div class="stat-line"><span>النوع</span><b>${EDITION[c.edition]}</b></div>
    <div class="stat-line"><span>الجهاز</span><b class="mono">${c.device || '—'}</b></div><div class="stat-line"><span>الموبايل</span><b class="mono">${c.phone || '—'}</b></div>
    <div class="stat-line"><span>اتعمل</span><b class="mono">${c.issued_at}</b></div>${c.note ? html`<div class="stat-line"><span>ملاحظة</span><b>${c.note}</b></div>` : ''}
    <div class="code-out">${c.code}</div></div>
    <div class="dialog-foot"><button class="btn" data-cp>${icon('clipboard')}نسخ</button><a class="btn" target="_blank" rel="noopener" href="${waLink(c)}">${icon('message')}واتساب</a>
    <a class="btn volt" href="#/issue?${new URLSearchParams({ product: c.product, device: c.device || '', customer: c.customer, phone: c.phone, edition: c.edition })}">${icon('refresh')}كود جديد لنفس الجهاز</a></div></div>`);
  document.body.appendChild(scrim);
  const close = () => scrim.remove();
  $('[data-x]', scrim).addEventListener('click', close);
  scrim.addEventListener('mousedown', (e) => { if (e.target === scrim) close(); });
  $('[data-cp]', scrim).addEventListener('click', () => copy(c.code));
  $$('a.btn.volt', scrim).forEach((a) => a.addEventListener('click', close));
}

const KIND = { trial: 'تجربة 14 يوم', monthly: 'اشتراك شهري', permanent: 'تفعيل دائم' };
const HELD = { locked: 'البرنامج مقفول: افتحه وهيتعمل لوحده', daily_cap: 'عدد التجارب النهاردة وصل الحد', review_src: 'طلبات كتير من نفس المكان: راجعها', payment_needed: 'مستني تأكيد الدفع',
  already_used: 'الكمبيوتر ده خد تجربة قبل كده', owner_refused: 'إنت رفضت', expired: 'الطلب انتهى عند الوسيط', closed_elsewhere: 'الطلب اتقفل عند الوسيط', relay_gone: 'الوسيط مابقاش يعرف الطلب ده: راجعه بنفسك', bad_device: 'رقم الجهاز مش مظبوط', bad_machine: 'بصمة الكمبيوتر مش مظبوطة', unknown_product: 'البرنامج مش معروف' };
const POLICY_SAYS = { issue: 'السياسة هتصدّره لوحدها', reissue: 'السياسة هتبعت نفس الكود تاني', refuse: 'السياسة هترفضه', hold: 'السياسة هتسيبه لك' };

async function relayPanel(page) {
  const r = await get('/api/relay');
  const pol = r.policy;
  const last = r.last || {};
  const state = !r.configured ? 'الوسيط لسه مش متظبط' : last.ok === false ? 'مفيش اتصال بالوسيط (' + (last.error || '') + ')' : last.at ? 'آخر سحب ' + last.at.replace('T', ' ').slice(0, 19) : 'لسه ماسحبش';
  put($('#relay-box'), html`<div class="card"><div class="card-head"><h2>طلبات المحلات (التجربة التلقائية)</h2>
      <span class="badge ${r.configured && last.ok !== false ? 'ok' : 'warn'}">${state}</span></div>
    <p class="small muted">المحل بيطلب تجربة من برنامجه، وإشعار بيوصلك على تليجرام بزرارين: «✅ موافق» و«❌ رفض». لو وافقت، البرنامج ده (على جهازك) هو اللي بيصدر الكود ويرجّعه للمحل ويتفعّل من غير نسخ ولصق، وبيتبعتلك نسخة من الكود على تليجرام. المفتاح السري بيفضل على الجهاز ده بس.</p>
    <div class="two"><form class="form" id="rf"><div class="field"><label for="ru">عنوان الوسيط (https://…)</label><input id="ru" class="input mono" value="${r.url || ''}" placeholder="https://xxxx.workers.dev" autocomplete="off"></div>
      <div class="field"><label for="rt">مفتاح الوسيط ${r.has_token ? '(محفوظ، اكتب جديد لو عايز تغيّره)' : ''}</label><input id="rt" type="password" class="input mono" autocomplete="off"></div>
      <p class="err small" id="re"></p><div class="row wrap"><button class="btn primary">${icon('check')}احفظ</button><button type="button" class="btn" id="pull" ${r.configured ? '' : raw('disabled')}>${icon('refresh')}اسحب الطلبات دلوقتي</button></div></form>
    <div class="stack tight">
      <div class="toggle-row"><div><b>اصدر التجارب لوحدك</b><div class="small muted">تجربة 14 يوم، مربوطة بالجهاز، وجهاز واحد مايخدش تجربة تانية. المدفوع مايتعملش لوحده أبدًا.</div></div>
        <label class="check"><input type="checkbox" id="au" ${pol.auto_trials ? raw('checked') : ''}>شغّال</label></div>
      <div class="toggle-row"><div><b>أقصى تجارب في اليوم</b></div><input id="cap" class="input q-in mono" value="${pol.auto_trial_daily_cap}" inputmode="numeric"></div>
      <div class="toggle-row"><div><b>افضل مفتوح عشان يصدّر وإنت مش قدام الجهاز</b><div class="small muted">${pol.keep_unlocked_until ? 'مفتوح لحد ' + pol.keep_unlocked_until.replace('T', ' ').slice(0, 16) : 'مقفول بعد 30 دقيقة من غير استخدام'}. أقصى حاجة 12 ساعة.</div></div>
        <div class="row"><input id="kh" class="input q-in mono" value="8" inputmode="numeric"><button type="button" class="btn sm" id="keep">افضل مفتوح</button></div></div></div></div></div>`);
  $('#rf').addEventListener('submit', async (e) => {
    e.preventDefault();
    try { await post('/api/relay/save', { url: $('#ru').value, token: $('#rt').value || undefined }); toast('اتحفظ'); relayPanel(page); } catch (err) { $('#re').textContent = err.message; }
  });
  $('#pull').addEventListener('click', async () => {
    try { const o = await post('/api/relay/pull'); toast(o.ok === false ? 'مفيش اتصال' : `اتسحب ${o.pulled} · اتصدّر ${o.issued} · اترفض ${o.refused} · مستني ${o.held}`, o.ok === false); ST = await get('/api/status'); requests(page); } catch (err) { toast(err.message, true); }
  });
  $('#au').addEventListener('change', async (e) => { await post('/api/policy', { auto_trials: e.target.checked }); toast('اتحفظ'); });
  $('#cap').addEventListener('change', async (e) => { await post('/api/policy', { auto_trial_daily_cap: +e.target.value }); toast('اتحفظ'); });
  $('#keep').addEventListener('click', async () => { try { await post('/api/auto/keep', { hours: +$('#kh').value }); toast('اتحفظ'); relayPanel(page); } catch (err) { toast(err.message, true); } });
}

async function requests(page) {
  const rows = await get('/api/requests?status=');
  put(page, html`${head('طلبات المحلات', 'طلب جاي من محل (عن طريق الوسيط) أو من الإيجنت. التجربة ممكن تتصدّر لوحدها بالسياسة. الاشتراك والتفعيل الدائم بيستنوا موافقتك وتأكيد الدفع.')}
    <div id="relay-box"></div>
    ${rows.length ? html`<div class="stack">${rows.map((r) => html`<div class="watch-item ${r.status === 'pending' ? 'warn' : ''}"><span class="ic">${icon('message')}</span>
      <div><b>${r.customer}</b> · ${r.product} · ${r.source === 'relay' ? KIND[r.kind] : EDITION[r.edition] + ' · ' + r.days + ' يوم'} ${r.device ? html`· <span class="mono">${r.device}</span>` : ''}
        <span class="badge">${r.source === 'relay' ? 'من المحل' : 'من الإيجنت'}</span>
        <div class="small muted">${r.note} · ${r.requested_at}${r.machine ? html` · جهاز <span class="mono">${r.machine.slice(0, 8)}</span>` : ''}</div>
        ${r.status === 'pending' && r.tg_decision === 'approved' ? html`<div class="small"><span class="badge ok">وافقت من تليجرام${r.kind && r.kind !== 'trial' ? ': ناقص إثبات الدفع' : ''}</span></div>` : ''}
        ${r.status === 'pending' && r.tg_decision === 'expired' ? html`<div class="small"><span class="badge warn">موافقتك على تليجرام قديمة: وافق من هنا بنفسك</span></div>` : ''}
        ${r.status !== 'pending' && r.decided_by === 'telegram' ? html`<div class="small"><span class="badge">القرار من تليجرام</span></div>` : ''}
        ${r.status === 'pending' && r.held ? html`<div class="small"><span class="badge warn">${HELD[r.held] || r.held}</span></div>` : ''}
        ${r.status === 'pending' && r.policy ? html`<div class="xs faint">${POLICY_SAYS[r.policy.verdict]}${r.policy.reason ? ' (' + (HELD[r.policy.reason] || r.policy.reason) + ')' : ''}</div>` : ''}
        ${r.status === 'pending' && r.source === 'relay' && r.kind !== 'trial' ? html`<div class="row wrap"><label class="check"><input type="checkbox" data-paid="${r.id}">الدفع وصل</label>
          <input class="input mono" data-ref="${r.id}" placeholder="مرجع الدفع" value="${r.payment_ref || ''}" maxlength="60" autocomplete="off"></div>` : ''}
        ${r.status !== 'pending' && r.source === 'relay' ? html`<div class="xs faint">${r.relayed === 1 ? 'اتبعت للمحل' : r.relayed === 2 ? 'الوسيط قفل الطلب: ابعت الكود للمحل يدوي' : 'لسه ماتبعتش للمحل: هيتحاول تاني'}</div>` : ''}</div>
      <div class="row">${r.status === 'pending' ? html`<button class="btn sm" data-no="${r.id}">ارفض</button><button class="btn sm volt" data-yes="${r.id}">وافق واعمل الكود</button>`
        : html`<span class="badge ${r.status === 'approved' ? 'ok' : 'bad'}">${r.status === 'approved' ? 'اتوافق' : 'اترفض'}</span>`}</div></div>`)}</div>`
      : html`<div class="card"><div class="empty">${icon('message')}<h3>مفيش طلبات</h3></div></div>`}`);
  relayPanel(page).catch(() => put($('#relay-box'), html``));
  $$('[data-yes],[data-no]').forEach((b) => b.addEventListener('click', async () => {
    const id = b.dataset.yes || b.dataset.no;
    const paid = $(`[data-paid="${id}"]`);
    try {
      await post('/api/request/decide', { id, approve: !!b.dataset.yes, payment_confirmed: paid ? paid.checked : undefined, payment_ref: paid ? $(`[data-ref="${id}"]`).value : undefined });
      toast('تمام'); ST = await get('/api/status'); shell(); location.hash = '#/requests';
    } catch (e) { toast(e.key === 'payment.required' ? 'علّم على «الدفع وصل» واكتب مرجع الدفع الأول.' : e.message, true); }
  }));
}

async function verify(page) {
  put(page, html`${head('افحص كود', 'عميل بيقول الكود مش شغال؟ الصقه هنا وهتعرف السبب.')}
    <div class="card form"><div class="cols"><div class="field"><label for="vp">البرنامج</label><select id="vp" class="input">${PRODUCTS.map((x) => html`<option value="${x.id}">${x.name}</option>`)}</select></div>
    <div class="field"><label for="vd">رقم جهاز العميل (اختياري)</label><input id="vd" class="input device-in" placeholder="XXXXX-XXXXX"></div></div>
    <div class="field"><label for="vc">الكود</label><textarea id="vc" class="input code-out"></textarea></div><button class="btn primary" id="go">${icon('shield')}افحص</button></div><div id="vr"></div>`);
  const REASONS = { other_device: 'الكود متعمل لجهاز تاني.', bad_signature: 'في حرف اتغير في الكود (اتنسخ غلط).', wrong_length: 'الكود ناقص أو زيادة.',
    unknown_key: 'الكود مش متوقّع بمفتاحنا.', wrong_product: 'الكود لبرنامج تاني.', bad_character: 'فيه رموز غريبة.', renew_to_unlock_paid_actions: 'مدته خلصت.', starts_later: 'لسه ميعاده مجاش.' };
  $('#go').addEventListener('click', async () => {
    const r = await post('/api/verify', { code: $('#vc').value, product: $('#vp').value, device: $('#vd').value || null });
    put($('#vr'), html`<div class="card ${r.valid && ['active', 'grace'].includes(r.state) ? 'volt-card' : ''}"><h2>${r.valid ? (STATUS[r.state] || r.state) : 'الكود مش سليم'}</h2>
      <p>${REASONS[r.reason] || r.reason || 'الكود سليم.'}</p>${r.terms?.serial ? html`<div class="small">رقم الكود <span class="mono">${r.terms.serial}</span> · ${EDITION[r.terms.edition] || ''} · ${r.terms.edition === 'perpetual' ? 'دائم' : 'لحد'} <span class="mono">${fmt(r.terms.last_day)}</span>
      · ${r.terms.device_bound ? 'مربوط بجهاز' : 'مش مربوط بجهاز'}</div>` : ''}${r.issued_here ? html`<div class="small">اتعمل هنا للعميل: <b>${r.issued_here.customer}</b> (${r.issued_here.device || '—'})</div>` : ''}</div>`);
  });
}

async function products(page) {
  PRODUCTS = await get('/api/products');
  put(page, html`${head('المنتجات', 'البرامج اللي بنطلع لها أكواد. «الكود» لازم يطابق رقم المنتج المكتوب جوه البرنامج نفسه.')}
    <div class="two"><div class="card pad-0"><table class="t"><thead><tr><th>المنتج</th><th>الرقم</th><th>أيام التجربة</th><th>الأكواد</th></tr></thead>
    <tbody>${PRODUCTS.map((x) => html`<tr><td class="name">${x.name}</td><td class="mono">${x.id}</td><td>${x.trial_days}</td><td>${x.codes}</td></tr>`)}</tbody></table></div>
    <form class="card form" id="f"><h2>منتج جديد</h2><div class="field"><label for="pid">الرقم (زي al-store)</label><input id="pid" class="input mono"></div>
    <div class="field"><label for="pn">الاسم</label><input id="pn" class="input"></div><div class="field"><label for="pd">أيام التجربة</label><input id="pd" class="input mono" value="14"></div>
    <button class="btn primary">${icon('plus')}ضيف</button></form></div>`);
  $('#f').addEventListener('submit', async (e) => { e.preventDefault(); try { await post('/api/product/save', { id: $('#pid').value, name: $('#pn').value, trial_days: +$('#pd').value }); toast('اتضاف'); products(page); } catch (err) { toast(err.message, true); } });
}

async function keys(page) {
  ST = await get('/api/status');
  put(page, html`${head('المفتاح', 'المفتاح الخاص متشفّر على الجهاز ده بس. المفتاح العام بيتحط في البرامج.')}
    <div class="two"><div class="card"><h2>المفتاح العام</h2><p class="small muted">حطه في ملف <span class="mono">licence_keys.txt</span> جوه كل برنامج قبل ما تبني النسخة.</p>
      <div class="code-out">${ST.public_key}</div><button class="btn" id="cp">${icon('clipboard')}انسخ</button></div>
    <div class="card"><h2>الأمان</h2><div class="stack tight small">
      <div class="tip">${icon('lock')}<div>البرنامج بيقفل نفسه بعد ${ST.policy.lock_minutes} دقيقة من غير استخدام.</div></div>
      <div class="tip warn">${icon('alert')}<div>خلي نسختين من فولدر <span class="mono">${ST.home}/keys</span> على فلاشتين برة الكمبيوتر. ومن غير كلمة السر النسخة مالهاش لازمة لأي حد.</div></div>
      <div class="tip bad">${icon('alert')}<div>عمر المفتاح الخاص ما يدخل GitHub أو أي سيرفر أو أي برنامج.</div></div></div></div></div>`);
  $('#cp').addEventListener('click', () => copy(ST.public_key));
}

async function agent(page) {
  ST = await get('/api/status');
  const [tokens, log] = await Promise.all([get('/api/tokens'), get('/api/audit')]);
  const pol = ST.policy;
  put(page, html`${head('الإيجنت والسجل', 'الإيجنت (Claude Code وغيره) بيتوصل بالبرنامج ده عن طريق MCP: بيقرا، ويفحص، ويطلب. وإنت اللي بتحدد يقدر يعمل إيه.')}
    <div class="two"><div class="card"><h2>المسموح للإيجنت</h2>
      <div class="toggle-row"><div><b>يطلّع أكواد تجربة لوحده</b><div class="small muted">مربوطة بجهاز، و14 يوم بالكتير. والمدفوع دايمًا بيستنى موافقتك.</div></div>
        <label class="check"><input type="checkbox" id="ag" ${pol.agent_may_issue_trials ? raw('checked') : ''}>مسموح</label></div>
      <div class="toggle-row"><div><b>أقصى عدد في اليوم</b></div><input id="lim" class="input q-in mono" value="${pol.agent_daily_limit}"></div>
      <h2>التوصيل</h2><p class="small muted">اعمل مفتاح للإيجنت (بيظهر مرة واحدة)، وحطه في إعدادات MCP:</p>
      <button class="btn primary" id="tk">${icon('key')}مفتاح جديد للإيجنت</button><div id="tko"></div>
      <p class="small muted">${tokens.filter((x) => !x.revoked).length} مفتاح شغال. ${tokens.length ? html`<button class="btn sm danger" id="rv">الغي كل المفاتيح</button>` : ''}</p></div>
    <div class="card"><h2>السجل</h2><div class="timeline">${log.map((l) => html`<div class="ev"><span class="badge ${l.actor === 'agent' ? 'info' : ''}">${l.actor === 'agent' ? 'الإيجنت' : 'أنت'}</span>
      <span class="small mono">${l.action}</span><span class="xs faint mono">${l.at}</span></div>`)}</div></div></div>`);
  $('#ag').addEventListener('change', async (e) => { await post('/api/policy', { agent_may_issue_trials: e.target.checked }); toast('اتحفظ'); });
  $('#lim').addEventListener('change', async (e) => { await post('/api/policy', { agent_daily_limit: +e.target.value }); toast('اتحفظ'); });
  $('#rv')?.addEventListener('click', async () => { await post('/api/tokens/revoke'); toast('اتلغت'); agent(page); });
  $('#tk').addEventListener('click', async () => {
    const r = await post('/api/token/new', { name: 'AI agent' });
    const cfg = JSON.stringify({ mcpServers: { 'licence-studio': { command: 'python', args: ['-m', 'licence_studio', 'mcp'], cwd: '<Apps-Factory>/apps/licence-studio',
      env: { LS_URL: r.url, LS_AGENT_TOKEN: r.token } } } }, null, 2);
    put($('#tko'), html`<div class="tip warn">${icon('alert')}<div>انسخه دلوقتي، مش هيظهر تاني.</div></div><pre class="snippet">${cfg}</pre><button class="btn" id="cpc">${icon('clipboard')}انسخ الإعدادات</button>`);
    $('#cpc').addEventListener('click', () => copy(cfg));
  });
}

boot();
