# Creative agent playbook • mandatory for motion/icons/layers/video UI

Read root `AGENTS.md`, `design-factory/AGENTS.md`, `design-factory/CREATIVE_ARCHITECTURE.md`, `design-factory/creative-sources.lock.json` and `design-factory/QA_CHECKLIST.md`. If making film, also read the owner `Animation/studio/studio-engine/STUDIO.md` and `Animation/studio/QUALITY_PLAYBOOK.md` from its pinned ref **without moving its engine into the shipped app**.

## Agent router
- "Icon, illustrated symbol": use consistent Lucide style, correct stroke, align baseline; logo/brand art needs bespoke work and legal rights. Iconify is a search layer, each actual icon pack has its own licence.
- "Hover, entrance, card, list": native CSS/WAAPI for first pass. Use Motion if orchestration, spring or layout transition justifies it.
- "Layers, depth, cinematic landing": use `creative-lab` original reference + layered scene contract; write real hero composition, optional scroll/cursor effects, no mandatory WebGL.
- "Smooth scroll": Lenis only for opted-in storytelling pages, never workflow dashboards. Preserve native keyboard navigation and anchor semantics.
- "3D website": Three.js only if real product value; React Three Fiber for React; poster fallback with WebGL unsupported or reduced motion.
- "Character/vector animation": choose Lottie/dotLottie OR Rive, with licensed project asset; do not bundle two competing runtimes.
- "Promo film/social reel": route to pinned owner Animation Studio first; dimension/fps/audio specified and verified; Motion Canvas optional only when needed.
- "Motion slides": route to Slide Forge, data schema and validator; export video via film adapter only after evidence.

## Always produce a Creative Brief
Industry, buyer, desired effect, hero narrative, user task, one critical screen, selected profile, design reference (URL/time/date), palette/token mapping, icon set/licence, layers ordered back-to-front, chosen clock (pointer/scroll/time), duration, easing, motion trigger, mobile fallback, reduced-motion behavior, performance budgets, source/asset provenance, implementation and explicit test artifacts.

## Creative review pipeline
1. Screenshot before change and collect lawful references. Decompose each into composition, foreground/mid/background, focal plane, light, typography, camera and timing, interaction, copy hierarchy.
2. Three truly different mood directions for brand-new creative styles. Pick one rationale, no speculative product screenshots.
3. Write versioned recipe under `creative-recipes/`, fit motion to product. Avoid demo-induced page bloat.
4. Build smallest honest working scene. Static content must be meaningful; no screenshot-only substitute where real behavior was asked.
5. Capture scroll, hover, pause, mobile, AR/EN, light/dark and reduced-motion, including actual frame strips for timed scenes.
6. Run measurable tests and inspect real screenshots/film playback. Accessibility cannot be replaced by aesthetic review.
7. Record exact source and SHA, licence approval, FPS/CPU/size observations, tests, defects, review decisions. Fail closed on missing evidence.

## Creative quality rules
- One visual centerpiece per view; other movement supports attention, not compete for it.
- Motion intent: entrance 350–750ms, hover 100–220ms, section transitions 350–900ms are **starting suggestions**, adapt to actual content and user testing.
- Design real parallax depth planes and highlight direction, not arbitrary layers stacked with shadows.
- No fake parallax/camera if pointer or scroll control is absent. No dead buttons or demo content presented as production.
- Do not break RTL text, disable text selection or hide forms behind pointer effects.
- No `eval`, third-party injection, unbounded timers or unexpected file/network accesses.
- Keep existing product design system and security; create new signature looks for marketing, not mandatory for ERP tables.
