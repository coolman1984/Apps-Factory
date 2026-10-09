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
"""

STEP = '[data-afg="coach"] .afg-bar'


def _pos(page):
    return page.evaluate("""() => { const c = document.querySelector('[data-afg="coach"]');
        if (!c || c.hidden) return -1; const b = c.querySelector('.afg-bar');
        return b ? Number(b.getAttribute('aria-valuenow')) : -1; }""")


def walk(page, catalogue, handle='window.__afguide', fill='12', prepare=None, timeout=4000, only=None):
    failures = []
    targets = catalogue.get('targets', {})
    for g in catalogue.get('guides', []):
        if only and g['id'] not in only:
            continue
        if prepare:
            prepare(g['id'])
        page.evaluate(f'id => {handle}.start(id)', g['id'])
        for n, step in enumerate(g['steps'], 1):
            try:
                page.wait_for_function(f'() => {{ const b = document.querySelector(\'{STEP}\'); '
                                       f'return b && Number(b.getAttribute("aria-valuenow")) === {n}; }}', timeout=timeout)
            except Exception:
                failures.append((g['id'], n, f'the coach did not reach step {n} (it is at {_pos(page)})'))
                break
            k = step['k']
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
                page.evaluate(f'() => {handle}.stop()')
                break
    return failures
