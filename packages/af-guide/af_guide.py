"""af-guide: the factory's gate for built-in help - guides, the learning path per role, problems, and the simple Arabic.

A product describes its help as a *catalogue* (plain JSON-able dict, see README.md). This module checks it against the factory
standard (docs/HELP_AND_GUIDANCE_STANDARD.md):

  * every guide has a title, a "what you get", every step and a "how you know it worked" in every language;
  * every role has a learning path (المنهج): ordered lessons, each one a guide, and where possible a fact the program can
    check by itself, so the person sees where they stand without anybody telling them;
  * the administrator's path starts by setting the program up; every page is reached by at least one guide;
  * every problem has a question and an answer in every language and a guide that fixes it;
  * the Arabic is *simple formal Arabic* (العربية المبسطة): neither street Egyptian nor stiff office Arabic - `register()`.

    python af_guide.py check catalogue.json      # exit 1 on any error

Standard library only, one file, copied into each product (scripts/vendor_guide.py).
"""
import json
import re
import sys

__version__ = '0.1.0'

ID_RE = re.compile(r'^[a-z][a-zA-Z0-9_-]*$')

# Simple formal Arabic: words a reader sees as street Egyptian (too loose for a product's help) ...
COLLOQUIAL = ['ده', 'دي', 'دى', 'دول', 'مش', 'عشان', 'علشان', 'إزاي', 'ازاي', 'إيه', 'ايه', 'دلوقتي', 'دلوقت', 'كده', 'كدة',
              'بتاع', 'بتاعة', 'بتاعك', 'بتاعته', 'عايز', 'عاوز', 'عايزة', 'هتلاقي', 'هتلاقى', 'هيظهر', 'هتظهر', 'هيفتح', 'هتفتح',
              'بيظهر', 'بتظهر', 'بيفتح', 'بتفتح', 'خلّي', 'خلي', 'برضه', 'برضو', 'لسه', 'لسّه', 'زرار', 'بقى', 'اتأكد',
              'اتحفظ', 'دوس', 'دوّس', 'اللي', 'إللي', 'فين', 'ليه', 'امتى', 'إمتى', 'حاجة', 'حاجات', 'كمان', 'تاني', 'تانية', 'بس']
# not listed on purpose: «يعني» (also good Arabic: «يعني أن»), «وعليه» (also «وعليه مبالغ»)
# ... and words that sound like a government letter (too stiff to be understood at a glance)
STIFF = ['يُرجى', 'يرجى', 'نظرًا', 'نظراً', 'نظرا', 'يتعذّر', 'يتعذر', 'المذكور', 'المذكورة', 'آنفًا', 'آنفا',
         'حيث إن', 'حيث أن', 'بموجب', 'إذ إن', 'لاسيما', 'لا سيما', 'تجدر الإشارة', 'يُعدّ', 'فيما يخص']
_AR_WORD = re.compile(r'[ء-ي٠-٩ـًٌٍَُِّْ]+')


def register(text):
    """The words in an Arabic help text that break the simple formal register: [(word, 'colloquial' | 'stiff')]."""
    text = str(text or '')
    found = []
    words = {w.replace('ـ', '') for w in _AR_WORD.findall(text)}
    bare = {re.sub(r'[ًٌٍَُِّْ]', '', w) for w in words}
    for w in COLLOQUIAL:
        if w in words or w in bare:
            found.append((w, 'colloquial'))
    for w in STIFF:
        if (' ' in w and w in text) or w in words or w in bare:
            found.append((w, 'stiff'))
    return found


class Finding:
    def __init__(self, level, code, where, message):
        self.level, self.code, self.where, self.message = level, code, where, message

    def __repr__(self):
        return f'{self.level.upper()} {self.code} [{self.where}] {self.message}'


