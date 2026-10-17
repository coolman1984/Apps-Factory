import test from 'node:test';
import assert from 'node:assert/strict';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const here = dirname(fileURLToPath(import.meta.url));
const require = createRequire(import.meta.url);
const afAuth = require(join(here, '..', 'af-auth.js'))(globalThis);

function parseAttrs(fragment) {
  const attrs = {};
  const re = /(\w[\w-]*)(?:="([^"]*)")?/g;
  let m;
  while ((m = re.exec(fragment)) !== null) {
    attrs[m[1]] = m[2] ?? '';
  }
  return attrs;
}

function makeMount() {
  let html = '';
  const clickHandlers = [];
  const mount = {
    get innerHTML() {
      return html;
    },
    set innerHTML(v) {
      html = v;
    },
    addEventListener(type, fn) {
      if (type === 'click') clickHandlers.push(fn);
    },
    querySelector(sel) {
      const formH2 = sel.match(/^#auth-form\s+h2$/);
      if (formH2) {
        const h = html.match(/<form[^>]*id="auth-form"[^>]*>[\s\S]*?<h2[^>]*>([^<]*)<\/h2>/);
        return h ? { textContent: h[1] } : null;
      }
      if (sel === '#auth-form') {
        const m = html.match(/<form[^>]*id="auth-form"[^>]*>/);
        if (!m) return null;
        const form = {
          querySelector(q) {
            if (q === 'h2') {
              const h = html.match(/<form[^>]*id="auth-form"[^>]*>[\s\S]*?<h2[^>]*>([^<]*)<\/h2>/);
              return h ? { textContent: h[1] } : null;
            }
            return null;
          },
          addEventListener() {},
        };
        return form;
      }
      const mode = sel.match(/\[data-auth-mode="([^"]+)"\]/);
      if (mode) {
        const re = new RegExp(
          `<button[^>]*data-auth-mode="${mode[1]}"[^>]*>([^<]*)</button>`,
        );
        const m = html.match(re);
        if (!m) return null;
        const attrs = parseAttrs(m[0]);
        return {
          dataset: { authMode: attrs['data-auth-mode'] },
          textContent: m[1],
          click() {
            const target = {
              closest(s) {
                if (s === '[data-auth-mode]') return this;
                return null;
              },
              dataset: { authMode: attrs['data-auth-mode'] },
            };
            const e = { target };
            clickHandlers.forEach((h) => h(e));
          },
        };
      }
      return null;
    },
  };
  return mount;
}

function mockHost(mount) {
  return {
    $(sel, root) {
      const scope = root || mount;
      if (sel === '#root') return mount;
      return scope.querySelector(sel);
    },
    t(key) {
      return key;
    },
    esc(s) {
      return String(s);
    },
    post() {
      return Promise.resolve({});
    },
    emit() {},
  };
}

test('DEFAULT_PATHS wires standard auth API routes', () => {
  assert.equal(afAuth.DEFAULT_PATHS.login, '/api/auth/login');
  assert.equal(afAuth.DEFAULT_PATHS.register, '/api/auth/register');
  assert.equal(afAuth.DEFAULT_PATHS.setup, '/api/auth/setup');
});

test('create show renders login with signup mode control', () => {
  const mount = makeMount();
  const api = afAuth.create(mockHost(mount), { rootId: 'root' });
  api.show({ hasUsers: true, local: true });
  const signup = mount.querySelector('[data-auth-mode="signup"]');
  assert.ok(signup);
  assert.equal(signup.textContent, 'auth.link.signup');
});

test('mode switch binds one click handler on mount', () => {
  const mount = makeMount();
  const api = afAuth.create(mockHost(mount), { rootId: 'root' });
  const status = { hasUsers: true, local: true };
  for (let i = 0; i < 5; i++) {
    api.show(status);
  }
  const signup = mount.querySelector('[data-auth-mode="signup"]');
  assert.ok(signup);
  signup.click();
  assert.equal(mount.querySelector('#auth-form h2').textContent, 'auth.signup.title');
});
