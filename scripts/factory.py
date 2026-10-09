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
SCHEMA_VERSIONS = {"1.0", "1.1"}
TIERS = {"standalone", "office_server", "office_mesh", "cloud_sync", "cloud_only"}
CLOUD_TIERS = {"cloud_sync", "cloud_only"}
TIERS_BY_MODE = {"desktop": {"standalone", "cloud_sync"},
                 "lan": {"office_server", "office_mesh", "cloud_sync"},
                 "saas": {"cloud_only", "cloud_sync"}}
DEFAULT_TIER = {"desktop": "standalone", "lan": "office_server", "saas": "cloud_only"}
DEFAULT_CLIENTS = {"desktop": ["windows_desktop"], "lan": ["windows_desktop", "browser"], "saas": ["browser"]}
CLIENTS = {"windows_desktop", "browser", "mobile_pwa"}
PROFILES = {"desktop", "lan", "saas", "paid", "ai", "regulated", "sync", "mesh", "mobile", "multi_site", "multi_owner",
            "windows"}
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

def connectivity(product):
    """Explicit connectivity (schema 1.1) or the legacy default implied by deployment (schema 1.0)."""
    if "connectivity" in product:
        return product["connectivity"]
    mode = product["deployment"]
    return {"tier": DEFAULT_TIER[mode], "sites": "single",
            "clients": list(DEFAULT_CLIENTS[mode]), "multi_owner": False}

def profiles(product):
    enabled = {product["deployment"]}
    if product["monetization"]["model"] in PAID:
        enabled.add("paid")
    if product["addons"]["ai_agents"]:
        enabled.add("ai")
    if product["addons"]["regulated_overlay"] or product["data"]["sensitivity"] == "regulated":
        enabled.add("regulated")
    link = connectivity(product)
    if link["tier"] == "cloud_sync":
        enabled.update({"sync", "saas"})  # the hub is a hosted multi-tenant service
    if link["tier"] == "office_mesh":
        enabled.add("mesh")  # every office PC holds a full replica and keeps working alone
    if "mobile_pwa" in link["clients"]:
        enabled.add("mobile")
    if "windows_desktop" in link["clients"]:
        enabled.add("windows")  # we ship an EXE: protection, signing and safe-update controls
    if link["sites"] == "multi":
        enabled.add("multi_site")
    if link["multi_owner"]:
        enabled.add("multi_owner")
    return enabled

def applicable(controls, product):
    enabled = profiles(product)
    return [c for c in controls if enabled.intersection(c["profiles"])]

def connectivity_errors(product):
    if product["schema_version"] == "1.1" and "connectivity" not in product:
        return ["Missing required field: connectivity (schema 1.1)"]
    if product["deployment"] not in MODES:
        return []
    link = connectivity(product)
    if not isinstance(link, dict):
        return ["connectivity must be an object"]
    errors = []
    tier, sites, clients = link.get("tier"), link.get("sites"), link.get("clients")
    if tier not in TIERS:
        return ["Unknown connectivity tier"]
    if tier not in TIERS_BY_MODE[product["deployment"]]:
        errors.append(f"Tier {tier} does not fit deployment {product['deployment']}")
    if sites not in {"single", "multi"}:
        errors.append("connectivity.sites must be single or multi")
    if (not isinstance(clients, list) or not clients or not all(isinstance(c, str) for c in clients)
            or len(set(clients)) != len(clients) or not set(clients).issubset(CLIENTS)):
        errors.append("connectivity.clients must be a non-empty unique list of windows_desktop/browser/mobile_pwa")
        clients = []
    if not isinstance(link.get("multi_owner"), bool):
        errors.append("connectivity.multi_owner must be true or false")
    cloud = tier in CLOUD_TIERS
    if "mobile_pwa" in clients and not cloud:
        errors.append("mobile_pwa needs a trusted HTTPS origin: choose cloud_sync or cloud_only")
    if sites == "multi" and not cloud:
        errors.append("Multiple sites need cloud_sync or cloud_only")
    grace = link.get("offline_grace_days")
    if tier == "cloud_sync" and (isinstance(grace, bool) or not isinstance(grace, int) or not 1 <= grace <= 60):
        errors.append("cloud_sync requires offline_grace_days between 1 and 60")
    actions = link.get("mobile_offline_actions", [])
    if not isinstance(actions, list) or not all(isinstance(a, str) and a.strip() for a in actions):
        errors.append("mobile_offline_actions must be a list of action names")
    elif actions and ("mobile_pwa" not in clients or tier != "cloud_sync"):
        errors.append("Offline mobile actions require mobile_pwa on the cloud_sync tier")
    residency = product["data"].get("residency") if isinstance(product["data"], dict) else None
    if cloud and (not isinstance(residency, str) or not residency.strip()):
        errors.append("Cloud tiers require data.residency (hosting region)")
    return errors

