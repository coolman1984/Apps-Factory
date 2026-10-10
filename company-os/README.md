# Pixel Plus Company OS: pilot contracts

**Today:** documentation, owner/agent policy and structured JSON handoffs only. This GitHub directory does **not** run a model, dispatch autonomous tasks, read real customer databases or authorize external actions.

- [Deep research and architecture](../docs/PIXEL_PLUS_ONE_PERSON_COMPANY_OS.md)
- [Daily operating playbook](../docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md)
- [Task contract](task.schema.json) and [two safe example handoffs](examples.json)
- **Validate all handoffs offline:** `python3 company-os/validate_task.py company-os/examples.json`; exit code 1 means INVALID. Use this on every imported task, including from another Claude/Codex account. Nothing is sent outside your PC.
- **Canon:** `backlog → ready → working → review → owner_gate → done`, or `blocked`; `owner_gate` records a requested approval only.
- **Mandatory:** actual document/source reference, nonblank independent reviewer and assignee, complete cross-account context (`branch`, `current_commit`, `open_prs`, `known_errors`, `tests_run`, `tests_skipped`, `next_action`), one dated verified evidence artifact before `done` and a named pending approval when in `owner_gate`. `null` is allowed for branch/commit when no code exists; empty lists are honest when there are no PRs/tests. All timestamps use the same explicit RFC-3339-like timezone-qualified syntax in the JSON schema and local validator. A metadata validation is **not** proof that an external URL or customer acceptance is authentic.
- Tested in factory CI: `python3 -m unittest discover -s tests -v`, which exercises positive and negative examples and the validator, not just two happy-path fixtures.

The offline validator also checks that repository-local decision files exist, rejects contradictory approval/allowed-action lists, and rejects punctuation-only evidence/approval identifiers. External HTTPS references are syntax-checked only, not fetched or independently verified. **Valid metadata is not verified evidence and is never authorization.**

An independently developed **local-only Python/SQLite prototype** has been run separately with seven tests, and can be used for a dry run. It is **not committed here**, not connected to outside services and not suitable as production owner authentication. The next narrowly scoped engineering PR should vendor it, test on Windows, and add **read-only GitHub status** before discussing cloud hosting or agent auto-dispatch.

## What is only written, what the validator enforces, and what is switched on
| Rule | Only written (docs, owner policy) | Enforced offline by `validate_task.py` and tested | Running autonomously today |
|---|---|---|---|
| Hand a task to another session or account | the playbook | every field of the handoff, strictly typed; `decision_ref` must exist | **No.** A person pastes the file |
| Independent review | the playbook | reviewer is not the assignee (case and spaces ignored); a done task needs dated evidence | **No** reviewer agent runs; the name is metadata, not an identity |
| Do not repeat work | the playbook | the same id twice, two active tasks on one branch or one open PR, over **several files at once** (`validate_task.py a.json b.json`) | **No** registry or dispatcher |
| Do not call it done when tests are not green | the playbook | a `done` task cannot list known errors or skipped tests, and one with code must list the tests run on its commit | **No.** The merge itself is held back only by GitHub branch protection and the required checks (see the repository settings) |
| Recover after an interruption | `next_action`, `current_commit`, `open_prs` in the handoff | `--stale-hours 24` lists `working` tasks that were not touched (optional `updated_at`) and exits 3, so another session can take over | **No** watcher |
| No money, customers, production, real data or secrets without the owner | `requires_owner_approval` | a handoff can never pre-grant such an action in `allowed_actions` (words like pay, send, deploy, merge, delete, secret, production; push to main); `owner_gate` needs a named pending approval | **No agent can act**, so there is nothing to block yet; the real enforcement must sit in the future integration (authenticated owner approval) |

Exit codes: 0 valid, 1 invalid or in conflict, 2 unreadable, 3 valid but interrupted work was found.

No new product factory release claims follow from this directory. All sensitive actions require owner approval *and* separate authenticated enforcement in the eventual integration.
