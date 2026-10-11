# ManimGX official 3D/motion reference | مرجع الرسوم المتحركة
Verified 2026-10-11 against:
- Official repository: https://github.com/academa-labs/manimgx
- Official docs: https://manimgx.academa.ai/
- Agent-facing official docs index: https://manimgx.academa.ai/llms.txt
- Distribution metadata: https://pypi.org/project/manimgx/
- Examples: https://manimgx.academa.ai/gallery/
- Rendering / inspect: https://manimgx.academa.ai/user-guide/rendering/
- Changelog: https://manimgx.academa.ai/changelog/

## Mandatory for every agent
Read this reference at task intake, and **decide explicitly** whether its precise 2D/3D animations, math/science visualizations, camera motion, plots or pre-rendered video can genuinely improve the customer outcome. For relevant creative/3D/video/scientific/marketing tasks, check the **current official stable docs/release**, compatibility, license and examples before implementing; perform an isolated proof if proposing adoption. For ordinary tables, forms and accounting flows, record `not applicable`; **do not install** for unrelated work.

## Capabilities verified from official README
- Python scene API designed for compatibility with many Manim Community Edition scripts; API coverage and differences must be checked, not presumed identical.
- Rust + wgpu GPU-based renderer; 2D/3D shapes, cameras, scientific charts and typography; export to MP4.
- Browser integration documented by the project, with `npm` package, Python run by Pyodide and WebGPU where supported.
- `manimgx inspect` allows storyboard/layout feedback. Explore if it helps visual QA. Animations can be synchronized with speech using documented scene methods.
- The reported ~90.6x speed relative to ManimCE was measured by maintainers on **specific scenes/hardware**. It is **not** a general performance guarantee; benchmark relevant scene and target hardware.

## Important production constraints
1. **Python requirement: >=3.13** per official installation/package metadata checked on 2026-10-11. Existing factory portable Windows Python 3.12 must not be overwritten or presumed compatible; a separate isolated runtime would be required and must be tested.
2. **Commercial licensing:** project code claims MIT, but PyPI and upstream state bundled native wheels with x264 are **GPL-3.0-or-later as a whole**. Other components, fonts, decoder and video distribution have separate conditions. Legal/license review is required before bundling the runtime into a commercial/offline desktop product. Prefer pre-rendered assets only if their individual rights/attribution are cleared.
3. **Performance and fallback:** WebGPU is not universal; test browser/GPU support, fallback still image/video, low-power mobile and reduced-motion access. Don't force continuous 3D on ERP/clinic workflow pages.
4. **Security/privacy:** no customer/medical/personal data in example scenes, screenshots, logs, cloud demos or voice services. Sandbox external assets, verify dependency provenance and avoid copying unreviewed agent prompts.
5. **Architecture:** use existing Factory creative primitives for ordinary motion; consider ManimGX only when meaningful precise explanatory 2D/3D or pre-rendered content justifies its cost. Keep film assembly in the owner Animation Studio rather than duplicate the whole pipeline.

## Practical routing
| Task | Best-fit approach |
|---|---|
| Medical clinic dashboard | Fast accessible HTML, CSS, native motion; optional **pre-rendered** explanatory animations in a separate module, not background on patient records |
| Product marketing or professional demo | Storyboard -> ManimGX isolated scene (if licensed) -> verified MP4 -> owner Animation Studio compositing -> QA |
| Mathematics, trends, KPI teaching | Candidate for plots, labelled shapes and camera scenes if intelligibility beats simple chart |
| 3D engineering/warehouse | Use owner 3D-Modeling for interactive operational geometry; ManimGX may make explanatory clips, not replace the working 3D app |
| Mobile / offline deployment | Static/poster/video fallback first, ensure installer/build compatibility and rights |

## Acceptance record for relevant use
```text
Task / benefit:
Upstream URL, release/tag/commit, checked date:
Install/runtime (separate env only), licence and external assets:
Approaches compared (native CSS / existing engine / ManimGX):
Scenario with synthetic data:
Render output dimension, fps and actual device measurements:
Visual QA, accessibility, browser/mobile fallback:
Screenshots/frame evidence and tests run:
Decision: adopt / defer / not applicable; why:
```

## Status
**Mandatory evaluation and official-reference check; NOT an approved automatic runtime dependency.** No installation, new bundled binary, production deployment or test pass is claimed here.