def advisories(product):
    link = connectivity(product)
    notes = []
    if link["tier"] == "office_server":
        notes.append("office_server: when the main PC is off, other devices cannot write. "
                     "Say so in the contract or offer office_mesh / cloud_sync.")
    if link["tier"] == "office_mesh":
        notes.append("office_mesh: every joined PC works alone and merges later; conflicts need an administrator's decision (MESH-01).")
    if link["tier"] in CLOUD_TIERS and product["data"].get("has_personal_data"):
        notes.append("Personal data leaves the premises: privacy_review must cover hosting region "
                     "and cross-border transfer before any pilot.")
    if link["tier"] == "cloud_sync" and product["monetization"]["model"] == "free":
        notes.append("cloud_sync has recurring hosting cost; a free model needs a recorded owner exception.")
    if link["tier"] == "cloud_sync" and product["data"].get("has_financial_ledger"):
        notes.append("Money must be append-only events with derived balances; cash close is hub-confirmed (SYNC-02).")
    if "mobile_pwa" in link["clients"]:
        notes.append("iOS PWA limits: push only after Add to Home Screen, no background sync, "
                     "no WebUSB printing (MOB-04).")
    return notes

def telemetry_errors(product):
    """ROLL-01: telemetry and alerts run on practice/demo data first, then on real installations."""
    tel = product.get("telemetry")
    if tel is None:
        return []
    if not isinstance(tel, dict) or set(tel) - {"rollout", "practice_evidence"}:
        return ["telemetry must be {rollout, practice_evidence}"]
    if tel.get("rollout") not in {"off", "practice", "installations"}:
        return ["telemetry.rollout must be off, practice or installations"]
    proof = tel.get("practice_evidence", "")
    if tel["rollout"] == "installations" and (not isinstance(proof, str) or not proof.strip()
                                             or proof.strip().upper().startswith(("PENDING", "TODO", "UNKNOWN"))):
        return ["ROLL-01: telemetry.rollout installations needs practice_evidence (checked on demo/practice data first)"]
    return []

def valid_product(product, release=False):
    errors = []
    if not isinstance(product, dict):
        return ["Product must be a JSON object"], []
    for k in REQUIRED:
        if k not in product:
            errors.append("Missing required field: " + k)
    if errors:
        return errors, []
    if product["schema_version"] not in SCHEMA_VERSIONS:
        errors.append("Unsupported schema_version (expected 1.0 or 1.1)")
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
    link = connectivity(product) if product["deployment"] in MODES else None
    tier = link.get("tier") if isinstance(link, dict) else None
    if product["deployment"] in MODES and method == "cloud_entitlement" and tier not in CLOUD_TIERS:
        errors.append("Cloud entitlement for offline/LAN requires the cloud_sync tier (ADR-0001)")
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
    errors.extend(connectivity_errors(product))
    errors.extend(telemetry_errors(product))
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
        if tier in CLOUD_TIERS and str(product["data"].get("residency", "")).upper().startswith(("TODO", "PENDING", "UNKNOWN")):
            errors.append("Release needs a decided hosting region (data.residency)")
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
    tier = getattr(args, "tier", None) or DEFAULT_TIER[args.mode]
    clients = getattr(args, "clients", None) or ",".join(DEFAULT_CLIENTS[args.mode])
    link = {"tier": tier, "sites": getattr(args, "sites", None) or "single",
            "clients": [c.strip() for c in clients.split(",") if c.strip()],
            "multi_owner": bool(getattr(args, "multi_owner", False))}
    if tier == "cloud_sync":
        link["offline_grace_days"] = 7
    cloud = tier in CLOUD_TIERS
    record = {
        "schema_version": "1.1", "id": args.id, "name": args.name,
        "deployment": args.mode, "connectivity": link, "markets": [args.market],
        "buyer": "TODO: real paying customer and their roles",
        "problem": "TODO: current customer pain and economic cost",
        "core_journey": "TODO: one buyer journey from initial input to accepted output",
        "monetization": {"model": "subscription",
                         "entitlement_method": "cloud_entitlement" if cloud else "manual_contract",
                         "expiry_data_access": "read_export_backup"},
        "data": {"sensitivity": "personal", "has_financial_ledger": False,
                 "has_personal_data": True, "backup_restore_plan": "TODO: restore on a separate clean device",
                 **({"residency": "TODO: hosting region decided by owner"} if cloud else {})},
        "addons": {"ai_agents": False, "regulated_overlay": False},
        "stage": "research", "competitors": [],
        "acceptance": ["TODO: actual person completes one workflow and recovery"],
        "evidence": {k: "PENDING" for k in EVIDENCE},
        "control_evidence": {}, "features": [], "exclusions": []
    }
    errors = connectivity_errors(record)
    if errors:
        raise ValueError("; ".join(errors))
    target = Path(args.output)
    target.parent.mkdir(parents=True, exist_ok=True)
    with target.open("x", encoding="utf-8") as f:
        json.dump(record, f, ensure_ascii=False, indent=2)
        f.write("\n")
    return target

