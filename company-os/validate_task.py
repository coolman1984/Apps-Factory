"""Fail-closed, offline validator for Pixel Plus cross-session task handoffs.

Supports precisely the JSON Schema keywords used by task.schema.json. This is
not a full JSON Schema library, and task metadata never authenticates actions.
Run: python3 company-os/validate_task.py company-os/examples.json
"""
import argparse
from datetime import datetime
import json
import math
from pathlib import Path
import re
import sys

HERE = Path(__file__).resolve().parent
DEFAULT_SCHEMA = HERE / "task.schema.json"


def _matches_type(value, kind):
    if kind == "object":
        return isinstance(value, dict)
    if kind == "array":
        return isinstance(value, list)
    if kind == "string":
        return isinstance(value, str)
    if kind == "null":
        return value is None
    if kind == "integer":
        return type(value) is int
    if kind == "number":
        return type(value) in (int, float) and math.isfinite(value)
    if kind == "boolean":
        return type(value) is bool
    raise ValueError("unsupported JSON Schema type: " + str(kind))


def _check(value, rule, where="$"):
    """Validate the subset of draft 2020-12 used by the checked-in contract."""
    problems = []
    kinds = rule.get("type")
    if kinds is not None:
        kinds = kinds if isinstance(kinds, list) else [kinds]
        if not any(_matches_type(value, kind) for kind in kinds):
            return [f"{where}: expected {' or '.join(kinds)}"]

    if "const" in rule and value != rule["const"]:
        problems.append(f"{where}: unexpected constant")
    if "enum" in rule and value not in rule["enum"]:
        problems.append(f"{where}: not an allowed value")

    if isinstance(value, dict):
        properties = rule.get("properties", {})
        for key in rule.get("required", []):
            if key not in value:
                problems.append(f"{where}.{key}: required")
        for key, item in value.items():
            if key in properties:
                problems.extend(_check(item, properties[key], f"{where}.{key}"))
            elif rule.get("additionalProperties") is False:
                problems.append(f"{where}.{key}: unexpected field")

    if isinstance(value, str):
        if len(value) < rule.get("minLength", 0):
            problems.append(f"{where}: too short")
        if len(value) > rule.get("maxLength", float("inf")):
            problems.append(f"{where}: too long")
        if "pattern" in rule and re.search(rule["pattern"], value) is None:
            problems.append(f"{where}: invalid format")
        if rule.get("format") == "date-time":
            try:
                parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
                if parsed.tzinfo is None or parsed.utcoffset() is None:
                    raise ValueError("timezone required")
            except (ValueError, OverflowError):
                problems.append(f"{where}: invalid timezone-aware date-time")

    if type(value) in (int, float):
        if value < rule.get("minimum", -float("inf")):
            problems.append(f"{where}: below allowed minimum")
        if value > rule.get("maximum", float("inf")):
            problems.append(f"{where}: above allowed maximum")

    if isinstance(value, list):
        if len(value) < rule.get("minItems", 0):
            problems.append(f"{where}: too few items")
        for index, item in enumerate(value):
            if "items" in rule:
                problems.extend(_check(item, rule["items"], f"{where}[{index}]"))
        if rule.get("uniqueItems"):
            if len({json.dumps(item, sort_keys=True, ensure_ascii=False) for item in value}) != len(value):
                problems.append(f"{where}: duplicate items")
        if "contains" in rule and not any(not _check(item, rule["contains"]) for item in value):
            problems.append(f"{where}: no qualifying evidence item")

    if "allOf" in rule:
        for condition in rule["allOf"]:
            problems.extend(_check(value, condition, where))
    if "if" in rule and not _check(value, rule["if"]):
        problems.extend(_check(value, rule.get("then", {}), where))
    return problems


def validate_task(task, schema=None):
    """Return actionable validation errors. Even a valid task is NOT an approval."""
    schema = schema or json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    errors = _check(task, schema)
    if isinstance(task, dict):
        actor = task.get("assignee")
        reviewer = task.get("reviewer")
        # Whitespace-only actor names are NOT identities; comparisons are case/space-insensitive.
        normalize = lambda value: " ".join(value.split()).casefold()
        for field in ("assignee", "reviewer"):
            candidate = task.get(field)
            if isinstance(candidate, str) and not normalize(candidate):
                errors.append(f"$.{field}: blank actor identity")
        if isinstance(actor, str) and isinstance(reviewer, str):
            if normalize(actor) and normalize(actor) == normalize(reviewer):
                errors.append("$.reviewer: independent reviewer must differ from assignee")
        if task.get("status") == "owner_gate" and isinstance(task.get("requires_owner_approval"), list) and not task["requires_owner_approval"]:
            errors.append("$.requires_owner_approval: owner_gate must identify the requested approval")

        # A task must not grant a capability that it still requires owner approval for.
        allowed = task.get("allowed_actions")
        approvals = task.get("requires_owner_approval")
        if isinstance(allowed, list) and isinstance(approvals, list):
            overlap = {normalize(v) for v in allowed if isinstance(v, str)} & {normalize(v) for v in approvals if isinstance(v, str)}
            if overlap:
                errors.append("$.allowed_actions: must not overlap requires_owner_approval: " + ", ".join(sorted(overlap)))

        # A syntactically valid local path that does not exist cannot restore context.
        # Keep the whole validator offline; HTTPS references must be checked separately.
        ref = task.get("decision_ref")
        if isinstance(ref, str) and (ref.startswith("docs/") or ref == "DECISIONS.md"):
            root = HERE.parent.resolve()
            target = (root / ref).resolve()
            try:
                target.relative_to(root)
            except ValueError:
                errors.append("$.decision_ref: path escapes the repository")
            else:
                if not target.is_file():
                    errors.append("$.decision_ref: referenced local decision file does not exist")

        # Raw minLength counts padding; enforce real content in both runtime and schema.
        for field, minimum in (("goal", 10), ("next_action", 8)):
            value = task.get(field)
            if isinstance(value, str) and len("".join(value.split())) < minimum:
                errors.append(f"$.{field}: must contain at least {minimum} non-whitespace characters")

        evidence = task.get("evidence")
        if isinstance(evidence, list):
            for index, item in enumerate(evidence):
                if isinstance(item, dict) and isinstance(item.get("reference"), str):
                    if len("".join(item["reference"].split())) < 6:
                        errors.append(f"$.evidence[{index}].reference: must contain at least 6 non-whitespace characters")
        if task.get("status") == "done" and isinstance(evidence, list) and not any(
            isinstance(e, dict) and isinstance(e.get("verified_at"), str)
            for e in evidence
        ):
            errors.append("$.evidence: completed tasks need dated verification")
    return errors


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate a Pixel Plus AI task handoff locally, without network access")
    parser.add_argument("file", type=Path, help="single JSON task or JSON array of tasks")
    args = parser.parse_args(argv)
    try:
        data = json.loads(args.file.read_text(encoding="utf-8"))
        schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as ex:
        print(f"Cannot read task/schema JSON: {ex}", file=sys.stderr)
        return 2
    tasks = data if isinstance(data, list) else [data]
    if not tasks:
        print("No tasks supplied", file=sys.stderr)
        return 1
    failed = False
    for idx, task in enumerate(tasks):
        issues = validate_task(task, schema)
        if issues:
            failed = True
            print(f"Task {idx + 1}: INVALID")
            for issue in issues:
                print("  " + issue)
        else:
            print(f"Task {idx + 1}: valid handoff metadata (NOT an authorization)")
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
