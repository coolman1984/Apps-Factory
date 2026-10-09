"""af-guide: every rule fires on a broken catalogue, the example passes, lint catches the register, progress is kept
per person, the JS core agrees, copies are fresh."""
import copy
import hashlib
import json
import os
import shutil
import sqlite3
import subprocess
import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_guide as G  # noqa: E402

EX = PKG / 'examples' / 'shop'
CAT, TEXTS = G.load_dir(EX)
UI = {lang: json.loads((EX / f'ui-{lang}.json').read_text(encoding='utf-8')) for lang in ('ar', 'en')}
ACCESS = json.loads((EX / 'access.json').read_text(encoding='utf-8'))
ERRORS = json.loads((EX / 'errors.json').read_text(encoding='utf-8'))


def run(cat=None, texts=None, **kw):
    kw.setdefault('ui', UI)
    kw.setdefault('access', ACCESS)
    kw.setdefault('error_codes', ERRORS)
    return G.check(cat if cat is not None else CAT, texts if texts is not None else TEXTS, **kw)


def codes(found):
    return {f.code for f in found if f.level == 'error'}


class Catalogue(unittest.TestCase):
    def test_example_is_clean_even_for_release(self):
        self.assertEqual(run(release=True), [])
        self.assertEqual(G.errors(CAT, TEXTS), [])

    def test_each_rule_fires(self):
        def g(c, gid):
            return next(x for x in c['guides'] if x['id'] == gid)
        cases = [
            ('format', lambda c, t: c.update(format=2)),
            ('languages', lambda c, t: c.update(defaultLang='fr')),
            ('guide-id', lambda c, t: g(c, 'add-product').update(id='Add Product')),
            ('duplicate', lambda c, t: c['guides'].append(copy.deepcopy(g(c, 'add-product')))),
            ('unknown-kind', lambda c, t: g(c, 'add-product')['steps'][1].update(k='press')),
            ('unknown-target', lambda c, t: g(c, 'add-product')['steps'][1].update(target='stock.nope')),
            ('target-page', lambda c, t: g(c, 'add-product')['steps'][1].update(target='shift.open')),
            ('unknown-page', lambda c, t: g(c, 'add-product')['steps'][0].update(page='nowhere')),
            ('unknown-perm', lambda c, t: g(c, 'add-product').update(perm='stock.nope')),
            ('unknown-state', lambda c, t: g(c, 'add-product').update(done={'state': 'nope'})),
            ('unknown-guide', lambda c, t: g(c, 'first-sale')['requires'].append('nope')),
            ('minutes', lambda c, t: g(c, 'add-product').update(minutes=40)),
            ('steps', lambda c, t: g(c, 'add-product')['steps'].pop()),
            ('step-shape', lambda c, t: g(c, 'add-product')['steps'][0].pop('page')),
            ('until', lambda c, t: g(c, 'add-product')['steps'][1].update(until={'when': 'x'})),
            ('role-without-path', lambda c, t: c['roles'][0].update(path=[])),
            ('requires-cycle', lambda c, t: g(c, 'open-shift')['requires'].append('first-sale')),
            ('path-order', lambda c, t: c['roles'][0].update(path=['first-sale', 'open-shift', 'close-shift'])),
            ('role-perm', lambda c, t: c['roles'][0]['path'].insert(0, 'add-person')),
            ('unknown-profile', lambda c, t: c['roles'][0].update(profiles=['ghost'])),
            ('coverage-checklist', lambda c, t: c['checklist'].append('print-labels')),
            ('problem-shape', lambda c, t: c['problems'][0].update(errors='sale.no_shift')),
            ('problem-without-link', lambda c, t: (c['problems'][3].pop('page'), c['problems'][3].pop('guide', None))),
            ('error-unexplained', lambda c, t: c['problems'][0].update(errors=[])),
            ('page-unguided', lambda c, t: c.update(unguided=[])),
            ('text-missing', lambda c, t: t['en'].pop('guide.open-shift.3')),
            ('ui-key-missing', lambda c, t: t['ar'].update({'guide.open-shift.2': 'اضغط [[shift.opne]].'})),
            ('target-shape', lambda c, t: c['targets'].update({'x.y': {'page': 'home'}})),
        ]
        for code, breaker in cases:
            with self.subTest(code=code):
                c, t = copy.deepcopy(CAT), copy.deepcopy(TEXTS)
                breaker(c, t)
                self.assertIn(code, codes(run(c, t)))

    def test_without_access_catalogue_perm_is_still_required(self):
        c = copy.deepcopy(CAT)
        c['guides'][0].pop('perm')
        self.assertIn('unknown-perm', codes(G.check(c, TEXTS)))

    def test_missing_until_is_a_warning(self):
        c = copy.deepcopy(CAT)
        c['guides'][0]['steps'][1].pop('until')
        found = run(c)
        self.assertEqual(codes(found), set())
        self.assertIn('no-auto-advance', {f.code for f in found})


