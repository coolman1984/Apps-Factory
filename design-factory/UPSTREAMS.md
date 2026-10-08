# Third-party sources, reproducibility & licences • checked 2026-10-08

These are **six Git submodules**, exact gitlink commit SHA pinned in Apps Factory; NOT GitHub forks in the user's account, not duplicated vendored code. `.gitmodules` defines upstream origins. Submodules won't download until explicitly initialized. Recheck latest tags, security advisories and package licenses before production installation.

| Repository | Gitlink ref | Primary use | Licence observations | Deployment policy |
|---|---|---|---|---|
| [UI UX Pro Max](https://github.com/nextlevelbuilder/ui-ux-pro-max-skill) | `1a2c459b35f26116fd165b0a0f30597f252749ff` | Visual-design research prompts/catalog | Root MIT | Dev-only skill; no runtime |
| [Tabler](https://github.com/tabler/tabler) | `c2a7cbf0262d201d97d7b5f9e7cc9ed5a346108e` | HTML/Bootstrap admin UI | Root MIT | Default potential kit for legacy HTML; inspect third-party assets |
| [Anthropic Skills](https://github.com/anthropics/skills) | `683bc88e56f3e09ba94f7055977f3d3aa499f202` | ONLY `skills/frontend-design` | That skill's `LICENSE.txt` Apache 2.0; **other skills in repository may be source-available, not open source** | Agent reference only; do not copy entire repo into products |
| [Vercel Agent Skills](https://github.com/vercel-labs/agent-skills) | `063bee94c3f4df8453406c830b0a7df0f2860278` | `skills/web-design-guidelines` and React guidance when appropriate | No blanket root LICENSE confirmed in snapshot; verify per subfolder and referenced sources before copying | Link/reference only unless licence confirmed |
| [shadcn/ui](https://github.com/shadcn-ui/ui) | `0132174664c07d41262fb51012d0cc782e458e6c` | React route, separate from HTML kit | Root `LICENSE.md` MIT; individual dependencies/assets need checking | ONLY if app already React |
| [Web Awesome](https://github.com/shoelace-style/webawesome) | `e99dc5e26ae63410bd481aa8a686a61ff7158ccd` | Framework-neutral Web Components alternative | Root `LICENSE.md` permissive; **free vs pro distribution/assets need separate assessment** | Choose instead of Tabler, not alongside it |

## Updating pinned upstream safely
1. Read release notes, dependency changes, licence updates, security issues and browser/framework compatibility.
2. Isolated branch: `git submodule update --init design-factory/upstream/<source>`; `git -C design-factory/upstream/<source> fetch`; checkout audited commit/tag.
3. Record change of pinned SHA, licence implications and affected UI-kit compatibility; run design tests and at least two product smoke tests.
4. Submit PR with visual before/after proof. Never float to `main`/latest in builds.

## Physical distribution
- Git submodules are source references, not customer runtime dependencies.
- Third-party notices, required copyrights and attributions must be included when bundling any real upstream source/assets.
- No wholesale copying of source-available office/document skills, paid/pro components, photos, marks or branding.
- Offline Windows deliverables must package audited built assets (where needed), not clone GitHub in production.
- Security review required for npm dependencies and transitive packages; a permissive top-level license is not an all-assets guarantee.
