"""Vendor CLI: keygen / issue / verify. Keep private keys offline and out of every repository."""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path

from .core import PURPOSES, generate_keypair, issue, verify


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="python -m af_license")
    sub = parser.add_subparsers(dest="action", required=True)
    k = sub.add_parser("keygen", help="Create an Ed25519 key pair for one purpose")
    k.add_argument("--purpose", required=True, choices=sorted(PURPOSES))
    k.add_argument("--out-dir", required=True)
    i = sub.add_parser("issue", help="Sign a claims JSON file")
    i.add_argument("--key", required=True, help="Private key PEM (offline vendor machine)")
    i.add_argument("--purpose", required=True, choices=sorted(PURPOSES))
    i.add_argument("--claims", required=True)
    i.add_argument("--output", required=True)
    v = sub.add_parser("verify", help="Check a signed document with a public key")
    v.add_argument("document")
    v.add_argument("--public", required=True, help="kid:public_key_b64")
    v.add_argument("--purpose", required=True, choices=sorted(PURPOSES))
    v.add_argument("--product", required=True)
    v.add_argument("--device")
    args = parser.parse_args(argv)
    try:
        if args.action == "keygen":
            pem, public, kid = generate_keypair()
            out = Path(args.out_dir)
            out.mkdir(parents=True, exist_ok=True)
            private_path = out / f"{args.purpose}-{kid}.private.pem"
            fd = os.open(private_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "wb") as f:
                f.write(pem)
            (out / f"{args.purpose}-{kid}.public.txt").write_text(f"{kid}:{public}\n", encoding="utf-8")
            print(f"KEY {args.purpose} {kid}\nPRIVATE (keep offline, back up twice, never commit): {private_path}")
            print(f"PUBLIC (embed in the app): {kid}:{public}")
            return 0
        if args.action == "issue":
            claims = json.loads(Path(args.claims).read_text(encoding="utf-8"))
            doc = issue(Path(args.key).read_bytes(), args.purpose, claims)
            with Path(args.output).open("x", encoding="utf-8") as f:
                json.dump(doc, f, ensure_ascii=False, indent=2)
                f.write("\n")
            print("SIGNED:", args.output)
            return 0
        kid, _, public = args.public.partition(":")
        result = verify(json.loads(Path(args.document).read_text(encoding="utf-8")), {kid: public},
                        args.purpose, args.product, device_id=args.device)
        print(f"VALID={result.valid} STATE={result.state} REASON={result.reason or '-'}")
        return 0 if result.full_access else 2
    except (OSError, ValueError, json.JSONDecodeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
