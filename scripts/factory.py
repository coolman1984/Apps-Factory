#!/usr/bin/env python3
"""Apps Factory: dependency-free manifest/standards gate; governance only, not an app generator."""
from __future__ import annotations
import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MODES = {"desktop", "lan", "saas"}
MARKETS = {"EG", "SA", "AE", "EU", "US", "OTHER"}
PAID = {"subscription", "perpetual", "usage", "hybrid"}
REQUIRED = ("schema_version", "id", "name", "deployment", "markets", "buyer",
            "problem", "core_journey", "monetization", "data", "addons",
            "stage", "competitors", "acceptance", "evidence")
EVIDENCE = ("market_review", "privacy_review", "security_review",
            "clean_device_restore", "core_user_acceptance")

def load(path):
    with Path(path).open(encoding="utf-8") as file:
        return json.load(file)

def catalog():
    result = load(ROOT / "factory" / "controls.json")
    assert result["controls"] and len({c["id"] for c in result["controls"]}) == len(result["controls"])
    return result["controls"]

def applicable(controls, product):
    p = product["deployment"]
    paid = product["monetization"]["model"] in PAID
    ai = product["addons"]["ai_agents"]
    regulated = product["addons"]["regulated_overlay"] or product["data"]["sensitivity"] == "regulated"
    enabled = {p}
    if paid:
        enabled.add("paid")
    if ai:
        enabled.add("ai")
    if regulated:
        enabled.add("regulated")
    return [c for c in controls if enabled.intersection(c["profiles"])]

def valid_product(product, release=False):
    errors = []
    if not isinstance(product, dict):
        return ["Product must be a JSON object"], []
    for k in REQUIRED:
        if k not in product:
            errors.append("Missing required field: " + k)
    if errors:
        return errors, []
    if product["schema_version"] != "1.0":
        errors.append("Unsupported schema_version (expected 1.0)")
    if not isinstance(product["id"], str) or not re.fullmatch(r"[a-z][a-z0-9-]{2,48}", product["id"]):
        errors.append("Invalid product id (3–49 lowercase characters / digits / hyphens)")
    if product["deployment"] not in MODES:
        errors.append("Unknown deployment mode")
    if not isinstance(product["markets"], list) or not product["markets"] or not set(product["markets"]).issubset(MARKETS):
        errors.append("Unknown or empty markets")
    for k in ("name", "buyer", "problem", "core_journey"):
        if not isinstance(product[k], str) or not product[k].strip():
            errors.append("Empty field: " + k)
    if not isinstance(product["acceptance"], list) or not product["acceptance"]:
        errors.append("At least one acceptance scenario is required")
    money = product["monetization"]
    data = product["data"]
    addons = product["addons"]
    if not isinstance(money, dict) or not isinstance(data, dict) or not isinstance(addons, dict):
        return errors + ["monetization, data and addons must be objects"], []
    if money.get("model") not in (PAID | {"free"}):
        errors.append("Unknown monetization model")
    if money.get("expiry_data_access") != "read_export_backup":
        errors.append("Expiry must preserve read/export/backup")
    method = money.get("entitlement_method")
    if method not in {"offline_signed", "cloud_entitlement", "manual_contract", "none"}:
        errors.append("Unknown entitlement_method")
    if money.get("model") in PAID and method == "none":
        errors.append("Paid product cannot have no entitlement policy")
    if product["deployment"] == "saas" and money.get("model") in PAID and method != "cloud_entitlement":
        errors.append("Paid SaaS requires trusted cloud_entitlement")
    if product["deployment"] != "saas" and method == "cloud_entitlement":
        errors.append("Cloud entitlement for offline/LAN requires explicit architecture review")
    if data.get("sensitivity") not in {"ordinary", "personal", "sensitive", "regulated"}:
        errors.append("Unknown data sensitivity")
    if data.get("sensitivity") == "regulated" and addons.get("regulated_overlay") is not True:
        errors.append("Regulated data requires regulated_overlay")
    if not isinstance(data.get("backup_restore_plan"), str) or not data["backup_restore_plan"].strip():
        errors.append("Restore plan missing")
    if product["stage"] not in {"research", "prototype", "pilot_candidate", "field_accepted", "production"}:
        errors.append("Unknown stage")
    if not isinstance(product["competitors"], list):
        errors.append("competitors must be a list")
    if not isinstance(product["evidence"], dict) or any(k not in product["evidence"] for k in EVIDENCE):
        errors.append("Missing evidence slots")
    if errors:
        return errors, []
    selected = applicable(catalog(), product)
    provided = product.get("control_evidence", {})
    if not isinstance(provided, dict):
        return ["control_evidence must be an object"], selected
    ids = {c["id"] for c in catalog()}
    for k, v in provided.items():
        if k not in ids:
            errors.append("Unknown control ID: " + k)
        if not isinstance(v, dict) or v.get("status") not in {"planned", "implemented", "verified", "field_accepted"}:
            errors.append("Invalid control state: " + k)
    if release:
        if product["stage"] not in {"field_accepted", "production"}:
            errors.append("Release requires independent field acceptance")
        if len(product["competitors"]) < 5:
            errors.append("Release needs 5 competitor/alternative evidence rows, or documented owner exception")
        for k in EVIDENCE:
            v = product["evidence"].get(k, "")
            if not isinstance(v, str) or not v.strip() or v.upper().startswith(("PENDING", "TODO", "UNKNOWN")):
                errors.append("Unverified release evidence: " + k)
        for control in selected:
            ev = provided.get(control["id"], {})
            if ev.get("status") not in {"verified", "field_accepted"} or not str(ev.get("proof", "")).strip():
                errors.append("Missing verified proof: " + control["id"])
    return errors, selected

