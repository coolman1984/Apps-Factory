"""CLI: create tokens and run the server.
  python -m control_center token --kind owner --name "Owner"     (prints the token once)
  python -m control_center token --kind agent --name "AI agent"
  python -m control_center revoke --name "AI agent"
  python -m control_center serve --host 127.0.0.1 --port 8765
"""
from __future__ import annotations
import argparse
import os
import sys

from . import db
from .security import new_token, token_hash


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
    args = parser.parse_args(argv)
    if args.action == "serve":
        import uvicorn
        from .app import create_app
        uvicorn.run(create_app(args.db), host=args.host, port=args.port)
        return 0
    conn = db.connect(args.db)
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