class Style(unittest.TestCase):
    def lint(self, text, lang='ar', key='guide.x.1'):
        return {f.code for f in G.lint({key: text}, lang)}

    def test_egyptian_and_jargon_words(self):
        self.assertIn('banned-word', self.lint('اضغط الزر اللي فوق.'))
        self.assertIn('banned-word', self.lint('احفظ عشان البيانات ما تضيعش.'))
        self.assertIn('banned-word', self.lint('ادخل على السيستم.'))
        self.assertEqual(self.lint('اضغط الزر الذي في الأعلى.'), set())
        self.assertEqual(self.lint('ستجد مشكلة مشتركة.'), set(), 'مش inside مشكلة/مشتركة is not the word مش')

    def test_digits_quotes_length_and_one_action(self):
        self.assertIn('eastern-digits', self.lint('اكتب ١٢ جنيهًا.'))
        self.assertIn('quoted-ui', self.lint('اضغط «[[shift.open]]».'))
        self.assertIn('sentence-long', self.lint(' '.join(['كلمة'] * 19) + '.'))
        self.assertIn('one-action', self.lint('اضغط [[a]] ثم اضغط [[b]].'))
        self.assertNotIn('one-action', self.lint('اضغط [[a]] ثم اضغط [[b]].', key='problem.x.do.1'))
        self.assertIn('one-action', self.lint('Press [[a]], then press [[b]].', 'en'))

    def test_release_turns_lint_into_errors(self):
        t = copy.deepcopy(TEXTS)
        t['ar']['guide.open-shift.why'] = 'لازم تفتح الوردية عشان تبيع.'
        self.assertEqual(codes(run(texts=t)), set())
        self.assertIn('banned-word', codes(run(texts=t, release=True)))

    def test_example_texts_follow_the_register(self):
        self.assertEqual(G.lint(TEXTS['ar'], 'ar'), [])
        self.assertEqual(G.lint(TEXTS['en'], 'en'), [])


class Progress(unittest.TestCase):
    def test_updates_and_course(self):
        rec = G.blank()
        rec = G.apply(rec, {'op': 'step', 'guide': 'open-shift', 'step': 2}, CAT)
        self.assertEqual(rec['current'], {'guide': 'open-shift', 'step': 2})
        rec = G.apply(rec, {'op': 'done', 'guide': 'open-shift'}, CAT, when='2026-10-09T06:00:00Z')
        self.assertIsNone(rec['current'])
        self.assertEqual(rec['done'], {'open-shift': '2026-10-09T06:00:00Z'})
        rec = G.apply(rec, {'op': 'lang', 'lang': 'en'}, CAT)
        c = G.course(CAT, 'cashier', rec)
        self.assertEqual((c['done'], c['total'], c['next']), (1, 3, 'first-sale'))
        rec = G.apply(rec, {'op': 'reset', 'guide': 'open-shift'}, CAT)
        self.assertEqual(G.course(CAT, 'cashier', rec)['next'], 'open-shift')
        self.assertEqual(G.course(CAT, 'cashier', rec, live_states={'shift.open'})['next'], 'first-sale')
        self.assertEqual(G.state(CAT, 'cashier', rec, ['shift.open', 'junk'])['states'], ['shift.open'])

    def test_bad_updates_are_refused(self):
        for bad in [None, {'op': 'step', 'guide': 'nope', 'step': 0}, {'op': 'step', 'guide': 'open-shift', 'step': 99},
                    {'op': 'step', 'guide': 'open-shift', 'step': True}, {'op': 'lang', 'lang': 'fr'},
                    {'op': 'fly'}, {'op': 'stop', 'extra': 1}]:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                G.apply(G.blank(), bad, CAT)

    def test_saved_per_person(self):
        db = sqlite3.connect(':memory:')
        db.execute(G.SQL)
        G.save(db, 'u1', G.apply(G.blank(), {'op': 'done', 'guide': 'add-product'}, CAT))
        G.save(db, 'u2', G.blank())
        self.assertIn('add-product', G.load(db, 'u1')['done'])
        self.assertEqual(G.load(db, 'u2')['done'], {})
        self.assertEqual(G.load(db, 'nobody'), G.blank())
        db.execute("UPDATE guide_progress SET data = 'not json' WHERE user_id = 'u2'")
        self.assertEqual(G.load(db, 'u2'), G.blank())
        self.assertEqual(G.problem_for(CAT, 'stock.not_enough')['id'], 'not-enough-stock')


