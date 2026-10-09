"""af-guide: every rule fires on a broken catalogue, a good one passes, the register lint and progress work, copies are fresh."""
import copy
import hashlib
import os
import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_guide as G  # noqa: E402


def T(n, ar='افتح صفحة البيع', en='Open the sale page'):
    return {'ar': [ar] * n, 'en': [en] * n}


def good():
    return {
        'product': 'tiny', 'languages': ['ar', 'en'], 'facts': ['shopNamed', 'shiftOpened', 'saleMade'],
        'pages': ['settings', 'cash', 'pos'], 'roles': ['owner', 'cashier'], 'setup_guides': ['setup'],
        'guides': [{'id': 'setup', 'steps': 2, 'pages': ['settings'], 'texts': T(5)},
                   {'id': 'openShift', 'steps': 3, 'pages': ['cash'], 'texts': T(6)},
                   {'id': 'sell', 'steps': 4, 'pages': ['pos'], 'texts': T(7)}],
        'paths': [{'id': 'owner', 'admin': True, 'roles': ['owner'], 'texts': T(2),
                   'lessons': [{'guide': 'setup', 'fact': 'shopNamed'}, {'guide': 'openShift', 'fact': 'shiftOpened'},
                               {'guide': 'sell', 'fact': 'saleMade'}]},
                  {'id': 'cashier', 'roles': ['cashier'], 'texts': T(2),
                   'lessons': [{'guide': 'openShift', 'fact': 'shiftOpened'}, {'guide': 'sell', 'fact': 'saleMade'},
                               {'guide': 'openShift'}]}],
        'situations': [{'id': 'drawerShort', 'guide': 'openShift', 'texts': T(2)}],
    }


class Catalogue(unittest.TestCase):
    def test_good_is_clean(self):
        self.assertEqual(G.check(good()), [])

    def test_each_rule_fires(self):
        cases = [
            ('words-missing', lambda c: c['guides'][1]['texts']['en'].pop()),
            ('words-missing', lambda c: c['guides'][1]['texts']['ar'].__setitem__(0, ' ')),
            ('register', lambda c: c['guides'][1]['texts']['ar'].__setitem__(1, 'دوس على الزرار ده عشان تحفظ')),
            ('register', lambda c: c['situations'][0]['texts']['ar'].__setitem__(1, 'يُرجى التحقق من الاتصال')),
            ('guide-id', lambda c: c['guides'][0].update(id='Open shift')),
            ('guide-short', lambda c: c['guides'][0].update(steps=1, texts=T(4))),
            ('page-without-guide', lambda c: c['pages'].append('reports')),
            ('no-paths', lambda c: c.update(paths=[])),
            ('no-admin-path', lambda c: c['paths'][0].pop('admin')),
            ('path-duplicate', lambda c: c['paths'][1].update(id='owner')),
            ('path-short', lambda c: c['paths'][1]['lessons'].pop()),
            ('lesson-unknown-guide', lambda c: c['paths'][1]['lessons'][0].update(guide='nope')),
            ('lesson-unknown-fact', lambda c: c['paths'][1]['lessons'][0].update(fact='nope')),
            ('admin-path-order', lambda c: c['paths'][0]['lessons'].reverse()),
            ('role-without-path', lambda c: c['roles'].append('storekeeper')),
            ('problem-unknown-guide', lambda c: c['situations'][0].update(guide='nope')),
            ('no-guides', lambda c: c.update(guides=[], paths=[], situations=[])),
            ('lesson-not-allowed', lambda c: (c['guides'][0].update(perm='settings.edit'), c.update(role_perms={'owner': '*', 'cashier': ['pos.sell']}),
                                              c['paths'][1]['lessons'].append({'guide': 'setup'}))),
        ]
        for code, breaks in cases:
            with self.subTest(code=code):
                cat = copy.deepcopy(good())
                breaks(cat)
                self.assertIn(code, {f.code for f in G.check(cat)})

    def test_warnings(self):
        cat = good()
        cat['situations'][0].pop('guide')
        for x in cat['paths'][1]['lessons']:
            x.pop('fact', None)
        self.assertEqual({f.code for f in G.check(cat)}, {'problem-without-guide', 'path-unchecked'})
        self.assertEqual(G.errors(cat), [])


class Register(unittest.TestCase):
    def test_simple_formal_arabic_passes(self):
        for ok in ('اضغط زر «حفظ» أسفل النافذة، وستظهر رسالة تؤكد الحفظ.', 'إذا لم يظهر الصنف، فتأكد أنه غير مخفي.',
                   'افتح «الخزنة والوردية» واكتب المبلغ الموجود في الدرج.', 'هذه الخطوة تحمي بياناتك.'):
            self.assertEqual(G.register(ok), [], ok)

    def test_street_and_stiff_words_are_caught(self):
        self.assertIn(('مش', 'colloquial'), G.register('البرنامج مش راضي يحفظ'))
        self.assertIn(('عشان', 'colloquial'), G.register('عشان تحفظ'))
        self.assertIn(('يُرجى', 'stiff'), G.register('يُرجى إعادة المحاولة'))
        self.assertIn(('حيث إن', 'stiff'), G.register('حيث إن العملية لم تكتمل'))
        self.assertEqual(G.register('دمشق'), [])  # a word that only contains a marker is fine


class Progress(unittest.TestCase):
    def test_where_the_person_stands(self):
        lessons = good()['paths'][1]['lessons']
        self.assertEqual(G.progress(lessons, {'shiftOpened': True}), (1, [True, False, False]))
        self.assertEqual(G.progress(lessons, {'shiftOpened': True, 'saleMade': True}, ['openShift']), (3, [True, True, True]))


class VendoredCopies(unittest.TestCase):
    def test_known_products_hold_a_fresh_copy(self):
        src = (PKG / 'af_guide.py').read_bytes()
        root = PKG.parents[2]
        for name in ('Store', 'Teachers', 'Yousef-Transportation'):
            path = Path(os.environ.get(f'AF_{name.upper().replace("-", "_")}_REPO', root / name)) / 'server' / 'afguide.py'
            if path.exists():
                body = path.read_bytes().split(b'\n', 2)[2]
                self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(src).hexdigest(),
                                 f'{path} is stale: run python scripts/vendor_guide.py <product repo>')


if __name__ == '__main__':
    unittest.main()
