"""af-access: every rule fires on a broken catalogue, the BAMS reference passes, the runtime guards hold, copies are fresh."""
import copy
import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path

PKG = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PKG))
import af_access as A  # noqa: E402

REFERENCE = json.loads((PKG / 'examples' / 'bams-catalogue.json').read_text(encoding='utf-8'))


def tiny():
    return {
        'product': 'tiny', 'languages': ['en', 'ar'], 'manage': 'users.manage',
        'groups': [
            {'id': 'pages', 'labels': {'en': 'Pages', 'ar': 'الصفحات'}, 'permissions': [
                {'id': 'sales.view', 'kind': 'page', 'labels': {'en': 'Sales page', 'ar': 'صفحة المبيعات'}}]},
            {'id': 'sell', 'labels': {'en': 'Selling', 'ar': 'البيع'}, 'permissions': [
                {'id': 'sales.return', 'requires': ['sales.view'], 'labels': {'en': 'Take returns', 'ar': 'استلام المرتجعات'}},
                {'id': 'cost.view', 'kind': 'field', 'labels': {'en': 'See cost', 'ar': 'رؤية التكلفة'}}]},
            {'id': 'admin', 'admin': True, 'labels': {'en': 'Administrator rights', 'ar': 'صلاحيات المدير'}, 'permissions': [
                {'id': 'users.manage', 'kind': 'admin', 'labels': {'en': 'Manage people', 'ar': 'إدارة الأشخاص'}}]},
        ],
        'pages': {'home': '*', 'sales': ['sales.view']},
        'profiles': [
            {'id': 'owner', 'locked': True, 'labels': {'en': 'Owner', 'ar': 'المالك'},
             'perms': ['sales.view', 'sales.return', 'cost.view', 'users.manage']},
            {'id': 'cashier', 'labels': {'en': 'Cashier', 'ar': 'كاشير'}, 'perms': ['sales.view', 'sales.return', 'cost.view']},
        ],
    }


def codes(cat):
    return {f.code for f in A.check(cat)}


class Catalogue(unittest.TestCase):
    def test_reference_and_tiny_are_clean(self):
        self.assertEqual(A.errors(REFERENCE), [])
        self.assertEqual(A.check(tiny()), [])

    def test_each_rule_fires(self):
        cases = [
            ('perm-id', lambda c: c['groups'][1]['permissions'][0].update(id='Sales Return')),
            ('perm-duplicate', lambda c: c['groups'][1]['permissions'].append(copy.deepcopy(c['groups'][1]['permissions'][0]))),
            ('perm-kind', lambda c: c['groups'][1]['permissions'][1].update(kind='secret')),
            ('label-missing', lambda c: c['groups'][1]['permissions'][1]['labels'].pop('ar')),
            ('requires-unknown', lambda c: c['groups'][1]['permissions'][0].update(requires=['nope.view'])),
            ('admin-group', lambda c: c['groups'][2].update(admin=False)),
            ('manage-not-admin', lambda c: c.update(manage='cost.view')),
            ('manage-missing', lambda c: c.update(manage='people.manage')),
            ('page-unguarded', lambda c: c['pages'].update(sales=[])),
            ('page-unknown-perm', lambda c: c['pages'].update(sales=['sales.see'])),
            ('locked-profile', lambda c: c['profiles'][0]['perms'].remove('cost.view')),
            ('profile-unknown-perm', lambda c: c['profiles'][1]['perms'].append('ghost.do')),
            ('profile-duplicate', lambda c: c['profiles'].append(dict(c['profiles'][1], id='cashier2'))),
            ('label-missing', lambda c: c['profiles'][1]['labels'].pop('ar')),
            ('profile-reserved-name', lambda c: c['profiles'][1]['labels'].update(en='Custom')),
            ('profile-missing-requires', lambda c: c['profiles'][1]['perms'].remove('sales.view')),
            ('no-work-profile', lambda c: c['profiles'][1]['perms'].append('users.manage')),
        ]
        for code, breaks in cases:
            with self.subTest(code=code):
                cat = tiny()
                breaks(cat)
                self.assertIn(code, codes(cat))

    def test_warnings_do_not_fail(self):
        cat = tiny()
        cat['profiles'][1]['perms'].remove('cost.view')  # nobody but the owner sees cost: allowed, but worth a look
        cat['pages'].pop('sales')
        found = A.check(cat)
        self.assertEqual({f.code for f in found}, {'perm-unused', 'page-perm-unused'})
        self.assertEqual(A.errors(cat), [])


