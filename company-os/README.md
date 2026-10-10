# Pixel Plus Company OS: pilot contracts

**Today:** documentation, owner/agent policy and structured JSON handoffs only. This GitHub directory does **not** run a model, dispatch autonomous tasks, read real customer databases or authorize external actions.

- [Deep research and architecture](../docs/PIXEL_PLUS_ONE_PERSON_COMPANY_OS.md)
- [Daily operating playbook](../docs/PIXEL_PLUS_COMPANY_OS_PLAYBOOK.md)
- [Task contract](task.schema.json) and [two safe example handoffs](examples.json)
- Tested with `python -m unittest discover -s tests -v` (schema presence, handoff shape and no fabricated evidence)

An independently developed **local-only Python/SQLite prototype** has been run separately with seven tests, and can be used for a dry run. It is **not committed here**, not connected to outside services and not suitable as production owner authentication. The next narrowly scoped engineering PR should vendor it, test on Windows, and add **read-only GitHub status** before discussing cloud hosting or agent auto-dispatch.

No new product factory release claims follow from this directory. All sensitive actions require owner approval *and* separate authenticated enforcement in the eventual integration.
