"""CLI: create tokens and run the server.
  python -m control_center token --kind owner --name "Owner"     (prints the token once)
  python -m control_center token --kind agent --name "AI agent"
  python -m control_center revoke --name "AI agent"
  python -m control_center serve --host 127.0.0.1 --port 8765   (pulls the relay + runs time rules in the background
                                                                when CC_RELAY_URL / CC_RELAY_TOKEN are set)
  python -m control_center pull-relay      (once: needs CC_RELAY_URL and CC_RELAY_TOKEN)
  python -m control_center alerts          (once: time-based alert rules)
  python -m control_center retention       (once: delete data past its retention period)
"""
from __future__ import annotations
import argparse
import os
import sys

from . import db
from .security import new_token, token_hash


def background(conn, every_s: int | None = None, lock=None, deliverer=None) -> None:
    """Every CC_RELAY_EVERY seconds (default 300): pull the relay if configured, run the time-based alert rules;
    once a day: retention. Errors are printed and the loop goes on. The lock is held only for database work: relay
    calls and alert sends happen outside it, so the dashboard never waits for the network."""
    import threading
    import time
    from . import alerts, telemetry
    every = every_s or int(os.environ.get("CC_RELAY_EVERY", "300"))
    import contextlib
    guard = lock or contextlib.nullcontext()

    def loop():
        last_retention = 0.0
        while True:
            try:
                if os.environ.get("CC_RELAY_URL") and os.environ.get("CC_RELAY_TOKEN"):
                    telemetry.pull_relay(conn, os.environ["CC_RELAY_URL"], os.environ["CC_RELAY_TOKEN"], lock=lock)
                with guard:
                    alerts.periodic(conn, deliver=False)
                    if time.time() - last_retention > 86400:
                        telemetry.retention(conn)
                        last_retention = time.time()
                if deliverer is not None:
                    deliverer.wake()
                else:
                    alerts.deliver_queued(conn, lock)
            except Exception as error:  # noqa: BLE001 - keep the loop alive; the dashboard shows staleness
                print("background:", type(error).__name__, error, file=sys.stderr)
            time.sleep(every)
    threading.Thread(target=loop, name="cc-background", daemon=True).start()


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m control_center")
    parser.add_argument("--db", default=os.environ.get("CC_DB", "data/control-center.db"))
    sub = parser.add_subparsers(dest="action", required=True)
    t = sub.add_parser("token")
    t.add_argument("--kind", required=True, choices=["owner", "agent"])
    t.add_argument("--name", required=True)
    r = sub.add_parser("revoke")
    r.add_argument("--name", required=True)
    s = sub.add_parser("serve")
    s.add_argument("--host", default="127.0.0.1")
    s.add_argument("--port", type=int, default=8765)
    sub.add_parser("pull-relay")
    sub.add_parser("alerts")
    sub.add_parser("retention")
    args = parser.parse_args(argv)
    if args.action == "serve":
        import uvicorn
        from .app import create_app
        app = create_app(args.db)
        background(app.state.conn, lock=app.state.lock, deliverer=app.state.deliverer)
        uvicorn.run(app, host=args.host, port=args.port)
        return 0
    conn = db.connect(args.db)
    if args.action in ("pull-relay", "alerts", "retention"):
        import json
        from . import alerts, telemetry
        if args.action == "pull-relay":
            url, token = os.environ.get("CC_RELAY_URL", ""), os.environ.get("CC_RELAY_TOKEN", "")
            if not url or not token:
                print("set CC_RELAY_URL and CC_RELAY_TOKEN", file=sys.stderr)
                return 2
            out = telemetry.pull_relay(conn, url, token)
            out["alerts_sent"] = alerts.deliver_queued(conn)
            print(json.dumps(out))
        elif args.action == "alerts":
            print(json.dumps({"fired": len(alerts.periodic(conn))}))
        else:
            print(json.dumps(telemetry.retention(conn)))
        return 0
    if args.action == "token":
        token = new_token("ven")
        conn.execute("INSERT INTO vendor_tokens (id, name, token_hash, kind, created_at) VALUES (?,?,?,?,?)",
                     (db.uuid7(), args.name, token_hash(token), args.kind, db.now_iso()))
        db.audit(conn, "cli", "token.create", None, name=args.name, kind=args.kind)
        print(f"{args.kind} token for {args.name} (shown once, keep it in a password manager):\n{token}")
        return 0
    changed = conn.execute("UPDATE vendor_tokens SET revoked = 1 WHERE name = ?", (args.name,)).rowcount
    db.audit(conn, "cli", "token.revoke", None, name=args.name)
    print(f"revoked {changed} token(s)")
    return 0 if changed else 1


if __name__ == "__main__":
    sys.exit(main())