def new_product(args):
    if not re.fullmatch(r"[a-z][a-z0-9-]{2,48}", args.id):
        raise ValueError("Invalid product id")
    if args.market not in MARKETS:
        raise ValueError("Invalid market")
    record = {
        "schema_version": "1.0", "id": args.id, "name": args.name,
        "deployment": args.mode, "markets": [args.market],
        "buyer": "TODO: real paying customer and their roles",
        "problem": "TODO: current customer pain and economic cost",
        "core_journey": "TODO: one buyer journey from initial input to accepted output",
        "monetization": {"model": "subscription",
                         "entitlement_method": "cloud_entitlement" if args.mode == "saas" else "manual_contract",
                         "expiry_data_access": "read_export_backup"},
        "data": {"sensitivity": "personal", "has_financial_ledger": False,
                 "has_personal_data": True, "backup_restore_plan": "TODO: restore on a separate clean device"},
        "addons": {"ai_agents": False, "regulated_overlay": False},
        "stage": "research", "competitors": [],
        "acceptance": ["TODO: actual person completes one workflow and recovery"],
        "evidence": {k: "PENDING" for k in EVIDENCE},
        "control_evidence": {}, "features": [], "exclusions": []
    }
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return target

def main(argv=None):
    parser = argparse.ArgumentParser(description="Apps Factory manifest and evidence gate (NOT production app generator)")
    sub = parser.add_subparsers(dest="action", required=True)
    new = sub.add_parser("new", help="Create a clearly incomplete product spec, never overwrite")
    new.add_argument("--id", required=True)
    new.add_argument("--name", required=True)
    new.add_argument("--mode", required=True, choices=sorted(MODES))
    new.add_argument("--market", required=True, choices=sorted(MARKETS))
    new.add_argument("--output", required=True)
    check = sub.add_parser("check", help="Validate candidate; --release forces evidence gates")
    check.add_argument("product")
    check.add_argument("--release", action="store_true")
    sub.add_parser("doctor", help="Read catalog and schema and check consistency")
    sub.add_parser("controls", help="List standard control IDs")
    prompt = sub.add_parser("prompt", help="Print safe agent starting prompt for a product manifest")
    prompt.add_argument("product")
    args = parser.parse_args(argv)
    try:
        if args.action == "doctor":
            controls = catalog()
            schema = load(ROOT / "factory" / "product.schema.json")
            ids = [x["id"] for x in controls]
            if not schema.get("required") or not {"desktop", "lan", "saas"}.issubset(set(schema["properties"]["deployment"]["enum"])):
                raise ValueError("Missing product schema requirements")
            print(f"FACTORY READY: {len(ids)} unique controls; schema present. This does NOT verify a commercial product.")
            return 0
        if args.action == "controls":
            for c in catalog():
                print(c["id"], c["slug"], "/".join(c["profiles"]))
            return 0
        if args.action == "new":
            print("Created:", new_product(args), "(research only; complete acceptance and evidence before release)")
            return 0
        product = load(args.product)
        errors, selected = valid_product(product, release=getattr(args, "release", False))
        if args.action == "prompt":
            if errors:
                print("\n".join("ERROR: "+e for e in errors), file=sys.stderr)
                return 2
            print("Read AGENTS.md, FACTORY_CONSTITUTION.md, docs/MARKET_AND_STANDARDS.md and DELIVERY_GATES.md first. "
                  "Research real competitors with cited dates and price evidence. Build only the paid journey for "
                  f"{product['name']} ({product['deployment']}, {','.join(product['markets'])}); "
                  "reuse verified platform components without rewriting existing products. "
                  "Never hardcode demo credentials in production. "
                  "Show exact tests, skipped checks, release limitations and required customer acceptance.")
            return 0
        print(f"PRODUCT: {product.get('id', '?')} | applicable controls: {len(selected)}")
        if errors:
            for e in errors:
                print("NO-GO:", e)
            return 2
        print("SPEC VALID. Not a certification, security audit, completed codebase or selling approval.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, AssertionError, json.JSONDecodeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
