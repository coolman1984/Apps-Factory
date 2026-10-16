"""Example product consumer: af-auth with a custom manage permission id."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
import af_auth as auth


def run_checks() -> bool:
    s = auth.AuthStore(':memory:', {'manage_permission': 'people.manage'})
    s.setup('owner', 'Site Owner', 'K9-Secure-pass')
    owner = s.get_by_username('owner')
    assert 'people.manage' in owner['perms']
    s.register('staff', 'Staff Member', 'K9-Secure-pass')
    pending = s.get_by_username('staff')
    s.review(pending['id'], 'approve', perms=['app.view'])
    token, user = s.login('staff', 'K9-Secure-pass')
    assert token and user['username'] == 'staff'
    s.close()
    return True


if __name__ == '__main__':
    run_checks()
    print('ok')
