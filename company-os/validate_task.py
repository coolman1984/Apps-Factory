"""Fail-closed, offline validator for Pixel Plus cross-session task handoffs.

Supports precisely the JSON Schema keywords used by task.schema.json. This is
not a full JSON Schema library, and task metadata never authenticates actions.
Run: python3 company-os/validate_task.py company-os/examples.json [more.json ...] [--stale-hours 24]
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

# A handoff may never PRE-GRANT an action that spends money, reaches customers, touches production or real data, or handles secrets:
# such an action belongs in requires_owner_approval (fail closed). Words, not substrings: «payload» is not «pay».
SENSITIVE_WORDS = {
    "pay", "payment", "payments", "charge", "refund", "invoice", "spend", "purchase", "transfer", "wire",
    "send", "message", "broadcast", "email", "sms", "whatsapp", "telegram", "post", "tweet", "announce",
    "deploy", "publish", "release", "merge", "force", "production", "prod", "live",
    "delete", "drop", "wipe", "purge", "truncate", "destroy",
    "secret", "secrets", "credential", "credentials", "password", "passwords", "token", "tokens", "signing", "private",
}
# Real customer data and reaching customers: sensitive unless the action says it is synthetic («read_synthetic_data» is fine, «read_customer_data» is not).
DATA_WORDS = {"customer", "customers", "client", "clients", "data", "record", "records", "personal", "real", "pii", "database", "db", "backup", "backups"}
OUTREACH_WORDS = {"contact", "call", "upload", "export", "share", "notify", "submit", "phone", "dm", "reply"}
WRITE_WORDS = {"push", "write", "commit", "edit", "update", "change", "modify"}
FAILED_TESTS = re.compile(r"(?<![\d.])[1-9]\d*\s*(?:failed|failures?|errors?|skipped|xfail)\b|(?-i:\b(?:FAILED|FAILURE|ERROR)\b)|\bnot\s+(?:green|passing|passed)\b|\bred\b", re.I)
ACTIVE = {"ready", "working", "review", "owner_gate"}  # statuses in which a person or agent is expected to be doing the task


def _words(action):
    return set(re.findall(r"[a-z0-9]+", action.casefold()))


def sensitive_actions(allowed):
    """The entries of allowed_actions that a handoff is not allowed to grant by itself."""
    found = []
    for action in allowed:
        if not isinstance(action, str):
            continue
        words = _words(action)
        if (words & SENSITIVE_WORDS or ("main" in words and words & WRITE_WORDS)
                or ((words & DATA_WORDS or words & OUTREACH_WORDS) and "synthetic" not in words)):
            found.append(action)
    return found


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
        if "pattern" in rule:
            pattern = rule["pattern"]
            # Anchored exact patterns use full matching; substring patterns use search.
            exact = pattern.startswith("^") and (pattern.endswith("$") or pattern.endswith(r"$(?![\s\S])"))
            match = re.fullmatch(pattern, value) if exact else re.search(pattern, value)
            if match is None:
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

        if isinstance(allowed, list):
            for action in sensitive_actions(allowed):
                errors.append(f"$.allowed_actions: {action!r} is sensitive (money, customers, production, real data, secrets, main): "
                              "list it in requires_owner_approval, a handoff cannot grant it")

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
                    if re.search(r"[A-Za-z0-9]", item["reference"]) is None:
                        errors.append(f"$.evidence[{index}].reference: needs a readable artifact identifier")
        if task.get("status") == "done" and isinstance(evidence, list) and not any(
            isinstance(e, dict) and isinstance(e.get("verified_at"), str)
            for e in evidence
        ):
            errors.append("$.evidence: completed tasks need dated verification")
        if task.get("status") == "done":
            # A task whose tests failed or were skipped, or that still lists an error, is not done: the merge it leads to must wait.
            if isinstance(task.get("known_errors"), list) and task["known_errors"]:
                errors.append("$.known_errors: a completed task cannot still list known errors")
            if isinstance(task.get("tests_skipped"), list) and task["tests_skipped"]:
                errors.append("$.tests_skipped: skipped tests are not green, a completed task cannot list any")
            if task.get("current_commit") and isinstance(task.get("tests_run"), list) and not task["tests_run"]:
                errors.append("$.tests_run: a completed task with code (current_commit) must list the tests that were run on it")
            for line in task.get("tests_run") if isinstance(task.get("tests_run"), list) else []:
                if isinstance(line, str) and FAILED_TESTS.search(line):  # a description is free text: a recorded failure or skip is never read as green
                    errors.append(f"$.tests_run: {line!r} records a failure or a skip; a completed task needs a clean run")
    return errors


def batch_conflicts(tasks):
    """Work that would be done twice: the same id in two handoffs, or two ACTIVE tasks on the same branch or the same open PR."""
    problems, ids, branches, prs = [], {}, {}, {}  # a branch name is only unique inside its project (Factory and Store may both have fix/x)
    for index, task in enumerate(tasks):
        if not isinstance(task, dict):
            continue
        name = task.get("task_id") if isinstance(task.get("task_id"), str) else f"#{index + 1}"
        key = name.strip()
        if key in ids:
            problems.append(f"{name}: duplicate task identifier (also {ids[key]})")
        ids.setdefault(key, name)
        if task.get("status") not in ACTIVE:
            continue
        branch = task.get("branch")
        if isinstance(branch, str) and branch.strip():
            bkey = (str(task.get("project", "")).strip().casefold(), branch.strip())
            if bkey in branches:
                problems.append(f"{name}: branch {branch!r} of {task.get('project')} is already being worked on by {branches[bkey]}")
            branches.setdefault(bkey, name)
        for url in task.get("open_prs") or []:
            if isinstance(url, str):
                if url.strip() in prs:
                    problems.append(f"{name}: pull request {url} is already carried by {prs[url.strip()]}")
                prs.setdefault(url.strip(), name)
    return problems


def stale_tasks(tasks, now, hours):
    """`working` tasks nobody has touched for `hours` (or that never said when): the work was interrupted, someone else takes over from
    next_action, current_commit and the open PRs in the handoff."""
    stale = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("status") != "working":
            continue
        stamp = task.get("updated_at")
        try:
            at = datetime.fromisoformat(stamp.replace("Z", "+00:00")) if isinstance(stamp, str) else None
        except ValueError:
            at = None
        if at is None or at.tzinfo is None or (now - at).total_seconds() > hours * 3600:
            stale.append(task.get("task_id") or "?")
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate Pixel Plus AI task handoffs locally, without network access")
    parser.add_argument("file", type=Path, nargs="+", help="JSON task or JSON array of tasks; several files are checked together for duplicated work")
    parser.add_argument("--stale-hours", type=float, default=None, help="report `working` tasks not updated for this long (interrupted work); exit 3 if any")
    parser.add_argument("--now", default=None, help="RFC 3339 time to measure staleness from (default: the clock)")
    args = parser.parse_args(argv)
    tasks, sources = [], []
    try:
        schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
        for path in args.file:
            data = json.loads(path.read_text(encoding="utf-8"))
            for task in data if isinstance(data, list) else [data]:
                tasks.append(task)
                sources.append(path.name)
    except (OSError, UnicodeError, json.JSONDecodeError) as ex:
        print(f"Cannot read task/schema JSON: {ex}", file=sys.stderr)
        return 2
    if not tasks:
        print("No tasks supplied", file=sys.stderr)
        return 1
    failed = False
    seen_ids = set()
    for idx, task in enumerate(tasks):
        issues = validate_task(task, schema)
        if isinstance(task, dict) and isinstance(task.get("task_id"), str):
            task_id = task["task_id"].strip()  # compare canonical IDs, even when invalid input has trailing whitespace
            if task_id in seen_ids:
                issues.append("$.task_id: duplicate task identifier in the handoff batch")
            seen_ids.add(task_id)
        if issues:
            failed = True
            print(f"Task {idx + 1}: INVALID")
            for issue in issues:
                print("  " + issue)
        else:
            print(f"Task {idx + 1}: valid handoff metadata (NOT an authorization)")
    for problem in batch_conflicts(tasks):
        if "duplicate task identifier" in problem:
            continue  # already reported per task above
        failed = True
        print("CONFLICT: " + problem)
    if failed:
        return 1
    if args.stale_hours is not None:
        try:
            now = datetime.fromisoformat(args.now.replace("Z", "+00:00")) if args.now else datetime.now().astimezone()
            if now.tzinfo is None or now.utcoffset() is None:
                raise ValueError("timezone required")
        except ValueError:
            print("--now must be an RFC 3339 time with a timezone", file=sys.stderr)
            return 2
        stale = stale_tasks(tasks, now, args.stale_hours)
        for task_id in stale:
            print(f"STALE: {task_id} is `working` but was not updated for {args.stale_hours:g} hours: take it over from its next_action and current_commit")
        if stale:
            return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
