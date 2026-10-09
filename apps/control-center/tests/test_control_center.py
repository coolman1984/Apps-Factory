import json
import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
sys.path.insert(0, str(APP.parents[1] / "packages" / "af-license"))
from fastapi.testclient import TestClient  # noqa: E402

import af_license  # noqa: E402
from control_center import db  # noqa: E402
from control_center.app import create_app, health  # noqa: E402
from control_center.redact import redact  # noqa: E402
from control_center.security import new_token, token_hash  # noqa: E402


class ControlCenterTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.pem, self.pub, self.kid = af_license.generate_keypair()
        os.environ["CC_LICENCE_PUBLIC_KEYS"] = f"{self.kid}:{self.pub}"
        self.app = create_app(str(Path(self.tmp.name) / "cc.db"))
        self.c = TestClient(self.app)
        conn = self.app.state.conn
        self.owner, self.agent = new_token("ven"), new_token("ven")
        for name, tok, kind in (("المالك", self.owner, "owner"), ("المساعد", self.agent, "agent")):
            conn.execute("INSERT INTO vendor_tokens (id, name, token_hash, kind, created_at) VALUES (?,?,?,?,?)",
                         (db.uuid7(), name, token_hash(tok), kind, db.now_iso()))
        self.O = {"Authorization": "Bearer " + self.owner}
        self.A = {"Authorization": "Bearer " + self.agent}
        cid = self.c.post("/api/customers", json={"name": "سنتر النور (تجريبي)", "phone": "01000000000"}, headers=self.O).json()["id"]
        r = self.c.post("/api/installs", json={"customer_id": cid, "product": "hessa-centre", "tier": "office_server"},
                        headers=self.O).json()
        self.install_id, self.I = r["id"], {"X-Install-Token": r["install_token"]}

    def tearDown(self):
        self.app.state.close()
        self.tmp.cleanup()

    def beat(self, **extra):
        body = {"version": "1.4.0", "licence_state": "active", "error_count": 0,
                "last_backup_at": datetime.now(timezone.utc).isoformat(), "disk_free_mb": 50000, **extra}
        return self.c.post("/api/agent/heartbeat", json=body, headers=self.I)

    def grant(self, scopes=("repair",), minutes=30):
        return self.c.post("/api/agent/grants", json={"scopes": list(scopes), "minutes": minutes,
                                                       "approved_by": "أ. منى (مديرة السنتر)"}, headers=self.I).json()

    def test_auth_is_required_everywhere(self):
        self.assertEqual(self.c.get("/api/installs").status_code, 401)
        self.assertEqual(self.c.get("/api/installs", headers={"Authorization": "Bearer ven_wrong"}).status_code, 401)
        self.assertEqual(self.c.post("/api/agent/heartbeat", json={}).status_code, 401)
        self.assertEqual(self.c.post("/api/customers", json={"name": "x y"}, headers=self.A).status_code, 403)

    def test_heartbeat_and_health(self):
        self.assertEqual(self.beat().status_code, 200)
        item = self.c.get("/api/installs", headers=self.O).json()[0]
        self.assertEqual(item["health"]["status"], "ok")
        self.beat(error_count=3, licence_state="grace", last_backup_at=None)
        item = self.c.get("/api/installs", headers=self.O).json()[0]
        self.assertEqual(item["health"]["status"], "warning")
        self.assertEqual(len(item["health"]["reasons"]), 3)

    def test_heartbeat_refuses_extra_fields(self):  # SUP-04: no silent telemetry growth
        r = self.beat(customer_names=["x"])
        self.assertEqual(r.status_code, 422)

    def test_stale_and_never(self):
        old = {"received_at": (datetime.now(timezone.utc) - timedelta(days=3)).isoformat(), "last_backup_at": None,
               "licence_state": "active", "error_count": 0, "pending_sync": None, "disk_free_mb": None}
        self.assertEqual(health(old, datetime.now(timezone.utc))["status"], "stale")
        self.assertEqual(health(None, datetime.now(timezone.utc))["status"], "never")

    def test_ticket_is_redacted_and_marked_untrusted(self):
        r = self.c.post("/api/agent/tickets", headers=self.I, json={
            "subject": "الطباعة واقفة", "message": "كلموني على 01012345678 أو mona@example.com",
            "bundle": {"log": "password=Secret123 student nid 29001011234567", "errors": ["E-PRN-02"]}})
        self.assertEqual(r.status_code, 201)
        t = self.c.get("/api/tickets", headers=self.A).json()[0]
        self.assertNotIn("01012345678", t["message"])
        self.assertNotIn("mona@example.com", t["message"])
        self.assertNotIn("Secret123", json.dumps(t["bundle"]))
        self.assertNotIn("29001011234567", json.dumps(t["bundle"]))
        self.assertTrue(t["untrusted_text"])

    def test_agent_reply_is_draft_and_hidden_from_customer(self):
        tid = self.c.post("/api/agent/tickets", headers=self.I, json={"subject": "مشكلة", "message": "تفاصيل"}).json()["id"]
        self.c.post(f"/api/tickets/{tid}", headers=self.A, json={"vendor_reply": "جرب تعيد التشغيل"})
        self.assertIsNone(self.c.get("/api/agent/tickets", headers=self.I).json()[0]["vendor_reply"])
        self.assertEqual(self.c.post(f"/api/tickets/{tid}", headers=self.A, json={"status": "resolved"}).status_code, 403)
        self.c.post(f"/api/tickets/{tid}", headers=self.O, json={"vendor_reply": "تم الإصلاح", "status": "resolved"})
        mine = self.c.get("/api/agent/tickets", headers=self.I).json()[0]
        self.assertEqual((mine["vendor_reply"], mine["status"]), ("تم الإصلاح", "resolved"))

    def test_repair_needs_allowlist_and_live_customer_grant(self):
        body = {"install_id": self.install_id, "action": "integrity_check"}
        self.assertEqual(self.c.post("/api/repairs", json=body, headers=self.O).status_code, 403)  # no grant
        self.grant(scopes=("view_diagnostics",))
        self.assertEqual(self.c.post("/api/repairs", json=body, headers=self.O).status_code, 403)  # wrong scope
        self.grant()
        bad = {"install_id": self.install_id, "action": "run_shell"}
        self.assertEqual(self.c.post("/api/repairs", json=bad, headers=self.O).status_code, 403)
        self.assertEqual(self.c.post("/api/repairs", json=body, headers=self.O).json()["status"], "approved")
        actions = [a["action"] for a in self.c.get("/api/audit", headers=self.O).json()]
        self.assertIn("repair.refused", actions)

    def test_agent_cannot_approve_its_own_repair(self):
        self.grant()
        rid = self.c.post("/api/repairs", headers=self.A,
                          json={"install_id": self.install_id, "action": "rebuild_search_index"}).json()["id"]
        self.assertEqual(self.c.get("/api/agent/repairs", headers=self.I).json(), [])
        self.assertEqual(self.c.post(f"/api/repairs/{rid}/approve", headers=self.A).status_code, 403)
        self.assertEqual(self.c.post(f"/api/repairs/{rid}/approve", headers=self.O).status_code, 200)
        todo = self.c.get("/api/agent/repairs", headers=self.I).json()
        self.assertEqual(todo[0]["action"], "rebuild_search_index")
        self.assertEqual(self.c.post(f"/api/agent/repairs/{rid}", headers=self.I,
                                     json={"status": "done", "result": "ok"}).status_code, 200)

    def test_customer_ends_grant_and_pending_repairs_cancel(self):
        g = self.grant()
        self.assertRegex(g["code"], r"^\d{3}-\d{3}-\d{3}$")
        self.c.post("/api/repairs", headers=self.O, json={"install_id": self.install_id, "action": "integrity_check"})
        self.assertEqual(self.c.delete(f"/api/agent/grants/{g['id']}", headers=self.I).status_code, 200)
        self.assertEqual(self.c.get("/api/agent/repairs", headers=self.I).json(), [])
        self.assertEqual(self.c.post("/api/repairs", headers=self.O,
                                     json={"install_id": self.install_id, "action": "integrity_check"}).status_code, 403)

    def test_grant_limits(self):
        r = self.c.post("/api/agent/grants", headers=self.I, json={"scopes": ["repair"], "minutes": 600, "approved_by": "منى"})
        self.assertEqual(r.status_code, 422)
        r = self.c.post("/api/agent/grants", headers=self.I, json={"scopes": ["root"], "minutes": 30, "approved_by": "منى"})
        self.assertEqual(r.status_code, 422)

    def test_licence_signed_offline_is_verified_before_storing(self):
        claims = self.c.get(f"/api/installs/{self.install_id}/licence-claims?days=30", headers=self.O).json()
        doc = af_license.issue(self.pem, "licence", claims)
        ok = self.c.post("/api/licences", headers=self.O, json={"document": doc, "install_id": self.install_id})
        self.assertEqual(ok.status_code, 201, ok.text)
        self.assertEqual(self.c.post("/api/licences", headers=self.O,
                                     json={"document": doc, "install_id": self.install_id}).status_code, 409)
        forged = json.loads(json.dumps(doc))
        forged["payload"]["licence_id"] = "LIC-FAKE"
        forged["payload"]["expires"] = "2099-01-01T00:00:00Z"
        self.assertEqual(self.c.post("/api/licences", headers=self.O,
                                     json={"document": forged, "install_id": self.install_id}).status_code, 422)
        self.assertEqual(len(self.c.get("/api/licences/expiring?days=40", headers=self.O).json()), 1)

    def test_deactivated_install_is_locked_out(self):
        self.c.post(f"/api/installs/{self.install_id}/deactivate", headers=self.O)
        self.assertEqual(self.beat().status_code, 401)

    def test_overview_and_dashboard(self):
        self.beat()
        o = self.c.get("/api/overview", headers=self.O).json()
        self.assertEqual((o["customers"], o["installs"], o["ok"]), (1, 1, 1))
        page = self.c.get("/")
        self.assertEqual(page.status_code, 200)
        self.assertIn('dir="rtl"', page.text)
        self.assertNotIn("innerHTML", page.text)  # customer text is rendered with textContent only

    def test_redaction_patterns(self):
        out = redact({"a": ["+201112223334", "token: ins_" + "x" * 30], "b": "-----BEGIN PRIVATE KEY-----\nabc\n-----END PRIVATE KEY-----"})
        self.assertNotIn("1112223334", json.dumps(out))
        self.assertIn("[PRIVATE_KEY]", out["b"])

    def test_ids_are_uuid7_and_schema_versioned(self):
        self.assertEqual(db.uuid7()[14], "7")
        v = self.app.state.conn.execute("SELECT version FROM schema_version").fetchone()["version"]
        self.assertEqual(v, len(db.MIGRATIONS))


if __name__ == "__main__":
    unittest.main()