def guide_check(args):
    """Run the af-guide checker from the factory checkout (same rules the product runs in its own tests)."""
    sys.path.insert(0, str(ROOT / "packages" / "af-guide"))
    import af_guide
    cat, texts = af_guide.load_dir(args.folder)
    found = af_guide.check(cat, texts, ui=af_guide._ui_files(args.ui) if args.ui else None,
                           access=load(args.access) if args.access else None,
                           error_codes=load(args.errors) if args.errors else None, release=args.release)
    for f in found:
        print(f)
    bad = [f for f in found if f.level == "error"]
    print(f"GUIDE {'NO-GO' if bad else 'OK'}: {len(cat.get('guides', []))} guides, {len(cat.get('roles', []))} roles, "
          f"{len(cat.get('problems', []))} problems, {len(bad)} errors, {len(found) - len(bad)} warnings")
    return 1 if bad else 0

def main(argv=None):
    parser = argparse.ArgumentParser(description="Apps Factory manifest and evidence gate (NOT production app generator)")
    sub = parser.add_subparsers(dest="action", required=True)
    new = sub.add_parser("new", help="Create a clearly incomplete product spec, never overwrite")
    new.add_argument("--id", required=True)
    new.add_argument("--name", required=True)
    new.add_argument("--mode", required=True, choices=sorted(MODES))
    new.add_argument("--market", required=True, choices=sorted(MARKETS))
    new.add_argument("--tier", choices=sorted(TIERS), help="Default: standalone/office_server/cloud_only by mode")
    new.add_argument("--sites", choices=["single", "multi"], default="single")
    new.add_argument("--clients", help="Comma list of windows_desktop,browser,mobile_pwa")
    new.add_argument("--multi-owner", action="store_true")
    new.add_argument("--output", required=True)
    check = sub.add_parser("check", help="Validate candidate; --release forces evidence gates")
    check.add_argument("product")
    check.add_argument("--release", action="store_true")
    sub.add_parser("doctor", help="Read catalog and schema and check consistency")
    sub.add_parser("controls", help="List standard control IDs")
    prompt = sub.add_parser("prompt", help="Print safe agent starting prompt for a product manifest")
    prompt.add_argument("product")
    guide = sub.add_parser("guide", help="Check a product's guide folder with packages/af-guide (HELP-07..12)")
    guide.add_argument("folder", help="Folder with catalogue.json and <lang>.json")
    guide.add_argument("--ui", action="append", default=[], help="UI dictionary JSON per language (ui-ar.json, ui-en.json)")
    guide.add_argument("--access", help="af-access permission catalogue JSON")
    guide.add_argument("--errors", help="JSON list of every error code the server can return")
    guide.add_argument("--release", action="store_true", help="Style warnings become errors (HELP-11)")
    args = parser.parse_args(argv)
    try:
        if args.action == "guide":
            return guide_check(args)
        if args.action == "doctor":
            controls = catalog()
            schema = load(ROOT / "factory" / "product.schema.json")
            ids = [x["id"] for x in controls]
            if not schema.get("required") or not {"desktop", "lan", "saas"}.issubset(set(schema["properties"]["deployment"]["enum"])):
                raise ValueError("Missing product schema requirements")
            if set(schema["properties"]["connectivity"]["properties"]["tier"]["enum"]) != TIERS:
                raise ValueError("Schema connectivity tiers differ from factory.py")
            unknown = {p for c in controls for p in c["profiles"]} - PROFILES
            if unknown:
                raise ValueError("Controls use unknown profiles: " + ", ".join(sorted(unknown)))
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
                  f"{product['name']} ({product['deployment']}, tier {connectivity(product)['tier']}, "
                  f"{','.join(product['markets'])}); read docs/CONNECTIVITY_AND_SYNC.md for the tier rules; "
                  "reuse verified platform components without rewriting existing products. "
                  "Never hardcode demo credentials in production. "
                  "Show exact tests, skipped checks, release limitations and required customer acceptance.")
            return 0
        print(f"PRODUCT: {product.get('id', '?')} | applicable controls: {len(selected)}")
        if errors:
            for e in errors:
                print("NO-GO:", e)
            return 2
        print("TIER:", connectivity(product)["tier"], "| PROFILES:", ",".join(sorted(profiles(product))))
        for note in advisories(product):
            print("ADVISORY:", note)
        print("SPEC VALID. Not a certification, security audit, completed codebase or selling approval.")
        return 0
    except (ValueError, OSError, KeyError, TypeError, AssertionError, json.JSONDecodeError) as error:
        print("ERROR:", error, file=sys.stderr)
        return 2

if __name__ == "__main__":
    sys.exit(main())
