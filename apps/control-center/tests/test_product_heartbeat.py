"""Contract: what a real product (Al-Store) sends as its heartbeat is accepted by the Control Center, and the Control Center's
strict model accepts exactly the fields the product's support.py is allowed to send (SUP-04: no silent telemetry growth).
Skipped when the Al-Store repository is not next to this one (set AF_STORE_REPO to its folder)."""
import os
import sys
import tempfile
import unittest
from pathlib import Path

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parents[1] / 'packages' / 'af-license'))
STORE = Path(os.environ.get('AF_STORE_REPO', HERE.parents[2] / 'Store'))

from fastapi.testclient import TestClient  # noqa: E402

from control_center import db  # noqa: E402
from control_center.app import Heartbeat, create_app  # noqa: E402
from control_center.security import new_token, token_hash  # noqa: E402


@unittest.skipUnless((STORE / 'server' / 'support.py').exists(), 'the Al-Store repository is not available')
class ProductHeartbeatContract(unittest.TestCase):
    def test_the_products_payload_is_exactly_what_the_control_center_accepts(self):
        os.environ.setdefault('STORE_DEVICE_ID', 'contract-test')
        sys.path.insert(0, str(STORE / 'server'))
        import support  # Al-Store's module

        required = {k for k, f in Heartbeat.model_fields.items() if f.is_required()}
        self.assertTrue(set(support.SENT_FIELDS) <= set(Heartbeat.model_fields), 'the product sends a field the Control Center refuses')
        self.assertTrue(required <= set(support.SENT_FIELDS), 'the product omits a field the Control Center requires')

        class FakeApp:
            def __init__(self, folder):
                self.backup_dir = os.path.join(folder, 'backups')
                self.data_dir = folder
                os.makedirs(self.backup_dir)
                open(os.path.join(self.backup_dir, 'store-20261008-120000.db'), 'wb').write(b'x')

            def licence(self):
                return {'state': 'trial'}

            def recent_errors(self):
                return 2

        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        body = support.payload(FakeApp(tmp.name))
        app = create_app(os.path.join(tmp.name, 'cc.db'))
        conn = app.state.conn
        owner = new_token('ven')
        conn.execute("INSERT INTO vendor_tokens (id, name, token_hash, kind, created_at) VALUES (?,?,?,?,?)",
                     (db.uuid7(), 'owner', token_hash(owner), 'owner', db.now_iso()))
        client = TestClient(app)
        H = {'Authorization': 'Bearer ' + owner}
        cid = client.post('/api/customers', json={'name': 'محل تجريبي', 'phone': '01000000000'}, headers=H).json()['id']
        made = client.post('/api/installs', json={'customer_id': cid, 'product': 'al-store', 'tier': 'standalone'}, headers=H).json()
        r = client.post('/api/agent/heartbeat', json=body, headers={'X-Install-Token': made['install_token']})
        self.assertEqual(r.status_code, 200, r.text)
        self.assertEqual(client.post('/api/agent/heartbeat', json={**body, 'customer_names': ['x']},
                                     headers={'X-Install-Token': made['install_token']}).status_code, 422)
        conn.close()


if __name__ == '__main__':
    unittest.main()
