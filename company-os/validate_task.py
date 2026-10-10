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

# What a handoff MAY grant by itself: a short allowlist of actions that touch nothing real. Anything else is refused (fail closed): a word
# list can never be complete (the review of PR #42 found customer, licence, export... in turn). An action that touches money, customers,
# licences, production, real data or secrets is never on this list: it goes in requires_owner_approval. To grant a new kind of harmless
# action, add it here in a reviewed change.
SAFE_ACTIONS = {
    "read_repo", "read_docs", "read_ci_logs", "research_public",
    "run_synthetic_tests", "run_unit_tests", "run_tests", "run_linter", "write_tests", "review_diff",
    "edit_files", "write_code", "create_branch", "commit_changes", "push_branch", "open_pr", "comment_on_pr",
    "draft_report", "draft_copy", "draft_docs",
}
# tests_run is free text, so «green» is read from what the line says: a pass with a count above zero, and no failure, error, skip, abort,
# timeout or non-zero exit once zero counts («0 failed», «failed: 0», TAP «# fail 0») are set aside.
_LABEL = r"(?:fail(?:ed|ing|ures?)?|errors?|errored|skipp?(?:ed|s|ing)?|xfail\w*)"
ZERO_COUNT = re.compile(rf"\b(?:0|no|zero)\s+{_LABEL}\b|\b{_LABEL}\s*[:=]\s*0\b|(?m:^\s*#\s*{_LABEL}\s+0\b)", re.I)
FAILURE_FORMS = re.compile(rf"(?<![\d.])[1-9]\d*\s*{_LABEL}\b|\b{_LABEL}\s*[:=#]?\s*[1-9]\d*\b|\b(?:failed|failing|failures?|errored|aborted|crash\w*|timed?[\s-]*out|timeout)\b"
                           r"|(?<![-/_.\w])(?:fails?|errors?|skipp?(?:ed|s|ing)?)\b(?![-/_.]\w)(?!\s+[a-z])|(?-i:\b(?:FAIL|FAILED|ERROR)\b)|\bred\b|\bnot\s+(?:green|passing|passed)\b|\bexit(?:ed)?(?:\s+with)?(?:\s+(?:code|status))?\s+[1-9]", re.I)
PASS_EVIDENCE = re.compile(r"(?<![\d.])[1-9]\d*\s*(?:tests?\s+)?pass(?:ed|es|ing)?\b|\bpass(?:ed|es|ing)?\s*[:=#]?\s*[1-9]\d*|\b(?:green|succeeded|success|all\s+(?:tests\s+)?pass(?:ed|ing)?)\b|(?-i:\bOK\b)", re.I)
ACTIVE = {"ready", "working", "review", "owner_gate"}  # statuses in which a person or agent is expected to be doing the task


def _parse_time(stamp):
    """An RFC 3339 time with a zone, or None. Fractions of any length and «Z» are read the same on every Python (before 3.11 only 3 or 6 digits parsed)."""
    if not isinstance(stamp, str):
        return None
    text = re.sub(r"\.(\d+)", lambda m: "." + (m.group(1) + "000000")[:6], stamp.replace("Z", "+00:00"), count=1)
    try:
        at = datetime.fromisoformat(text)
    except (ValueError, OverflowError):
        return None
    return at if at.tzinfo is not None and at.utcoffset() is not None else None


def unlisted_actions(allowed):
    """The entries of allowed_actions that are not on SAFE_ACTIONS (spaces and case are ignored, like for approvals)."""
    return [a for a in allowed if isinstance(a, str) and " ".join(a.split()).casefold() not in SAFE_ACTIONS]


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
                if _parse_time(value) is None:
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
            for action in unlisted_actions(allowed):
                errors.append(f"$.allowed_actions: {action!r} is not on the allowlist ({', '.join(sorted(SAFE_ACTIONS))}): anything that touches money, customers, "
                              "licences, production, real data or secrets goes in requires_owner_approval; a harmless new kind of action is added to SAFE_ACTIONS in a reviewed change")

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
                if isinstance(line, str):  # free text: green needs a stated pass and no failure, error, skip or non-zero exit in any form
                    rest = ZERO_COUNT.sub("", line)
                    if FAILURE_FORMS.search(rest):
                        errors.append(f"$.tests_run: {line!r} records a failure or a skip; a completed task needs a clean run")
                    elif not PASS_EVIDENCE.search(line):
                        errors.append(f"$.tests_run: {line!r} does not say the tests passed (write the result, for example '113 passed, 0 failed')")
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
    """`working` tasks nobody has touched for `hours`, or that never said when, or whose stamp lies in the future (a typo or a wrong clock
    cannot make work look fresh for ever): the work was interrupted, someone else takes over from next_action, current_commit and the open PRs."""
    stale = []
    for task in tasks:
        if not isinstance(task, dict) or task.get("status") != "working":
            continue
        at = _parse_time(task.get("updated_at"))
        age = (now - at).total_seconds() if at is not None else None
        if age is None or age < -300 or age > hours * 3600:
            stale.append(task.get("task_id") or "?")
    return stale


def main(argv=None):
    parser = argparse.ArgumentParser(description="Validate Pixel Plus AI task handoffs locally, without network access")
    parser.add_argument("file", type=Path, nargs="+", help="JSON task or JSON array of tasks; several files are checked together for duplicated work")
    parser.add_argument("--stale-hours", type=float, default=None, help="report `working` tasks not updated for this long (interrupted work); exit 3 if any")
    parser.add_argument("--now", default=None, help="RFC 3339 time to measure staleness from (default: the clock)")
    args = parser.parse_args(argv)
    tasks = []
    try:
        schema = json.loads(DEFAULT_SCHEMA.read_text(encoding="utf-8"))
        for path in args.file:
            data = json.loads(path.read_text(encoding="utf-8"))
            for task in data if isinstance(data, list) else [data]:
                tasks.append(task)
    except (OSError, UnicodeError, json.JSONDecodeError) as ex:
        print(f"Cannot read task/schema JSON: {ex}", file=sys.stderr)
        return 2
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
    for problem in batch_conflicts(tasks):  # the one place that knows «the same work twice»: an id, a branch or a pull request
        failed = True
        print("CONFLICT: " + problem)
    stale = []
    if args.stale_hours is not None:  # reported even when something else is wrong: a messy batch is when the takeover signal is needed most
        now = _parse_time(args.now) if args.now else datetime.now().astimezone()
        if now is None:
            print("--now must be an RFC 3339 time with a timezone", file=sys.stderr)
            return 2
        stale = stale_tasks(tasks, now, args.stale_hours)
        for task_id in stale:
            print(f"STALE: {task_id} is `working` but was not updated for {args.stale_hours:g} hours: take it over from its next_action and current_commit")
    if failed:
        return 1
    return 3 if stale else 0


if __name__ == "__main__":
    raise SystemExit(main())
