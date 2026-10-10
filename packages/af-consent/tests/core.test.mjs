// node --test packages/af-consent/tests/core.test.mjs
// The settings block must never print the word "null": the real DOM's replaceChildren() turns every non-Node argument into text, so
// a `null` child (an absent button) becomes "null". This stub follows that rule exactly; the old code failed here with «nullnull».
import test from 'node:test';
import assert from 'node:assert/strict';
import {createRequire} from 'node:module';
const AFConsent = createRequire(import.meta.url)('../af-consent.js');

function fakeDoc() {
  const node = (tag) => ({
    nodeType: 1, tag, attrs: {}, kids: [],
    setAttribute(k, v) { this.attrs[k] = String(v); },
    addEventListener() {},
    append(...xs) { for (const x of xs) this.kids.push(x && x.nodeType ? x : {nodeType: 3, text: String(x)}); },
    set textContent(v) { this.kids = [{nodeType: 3, text: String(v)}]; },
    // the DOM rule: anything that is not a Node is converted to a string and becomes a text node
    replaceChildren(...xs) { this.kids = xs.map((x) => (x && x.nodeType ? x : {nodeType: 3, text: String(x)})); },
    get innerText() { return this.kids.map((k) => (k.nodeType === 3 ? k.text : k.innerText)).join(' '); },
  });
  return {createElement: node, createTextNode: (t) => ({nodeType: 3, text: String(t)})};
}

function render(opts) {
  const doc = fakeDoc();
  const box = doc.createElement('div');
  box.ownerDocument = doc;
  AFConsent.settings(box, opts);
  return box;
}

test('the settings block never prints "null", whatever is absent', () => {
  const cases = [
    {status: {}},                                                                         // nobody agreed, nobody to show
    {status: {install: {decision: 'agree'}, tracking: false}},                            // installation agreed, person did not
    {status: {install: {decision: 'agree'}, tracking: true, person: {label: 'Mona', at: '2026-10-10'}}, showSent: () => {}},
    {status: {install: {decision: 'decline'}}, showSent: () => {}},
  ];
  for (const lang of ['ar', 'en']) {
    for (const c of cases) {
      const text = render({...c, prompt: {lang}, decide() {}}).innerText;
      assert.doesNotMatch(text, /(?<![A-Za-z])(?:null|undefined|false)+(?![A-Za-z])|\[object/, `${lang} ${JSON.stringify(c.status)} -> ${text}`);
    }
  }
});

test('the buttons that belong are there, and only those', () => {
  const buttons = (box) => box.kids.filter((k) => k.tag === 'button').map((k) => k.attrs['data-afc']);
  assert.deepEqual(buttons(render({status: {}, prompt: {lang: 'en'}, decide() {}})), []);
  assert.deepEqual(buttons(render({status: {install: {decision: 'agree'}}, prompt: {lang: 'en'}, decide() {}})), ['agree-now']);
  assert.deepEqual(buttons(render({status: {install: {decision: 'agree'}, tracking: true}, prompt: {lang: 'en'}, decide() {}, showSent() {}})), ['withdraw', 'sent']);
});

test('version', () => assert.equal(AFConsent.version, '0.1.1'));