def check(cat):
    """Every rule broken by the help catalogue, as Findings (level 'error' or 'warning')."""
    out = []

    def bad(code, where, msg, level='error'):
        out.append(Finding(level, code, where, msg))

    langs = cat.get('languages') or ['ar', 'en']
    guides = {g.get('id'): g for g in cat.get('guides', [])}
    facts = set(cat.get('facts', []))

    def texts_ok(where, texts, need):
        for lang in langs:
            got = (texts or {}).get(lang) or []
            if len(got) < need or any(not str(t or '').strip() for t in got[:need]):
                bad('words-missing', f'{where}:{lang}', f'Needs {need} non-empty texts in {lang}, found {len(got)}.')
        for t in (texts or {}).get('ar') or []:
            for word, kind in register(t):
                bad('register', where, f'«{word}» is {kind}; help is written in simple formal Arabic (العربية المبسطة).')

    if not guides:
        bad('no-guides', 'guides', 'A product ships guides: one per daily job.')
    for gid, g in guides.items():
        if not isinstance(gid, str) or not ID_RE.match(gid):
            bad('guide-id', str(gid), 'Guide ids are short words, e.g. "openShift".')
        n = int(g.get('steps') or 0)
        if n < 2:
            bad('guide-short', str(gid), 'A guide has at least two steps.')
        texts_ok(f'guide {gid}', g.get('texts'), n + 3)  # title, what you get, the steps, how you know it worked

    pages = cat.get('pages') or []
    reached = {p for g in guides.values() for p in g.get('pages', [])}
    for p in pages:
        if p not in reached:
            bad('page-without-guide', p, 'Every page is reached by at least one guide.')

    paths = cat.get('paths') or []
    if not paths:
        bad('no-paths', 'paths', 'Every role has a learning path (المنهج): ordered lessons with progress.')
    if paths and not any(p.get('admin') for p in paths):
        bad('no-admin-path', 'paths', 'The administrator has a path that starts by setting the program up.')
    seen = set()
    for p in paths:
        pid = p.get('id')
        if pid in seen:
            bad('path-duplicate', str(pid), 'Two paths share an id.')
        seen.add(pid)
        texts_ok(f'path {pid}', p.get('texts'), 2)  # name, who it is for
        lessons = p.get('lessons') or []
        if len(lessons) < 3:
            bad('path-short', str(pid), 'A path has at least three lessons.')
        for i, lesson in enumerate(lessons):
            gid, fact = lesson.get('guide'), lesson.get('fact')
            if gid not in guides:
                bad('lesson-unknown-guide', f'{pid}#{i + 1}', f'"{gid}" is not a guide.')
            if fact and fact not in facts:
                bad('lesson-unknown-fact', f'{pid}#{i + 1}', f'"{fact}" is not a fact the program reports.')
        checked = sum(1 for x in lessons if x.get('fact'))
        if lessons and checked * 2 < len(lessons):
            bad('path-unchecked', str(pid), 'At least half of a path\'s lessons are checked by the program itself (a fact), '
                'so the person sees where they stand.', 'warning')
        if p.get('admin') and lessons and lessons[0].get('guide') not in (cat.get('setup_guides') or [lessons[0].get('guide')]):
            bad('admin-path-order', str(pid), 'The administrator\'s path starts with setting the program up.')
    for role in cat.get('roles') or []:
        if not any(role in (p.get('roles') or []) for p in paths):
            bad('role-without-path', role, 'Every ready-made role/profile has a learning path.')

    for s in cat.get('situations') or []:
        sid = s.get('id')
        texts_ok(f'problem {sid}', s.get('texts'), 2)  # question, answer
        if s.get('guide') and s['guide'] not in guides:
            bad('problem-unknown-guide', str(sid), f'"{s["guide"]}" is not a guide.')
        if not s.get('guide'):
            bad('problem-without-guide', str(sid), 'A problem offers "Guide me" through the guide that fixes it.', 'warning')
    for key, text in (cat.get('other_ar') or {}).items():
        for word, kind in register(text):
            bad('register', key, f'«{word}» is {kind}; help is written in simple formal Arabic (العربية المبسطة).')
    return out


def errors(cat):
    return [f for f in check(cat) if f.level == 'error']


def progress(lessons, facts, done_guides=()):
    """Where a person stands on their path: (index of the first lesson not done, [done flags]). A lesson is done when its fact
    is true (the program saw it happen) or, for a lesson without a fact, when the person finished its guide."""
    flags = [bool(facts.get(x['fact'])) if x.get('fact') else x.get('guide') in set(done_guides) for x in lessons]
    return next((i for i, f in enumerate(flags) if not f), len(flags)), flags


def main(argv):
    if len(argv) != 3 or argv[1] != 'check':
        print(__doc__)
        return 2
    with open(argv[2], encoding='utf-8') as f:
        cat = json.load(f)
    found = check(cat)
    for x in found:
        print(x)
    n = sum(f.level == 'error' for f in found)
    print(f'{cat.get("product", "catalogue")}: {len(cat.get("guides", []))} guides, {len(cat.get("paths", []))} paths, '
          f'{len(cat.get("situations", []))} problems, {n} error(s), {len(found) - n} warning(s)')
    return 1 if n else 0


if __name__ == '__main__':
    sys.exit(main(sys.argv))
