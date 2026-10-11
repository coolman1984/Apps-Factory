"""Walk every guide of a running product in a real browser (HELP-12). Uses Playwright's sync API.

    from walk_guides import walk
    failures = walk(page, catalogue)          # page: a signed-in Playwright page with af-guide loaded
    assert failures == [], failures

The product exposes its controller as window.__afguide (one line after AFGuide.init). For each guide the walker
starts the coach, then does what the step asks a person to do - go: presses "Take me there"; click/check: clicks the
target; type: fills it; choose: picks the first real option; tip/warn: presses Next; done: presses Finish - and waits
until the coach moves on by itself (auto-advance, HELP-08) or presses Next for steps without "until".
A failure is (guide id, step number, reason): a target that is missing on its page, or a step that never advances.
Products give `prepare(guide_id)` to put the data in the right state first (for example "a shift is open").

Strict-CSP safe (a product's own policy, e.g. Store's `script-src 'self'` without 'unsafe-eval'): the walker never
uses wait_for_function (Playwright evaluates its string with eval while polling, which such a policy refuses) and never
builds JavaScript from strings. It runs three fixed functions through page.evaluate, with the values passed as
arguments, and polls from Python.
"""
import re
import time

# Fixed page functions (no string building, no eval in the page).
_POS = """() => { const c = document.querySelector('[data-afg="coach"]');
    if (!c || c.hidden) return -1; const b = c.querySelector('.afg-bar');
    return b ? Number(b.getAttribute('aria-valuenow')) : -1; }"""
_CALL = """([path, method, args]) => {
    const ctl = String(path).replace(/^window\./, '').split('.').reduce((o, k) => (o == null ? o : o[k]), window);
    if (!ctl || typeof ctl[method] !== 'function') throw new Error('no guide controller at ' + path);
    return ctl[method](...args); }"""


# A word that means the page printed a missing value (`replaceChildren(null)` once put «null» into every step of the coach).
_STRAY = re.compile(r'(?<![A-Za-z])(?:null|undefined|NaN)+(?![A-Za-z])|\[object ')  # (+: «nullnull» too: a \b boundary misses a run)
_COACH_TEXT = """() => { const c = document.querySelector('[data-afg="coach"]'); return c && !c.hidden ? c.innerText : ''; }"""


def _pos(page):
    return page.evaluate(_POS)


def _call(page, handle, method, *args):
    return page.evaluate(_CALL, [handle, method, list(args)])


def _until_step(page, n, timeout_ms):
    """Poll (from Python) until the coach shows step n."""
    end = time.monotonic() + timeout_ms / 1000
    while True:
        if _pos(page) == n:
            return True
        if time.monotonic() >= end:
            return False
        page.wait_for_timeout(50)


def walk(page, catalogue, handle='window.__afguide', fill='12', prepare=None, timeout=4000, only=None):
    failures = []
    targets = catalogue.get('targets', {})
    for g in catalogue.get('guides', []):
        if only and g['id'] not in only:
            continue
        if prepare:
            prepare(g['id'])
        _call(page, handle, 'start', g['id'])
        for n, step in enumerate(g['steps'], 1):
            if not _until_step(page, n, timeout):
                failures.append((g['id'], n, f'the coach did not reach step {n} (it is at {_pos(page)})'))
                break
            k = step['k']
            stray = _STRAY.search(page.evaluate(_COACH_TEXT) or '')
            if stray:
                failures.append((g['id'], n, f'the coach prints «{stray.group(0)}»'))
            try:
                if k == 'done':
                    page.click('[data-afg="finish"]', timeout=timeout)
                    break
                if k == 'go':
                    if page.locator('[data-afg="there"]').count():
                        page.click('[data-afg="there"]', timeout=timeout)
                elif k in ('tip', 'warn'):
                    page.click('[data-afg="next"]', timeout=timeout)
                    continue
                else:
                    sel = targets[step['target']]['sel']
                    if page.locator('[data-afg="there"]').count():
                        page.click('[data-afg="there"]', timeout=timeout)
                    loc = page.locator(sel).first
                    loc.wait_for(state='visible', timeout=timeout)
                    if k == 'type':
                        loc.fill(fill)
                    elif k == 'choose':
                        loc.select_option(index=1)
                    else:
                        loc.click()
                if not step.get('until') and k != 'go':
                    page.click('[data-afg="next"]', timeout=timeout)
            except Exception as e:  # noqa: BLE001 - report every failure, keep walking the other guides
                failures.append((g['id'], n, f'{k} step failed: {str(e).splitlines()[0]}'))
                _call(page, handle, 'stop')
                break
    return failures
