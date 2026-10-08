"""Token gate: fail a build when a product's design tokens break the factory standard (DESIGN.md v2).

Dependency-free. Reads one tokens.css, finds the light block (`:root`) and every dark block (a selector naming dark or
night, merged over light), and checks WCAG 2.2 AA contrast (4.5:1) for the text/background pairs the product declares,
plus minimum sizes (body text, icon, touch target). Born in Al-Store/Mizan, where it found real failures.

    python design-factory/qa/token_gate.py design-factory/core/tokens.css                      # factory preset
    python design-factory/qa/token_gate.py path/tokens.css --pairs ink/surface,ink-3/canvas --min fs=16 --min tap=44
"""
import argparse
import re
import sys

AF_PAIRS = ['af-text/af-surface', 'af-text-secondary/af-surface', 'af-text-tertiary/af-surface', 'af-text-tertiary/af-bg',
            'af-success/af-success-soft', 'af-warning/af-warning-soft', 'af-danger/af-danger-soft', 'af-accent/af-surface']


def luminance(hex_):
    c = [int(hex_[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    c = [x / 12.92 if x <= .03928 else ((x + .055) / 1.055) ** 2.4 for x in c]
    return .2126 * c[0] + .7152 * c[1] + .0722 * c[2]


def contrast(a, b):
    a, b = luminance(a), luminance(b)
    return (max(a, b) + .05) / (min(a, b) + .05)


def blocks(css):
    """Yield (context, {prop: value}) for every rule that declares custom properties. Context is the chain of
    at-rule preludes and the selector, so `@media (prefers-color-scheme: dark) { :root {…} }` stays separate from `:root`."""
    css = re.sub(r'/\*.*?\*/', '', css, flags=re.S)
    stack, start = [], 0
    for i, ch in enumerate(css):
        if ch == '{':
            stack.append(' '.join(css[start:i].split()))
            start = i + 1
        elif ch == '}':
            body = css[start:i]
            props = dict((k, v.strip()) for k, v in re.findall(r'--([\w-]+)\s*:\s*([^;]+)', body + ';'))
            if props and stack:
                yield ' '.join(stack), props
            if stack:
                stack.pop()
            start = i + 1
        elif ch == ';' and not stack:
            start = i + 1  # a top-level statement such as @import


def themes(css):
    """{'light': {...}, '<context>': {...}}: the plain `:root` block is light; every other block that sets a colour is a
    theme (dark, night, contrast, a system-dark media query…) checked merged over light."""
    light, others = {}, []
    for context, props in blocks(css):
        if context == ':root':
            light.update(props)
        elif any(re.fullmatch(r'#[0-9a-fA-F]{6}', v) for v in props.values()):
            others.append((context, props))
    result = {'light': light}
    for context, props in others:
        result[context] = {**result.get(context, light), **props}
    return result


def px(value):
    m = re.fullmatch(r'\s*([\d.]+)px\s*', value or '')
    return float(m.group(1)) if m else None


def check(css, pairs, minimums):
    problems = []
    for theme, props in themes(css).items():
        for pair in pairs:
            fg, bg = pair.split('/')
            a, b = props.get(fg, '').strip(), props.get(bg, '').strip()
            if not (re.fullmatch(r'#[0-9a-fA-F]{6}', a) and re.fullmatch(r'#[0-9a-fA-F]{6}', b)):
                problems.append(f'{theme}: --{fg} / --{bg} missing or not a #rrggbb colour')
                continue
            ratio = contrast(a, b)
            if ratio < 4.5:
                problems.append(f'{theme}: --{fg} {a} on --{bg} {b} is {ratio:.2f}:1 (needs 4.5)')
    light = themes(css)['light']
    for name, least in minimums.items():
        value = px(light.get(name))
        if value is None or value < least:
            problems.append(f'--{name} is {light.get(name, "missing")}, needs at least {least:g}px')
    return problems


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument('tokens')
    ap.add_argument('--pairs', help='comma-separated fg/bg token names (without --); default: factory af- preset')
    ap.add_argument('--min', action='append', default=[], help='name=px, e.g. tap=44 (repeatable)')
    args = ap.parse_args(argv)
    with open(args.tokens, encoding='utf-8') as f:
        css = f.read()
    pairs = args.pairs.split(',') if args.pairs else AF_PAIRS
    minimums = {k: float(v) for k, v in (m.split('=') for m in args.min)}
    problems = check(css, pairs, minimums)
    for p in problems:
        print('FAIL', p)
    print('token gate:', 'PASS' if not problems else f'{len(problems)} problem(s)')
    return 1 if problems else 0


if __name__ == '__main__':
    sys.exit(main())