class Cli(unittest.TestCase):
    def cli(self, *args):
        return subprocess.run([sys.executable, str(PKG / 'af_guide.py'), *args], capture_output=True, text=True)

    def test_check_lint_outline(self):
        r = self.cli('check', str(EX), '--ui', str(EX / 'ui-ar.json'), '--ui', str(EX / 'ui-en.json'),
                     '--access', str(EX / 'access.json'), '--errors', str(EX / 'errors.json'), '--release')
        self.assertEqual(r.returncode, 0, r.stdout)
        self.assertIn('OK: 5 guides', r.stdout)
        self.assertEqual(self.cli('lint', str(EX / 'ar.json'), '--release').returncode, 0)
        out = self.cli('outline', str(EX), 'en')
        self.assertIn('Cashier path', out.stdout)
        self.assertEqual(self.cli('nonsense').returncode, 2)

    def test_check_fails_on_errors(self):
        import tempfile
        with tempfile.TemporaryDirectory() as d:
            for f in EX.iterdir():
                shutil.copy(f, d)
            (Path(d) / 'en.json').write_text('{}', encoding='utf-8')
            r = self.cli('check', d)
            self.assertEqual(r.returncode, 1)
            self.assertIn('text-missing', r.stdout)


@unittest.skipUnless(shutil.which('node'), 'node is not installed')
class JsCore(unittest.TestCase):
    def test_node_core_tests(self):
        r = subprocess.run(['node', '--test', str(PKG / 'tests' / 'core.test.mjs')], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)

    def test_no_inner_html(self):
        src = (PKG / 'af-guide.js').read_text(encoding='utf-8')
        for bad in ('innerHTML', 'outerHTML', 'insertAdjacentHTML', 'eval(', 'new Function'):
            self.assertFalse(bad in src, bad)


class Walker(unittest.TestCase):
    def test_walker_is_strict_csp_safe(self):
        """walk_guides must work under script-src 'self' without 'unsafe-eval' (Store): no wait_for_function (eval
        while polling) and no JavaScript built from strings; values go in as evaluate() arguments."""
        import ast
        tree = ast.parse((PKG / 'testing' / 'walk_guides.py').read_text(encoding='utf-8'))
        calls = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)]
        self.assertNotIn('wait_for_function', {c.func.attr for c in calls})
        for c in calls:
            if c.func.attr == 'evaluate':
                self.assertIsInstance(c.args[0], ast.Name, 'evaluate() gets a fixed script constant, never an f-string')


class VendoredCopies(unittest.TestCase):
    def test_known_products_hold_a_fresh_copy(self):
        """Products copy the three files with a two-line header; a stale copy is a release blocker."""
        root = PKG.parents[2]
        sys.path.insert(0, str(PKG.parents[1] / 'scripts'))
        import vendor_guide as V
        for name in ('Store', 'Teachers', 'Yousef-Transportation', 'Mr.Ayman-HR'):
            repo = Path(os.environ.get(f'AF_{name.upper().replace("-", "_").replace(".", "_")}_REPO', root / name))
            for src, dest in V.destinations(repo):
                if not dest.exists():
                    continue
                body = dest.read_bytes() if dest.suffix == '.json' else dest.read_bytes().split(b'\n', 2)[2]
                self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(src.read_bytes()).hexdigest(),
                                 f'{dest} is stale: run python scripts/vendor_guide.py <product repo>')

    def test_vendored_copy_works_on_its_own(self):
        """Regression: the lexicon was not copied, so the vendored afguide.lint()/errors() crashed in the product."""
        import tempfile
        sys.path.insert(0, str(PKG.parents[1] / 'scripts'))
        import vendor_guide as V
        with tempfile.TemporaryDirectory() as d:
            repo = Path(d)
            (repo / 'server').mkdir()
            (repo / 'web' / 'js').mkdir(parents=True)
            self.assertEqual(V.main(['vendor_guide.py', str(repo)]), 0)
            lex = repo / 'server' / 'afguide_ar_lexicon.json'
            self.assertEqual(lex.read_bytes(), (PKG / 'style' / 'ar-lexicon.json').read_bytes())
            self.assertTrue((repo / 'web' / 'js' / 'vendor' / 'af-guide.js').exists())
            out = subprocess.run([sys.executable, '-c', 'import afguide, json; print(json.dumps(afguide.lint('
                                  '{"g.title": "اضغط على الزرار"}, "ar") is not None))'],
                                 cwd=repo / 'server', capture_output=True, text=True, env={**os.environ, 'PYTHONPATH': ''})
            self.assertEqual(out.returncode, 0, out.stderr)
            self.assertEqual(out.stdout.strip(), 'true')


if __name__ == '__main__':
    unittest.main()