class Guards(unittest.TestCase):
    ADMIN = {'users.manage'}

    def people(self):
        return [{'id': 'a', 'active': True, 'perms': ['users.manage', 'sales.view']},
                {'id': 'b', 'active': True, 'perms': ['sales.view'], 'link': True}]

    def test_safe_change(self):
        after = self.people()
        after[1]['perms'] = ['sales.view', 'sales.return']
        self.assertEqual(A.admin_safety(self.people(), after, 'a', self.ADMIN), [])

    def test_last_manager_and_self_lockout(self):
        after = self.people()
        after[0]['perms'] = ['sales.view']
        self.assertEqual(A.admin_safety(self.people(), after, 'a', self.ADMIN), ['last-manager', 'self-lockout'])
        after = self.people()
        after[0]['active'] = False
        self.assertIn('last-manager', A.admin_safety(self.people(), after, 'b', self.ADMIN))
        self.assertIn('self-lockout', A.admin_safety(self.people(), [after[1]], 'a', self.ADMIN))  # deleted myself

    def test_another_manager_keeps_the_shop_open(self):
        before = self.people() + [{'id': 'c', 'active': True, 'perms': ['users.manage']}]
        after = copy.deepcopy(before)
        after[0]['perms'] = []
        self.assertEqual(A.admin_safety(before, after, 'c', self.ADMIN), [])

    def test_link_never_carries_admin(self):
        after = self.people()
        after[1]['perms'].append('users.manage')
        self.assertEqual(A.admin_safety(self.people(), after, 'a', self.ADMIN), ['link-admin'])

    def test_helpers(self):
        self.assertEqual(A.effective(['a', 'b'], ['c'], ['a']), ['b', 'c'])
        self.assertEqual(A.perm_diff(['a', 'b'], ['b', 'c']), {'added': ['c'], 'removed': ['a']})
        profs = tiny()['profiles']
        self.assertEqual(A.matching_profile(['cost.view', 'sales.return', 'sales.view'], profs), 'cashier')
        self.assertIsNone(A.matching_profile(['sales.view'], profs))

    def test_matrix(self):
        m = A.matrix(tiny(), 'ar')
        self.assertIn('| استلام المرتجعات | ✓ | ✓ |', m)
        self.assertIn('المالك', m.splitlines()[0])


class Cli(unittest.TestCase):
    def run_cli(self, cat, tmp='cat.json'):
        path = Path(os.environ.get('TMPDIR', '/tmp')) / f'af-access-{os.getpid()}-{tmp}'
        path.write_text(json.dumps(cat), encoding='utf-8')
        try:
            return subprocess.run([sys.executable, str(PKG / 'af_access.py'), 'check', str(path)], capture_output=True, text=True)
        finally:
            path.unlink()

    def test_exit_codes(self):
        self.assertEqual(self.run_cli(tiny()).returncode, 0)
        broken = tiny()
        broken['profiles'][0]['locked'] = False
        r = self.run_cli(broken)
        self.assertEqual(r.returncode, 1)
        self.assertIn('locked-profile', r.stdout)


class VendoredCopies(unittest.TestCase):
    def test_known_products_hold_a_fresh_copy(self):
        """Products copy af_access.py with a two-line header; a stale copy is a release blocker."""
        src = (PKG / 'af_access.py').read_bytes()
        root = PKG.parents[2]
        for name in ('Store', 'Teachers', 'Yousef-Transportation'):
            copy_ = Path(os.environ.get(f'AF_{name.upper().replace("-", "_")}_REPO', root / name)) / 'server' / 'afaccess.py'
            if not copy_.exists():
                continue
            body = copy_.read_bytes().split(b'\n', 2)[2]
            self.assertEqual(hashlib.sha256(body).hexdigest(), hashlib.sha256(src).hexdigest(),
                             f'{copy_} is stale: run python scripts/vendor_access.py <product repo>')


if __name__ == '__main__':
    unittest.main()
