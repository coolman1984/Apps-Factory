/* af-auth: generic sign-in, first setup, self sign-up, forgot-password help, reset-with-code (product-agnostic). */
(function (root, factory) {
  'use strict';
  if (typeof module === 'object' && module.exports) {
    module.exports = factory;
  } else {
    root.afAuth = factory(root);
  }
})(typeof globalThis !== 'undefined' ? globalThis : this, function (root) {
  'use strict';

  var DEFAULT_PATHS = {
    status: '/api/auth/status',
    setup: '/api/auth/setup',
    login: '/api/auth/login',
    register: '/api/auth/register',
    reset: '/api/auth/reset',
    password: '/api/auth/password'
  };

  function create(host, opts) {
    opts = opts || {};
    var paths = Object.assign({}, DEFAULT_PATHS, opts.paths || {});
    var mode = 'login';

    function t(key, vars) {
      return host.t(key, vars);
    }
    function esc(s) {
      return host.esc(s);
    }
    function field(id, label, type, extra) {
      return '<div class="field"><label for="' + id + '">' + esc(label) + '</label>' +
        '<input class="input" id="' + id + '" name="' + id + '" type="' + type + '" ' + (extra || '') + '></div>';
    }
    function fail(form, msg) {
      var e = form.querySelector('.err');
      e.hidden = false;
      e.textContent = msg;
    }
    function links() {
      return '<div class="row wrap" style="gap:.8rem;margin-top:.6rem;font-size:.9rem">' +
        '<button type="button" class="btn ghost sm" data-auth-mode="signup">' + esc(t('auth.link.signup')) + '</button>' +
        '<button type="button" class="btn ghost sm" data-auth-mode="forgot">' + esc(t('auth.link.forgot')) + '</button>' +
        '<button type="button" class="btn ghost sm" data-auth-mode="reset">' + esc(t('auth.link.reset')) + '</button></div>';
    }
    function loginForm() {
      return '<form id="auth-form"><div><h2>' + esc(t('auth.login.title')) + '</h2><p class="muted" style="margin-top:.4rem">' +
        esc(t('auth.login.sub')) + '</p></div>' +
        field('username', t('auth.username'), 'text', 'autofocus required autocapitalize="off" spellcheck="false" dir="ltr" autocomplete="username"') +
        field('password', t('auth.password'), 'password', 'required dir="ltr" autocomplete="current-password"') +
        '<div class="tip err" hidden role="alert"></div>' +
        '<button class="btn primary" type="submit">' + esc(t('auth.login.btn')) + '</button>' + links() + '</form>';
    }
    function signupForm() {
      return '<form id="auth-form"><div><h2>' + esc(t('auth.signup.title')) + '</h2><p class="muted" style="margin-top:.4rem">' +
        esc(t('auth.signup.sub')) + '</p></div>' +
        field('full_name', t('auth.fullname'), 'text', 'autofocus required') +
        field('username', t('auth.username'), 'text', 'required autocapitalize="off" spellcheck="false" dir="ltr"') +
        field('password', t('auth.password'), 'password', 'required dir="ltr"') +
        field('password2', t('auth.password2'), 'password', 'required dir="ltr"') +
        '<p class="faint" style="font-size:.85rem">' + esc(t('auth.pw.hint')) + '</p>' +
        '<div class="tip err" hidden role="alert"></div><div class="tip ok" hidden role="status"></div>' +
        '<button class="btn primary" type="submit">' + esc(t('auth.signup.btn')) + '</button>' +
        '<button type="button" class="btn ghost" data-auth-mode="login" style="margin-inline-start:.5rem">' +
        esc(t('auth.backLogin')) + '</button></form>';
    }
    function forgotForm() {
      return '<form id="auth-form"><div><h2>' + esc(t('auth.forgot.title')) + '</h2><p class="muted" style="margin-top:.4rem">' +
        esc(t('auth.forgot.sub')) + '</p></div>' +
        field('username', t('auth.username'), 'text', 'autofocus required autocapitalize="off" spellcheck="false" dir="ltr"') +
        '<div class="tip err" hidden role="alert"></div>' +
        '<button class="btn primary" type="submit">' + esc(t('common.close')) + '</button>' +
        '<button type="button" class="btn ghost" data-auth-mode="login" style="margin-inline-start:.5rem">' +
        esc(t('auth.backLogin')) + '</button></form>';
    }
    function resetForm() {
      return '<form id="auth-form"><div><h2>' + esc(t('auth.reset.title')) + '</h2><p class="muted" style="margin-top:.4rem">' +
        esc(t('auth.reset.sub')) + '</p></div>' +
        field('username', t('auth.username'), 'text', 'autofocus required autocapitalize="off" spellcheck="false" dir="ltr"') +
        field('code', t('auth.reset.code'), 'text', 'required dir="ltr" autocapitalize="characters" spellcheck="false"') +
        field('password', t('auth.password'), 'password', 'required dir="ltr"') +
        field('password2', t('auth.password2'), 'password', 'required dir="ltr"') +
        '<p class="faint" style="font-size:.85rem">' + esc(t('auth.pw.hint')) + '</p>' +
        '<div class="tip err" hidden role="alert"></div>' +
        '<button class="btn primary" type="submit">' + esc(t('auth.reset.btn')) + '</button>' +
        '<button type="button" class="btn ghost" data-auth-mode="login" style="margin-inline-start:.5rem">' +
        esc(t('auth.backLogin')) + '</button></form>';
    }

    function show(status) {
      var mount = host.$('#' + (opts.rootId || 'root'));
      var setup = !status.hasUsers;
      var body;
      if (setup && !status.local) {
        body = '<div class="empty"><h3>' + esc(t('auth.setup.title')) + '</h3><p>' + esc(t('auth.remote')) + '</p></div>';
      } else if (setup) {
        body = '<form id="auth-form" autocomplete="off"><div><h2>' + esc(t('auth.setup.title')) + '</h2><p class="muted">' +
          esc(t('auth.setup.sub')) + '</p></div>' +
          field('full_name', t('auth.fullname'), 'text', 'autofocus required') +
          field('username', t('auth.username'), 'text', 'required autocapitalize="off" spellcheck="false" dir="ltr"') +
          field('password', t('auth.password'), 'password', 'required dir="ltr"') +
          '<p class="faint" style="font-size:.85rem">' + esc(t('auth.pw.hint')) + '</p>' +
          '<div class="tip err" hidden role="alert"></div>' +
          '<button class="btn primary" type="submit">' + esc(t('auth.setup.btn')) + '</button></form>';
      } else {
        body = mode === 'signup' ? signupForm() : mode === 'forgot' ? forgotForm() : mode === 'reset' ? resetForm() : loginForm();
      }
      mount.innerHTML = (opts.wrap || function (inner) { return '<div class="auth"><div class="panel">' + inner + '</div></div>'; })(body);
      mount.addEventListener('click', function (e) {
        var b = e.target.closest('[data-auth-mode]');
        if (b) {
          mode = b.dataset.authMode;
          show(status);
        }
      });
      var form = host.$('#auth-form', mount);
      if (!form) return;
      form.addEventListener('submit', function (e) {
        e.preventDefault();
        var d = {};
        new FormData(form).forEach(function (v, k) { d[k] = String(v).trim(); });
        var btn = form.querySelector('button[type=submit]');
        if (btn) btn.disabled = true;
        if (setup) {
          host.post(paths.setup, d).then(function () { host.emit('logged-in'); }, function (err) {
            if (btn) btn.disabled = false;
            fail(form, err.message || t('common.error'));
          });
          return;
        }
        if (mode === 'signup') {
          if (d.password !== d.password2) {
            if (btn) btn.disabled = false;
            fail(form, t('auth.pw.mismatch'));
            return;
          }
          host.post(paths.register, d).then(function (r) {
            var ok = form.querySelector('.ok');
            if (ok) {
              ok.hidden = false;
              ok.textContent = t('auth.signup.done', { code: r.request_code || '' });
            }
            if (btn) btn.disabled = false;
          }, function (err) {
            if (btn) btn.disabled = false;
            fail(form, err.message || t('common.error'));
          });
          return;
        }
        if (mode === 'forgot') {
          if (btn) btn.disabled = false;
          host.dialog({
            title: t('auth.forgot.title'),
            body: '<p>' + esc(t('auth.forgot.help')) + '</p>',
            footer: '<button class="btn primary" data-close>' + esc(t('common.close')) + '</button>'
          });
          return;
        }
        if (mode === 'reset') {
          if (d.password !== d.password2) {
            if (btn) btn.disabled = false;
            fail(form, t('auth.pw.mismatch'));
            return;
          }
          host.post(paths.reset, { username: d.username, code: d.code, password: d.password }).then(function () {
            mode = 'login';
            if (host.toast) host.toast(t('auth.reset.done'));
            show(status);
          }, function (err) {
            if (btn) btn.disabled = false;
            fail(form, err.message || t('common.error'));
          });
          return;
        }
        host.post(paths.login, d).then(function () { host.emit('logged-in'); }, function (err) {
          if (btn) btn.disabled = false;
          fail(form, err.message || t('auth.failed'));
        });
      });
    }

    return { show: show, setMode: function (m) { mode = m; } };
  }

  return { create: create, DEFAULT_PATHS: DEFAULT_PATHS };
});
