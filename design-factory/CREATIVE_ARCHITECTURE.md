# Creative Factory v2: icons, layers, motion, transitions, 2D/3D, film

This is the **architecture and implementable local preview** for a reusable, offline-first creative system. Pinned references are not preinstalled production dependencies. Keep default Windows/LAN business apps lean.

## One creative factory, six optional capabilities
| Capability | Default | Optional specialist | Typical product |
|---|---|---|---|
| Icons | Lucide selected SVGs (ISC + legacy Feather MIT) | Iconify only with per-pack licence manifest | all |
| Microinteractions | CSS + Web Animations API and reduced-motion fallback | Auto Animate OR Motion | any UI |
| Layout transitions | CSS transform/opacity + View Transitions API progressive enhancement | Motion layout transitions; cross-page scenes optional | admin / website |
| Layered story / parallax | original CSS 3D transforms with bounded pointer input, optional scroll progress | Motion + Lenis, one scroll orchestrator | marketing landing |
| 2D/3D scenes | image/CSS shape first, hard CPU/GPU budget | Pixi / Three.js; React Three Fiber if React | product visualization |
| Explainers and film | Existing Animation Studio deterministic spec pipeline | Motion Canvas; Lottie/dotLottie/Rive for playback | launch film |
| Presentation motion | Existing Slide Forge JSON engine | Film engine for exports, if accepted | management slides |

## Runtime and cost tiers
1. `essential`: reference CSS and native DOM/WAAPI only. Zero npm/runtime, works on offline Windows. Required default.
2. `polished`: icon set + one selected animation library (Motion OR Auto Animate), plus one bundled vector player if actually needed.
3. `cinematic`: scroll choreography, layered image/3D, external assets, progressive loading and mobile fallback.
4. `film`: build-time toolchain, Puppeteer/Playwright Chrome, FFmpeg, audio, timeline and deterministic renders. **Do not ship this engine inside ordinary Windows customers' installers**.

### "Layers like video" explained
A browser can create perceived depth with multiple independently moving HTML/SVG/canvas layers: background, midground, subject, cards and foreground light. Move with `translate3d` and limited perspective, mask/clipping and opacity, and drive by mouse, scroll or a deterministic scene clock. Video-like quality comes from **art direction + motion grammar + timing**, not from installing every animation framework. Real video and image textures are optional assets, with copyrights and fallback.

## Original scene contract
```json
{
  "version": "1.0",
  "id": "editorial-depth",
  "profile": "cinematic",
  "layers": [
    {"id":"background","kind":"css","depth":0.1},
    {"id":"subject","kind":"dom","depth":0.5},
    {"id":"foreground","kind":"dom","depth":1}
  ],
  "camera":{"intensity":0.65,"max_px":26},
  "timeline":{"duration_ms":6000,"loop":true},
  "motion_policy":{"respect_reduced_motion":true,"use_transform_opacity_only":true},
  "fallback":{"type":"static","same_content":true}
}
```
See `creative-recipes/` for checked authoring examples and `creative-lab/` for an original rendered scene. Source video adapters are **not** the same interface as real-time web motion; map through explicit export tasks and fps/canvas profiles.

## Ownership and integration
- `Apps-Factory` owns design brief, icons vocabulary, semantic tokens, recipes, scene policy, tests, and optional adapter contracts.
- `Animation` owns the film maker; keep its validated renderer/source code in its source repository. Do not clone internal modules into apps.
- `The-Slide-Show` owns JSON slide engine.
- `promo-video-generator` remains a reference pipeline with its licence/origin verified before redistribution.
- Third-party upstreams are exact pinned Git submodules and must pass licence/performance/compatibility checks. No blanket licence of Lottie/Rive assets or Iconify packs.
- Each business app opts into a profile and installs only selected proven artifacts.

## Integration example in a Python+HTML Windows app
```html
<link rel="stylesheet" href="/design-system/af-tokens.css">
<link rel="stylesheet" href="/design-system/af-components.css">
<link rel="stylesheet" href="/creative/creative-effects.css">
<script type="module" src="/creative/scene-player.js"></script>
```
Actual paths depend on the app's static router. The original creative-lab runtime is a demo, not a production security/auth or backend replacement.

## Budget and failure behaviors
- Target responsive 60 fps when feasible, never guarantee it. Prefer opacity/transform over layout-affecting left/top/width animation.
- No autoplay flash in reduced-motion mode; preserve meaning even when motion disabled.
- Test 320px narrow phone, slow CPU, RTL, keyboard, scrolling, screen reader labels, landscape and orientation.
- Pause animations when document becomes hidden; handle missing WebGL/context-loss if optional 3D activated.
- No scroll hijacking on forms, data tables, or operating dashboards; no major content below the fold inaccessible without motion.
- Color/texture/particles cannot be a prerequisite for finding buttons, reading numbers or performing tasks.
- CI test includes no network, scenario determinism, pause, reduced-motion, viewport overflow, export.
