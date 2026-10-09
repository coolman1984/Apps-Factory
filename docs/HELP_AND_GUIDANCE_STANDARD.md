> Reference spec. Living rules: [RULES.md](../RULES.md); parts: [PARTS.md](../PARTS.md).

# Built-in help, "Guide me" and "Solve a problem" — a core part of every product

Decisions: [ADR-0005](decisions/ADR-0005-help-diagnostics-remote.md), [ADR-0006](decisions/ADR-0006-guided-onboarding-and-arabic-register.md). Controls: `HELP-07`, `HELP-09`, `HELP-11` (core; the old ids `HELP-01` … `HELP-12` resolve to them, see `merged_from` in `factory/controls.json`).
The shared engine is `packages/af-guide` (role courses, coach, per-page "?", problems, language switch, style lint); how a
product adopts it is in [GUIDED_ONBOARDING_STANDARD.md](GUIDED_ONBOARDING_STANDARD.md).
Reference implementation: Hessa (`js/views/help.js`, `js/views/guides.js`: 31 guides, a docked coach, 44 situations).

**Goal:** a customer never needs to call us to learn how to use the program. Help is not a manual at the end; it is a part of
the product, written, tested and released with every feature.

## 1. What every product ships (all tiers)
| Part | What the user sees | Rule |
|---|---|---|
| **Learning path** (المنهج) | Ordered lessons for my role, with *you are here* | §2 |
| **Guides** (الدليل) | One short guide per daily job, per role, with steps | Every screen is reachable from at least one guide |
| **Guide me** (ارشدني) | A docked coach that opens the right page and outlines the exact button, step by step, then says "done" | Every guide step that names a button can light it up; a new button gets a stable `data-` hook |
| **Solve a problem** (حلّل المشكلة) | Real problems and edge cases grouped by topic, each: what you see → why → what to do, with a "Take me there" link and a "Guide me" button | Every error message the program can show has an entry; every support ticket that was not a bug adds an entry |
| **Questions** (أسئلة) | Short Q&A with search that understands Arabic spelling variants | Search finds by the words people really type |
| **Contact support** | Self-check, help request, support window ([PROTECTION_UPDATES_AND_SUPPORT.md](PROTECTION_UPDATES_AND_SUPPORT.md)) | Last resort, after the three above |
| **"?" on every page** | Opens the guide and problems of the page you are on | — |

**No welcome slideshow by default.** The first sign-in goes straight to work with one short line that says where help is.
A product may keep a tour only as an opt-in button inside Help.

## 2. The learning path (المنهج) — owner's decision 2026-10-09 (HELP-07)

A new person must be able to learn the program **alone**, in the right order, without anybody sitting next to them.
So every product has, next to the guide library, **a course (path) for every role**: the administrator who installs and
sets up the program, and every daily role after them (cashier, storekeeper, front desk, teacher, dispatcher…).

| Part | What the person sees | Rule |
|---|---|---|
| **Path per role** | "Your path: the administrator — 4 of 9 lessons" with an ordered list of lessons | One path per ready-made role/profile (`role-without-path`). The administrator's path starts by setting the program up (business details → lists → people → daily work → safety). The checker does not know this order; the reading pass of `python af_guide.py outline <folder> ar` does |
| **You are here** (أنت هنا) | The first lesson not done yet is marked and has one button: **Start** (it starts *Guide me* for that lesson) | The program finds it by itself: a guide has `done: {"state": …}` wherever possible, a state the server computes from the real rows (the business has a name, a product exists, a shift was opened, a backup was made…). A guide without a state is done when it was finished. The server answers with `course()` / `state()` of `af_guide.py` (`next` is the lesson to start) |
| **Locked lessons** | A lesson that needs an earlier one waits for it | `requires` between guides; `path-order` fails when a path puts them the wrong way round |
| **Choose another path** | A person can open any other path to learn more | The default path follows the person's profile |

A lesson **is a guide**: there is one source of steps, the same one *Guide me* walks through. A guide may be in a role's path
only if that role can do it (`role-perm`, checked against the `af-access` catalogue): a teacher's path must not hold a lesson
about balances teachers cannot see. States are computed from the real records, never stored, so the progress is always true,
also after an import, a restore or a second PC. A card on the first page ("Continue your path: lesson 4") is allowed, never
a pop-up.

## 3. Language: «العربية الميسّرة» (simple formal Arabic) — owner's decision 2026-10-09 (HELP-11)
This replaces the earlier "polished Egyptian" rule (ADR-0006).

Help text (guides, paths, problems, questions, support) is written in **simple, correct Arabic that sits between Modern
Standard Arabic and polite Egyptian**:
- sentences follow Modern Standard Arabic order, without case endings;
- use the easiest everyday words that every Egyptian already knows, so anyone understands them on the first read and they
  still sound polite;
- the result reads like a careful professional explaining something to a customer.

Buttons and labels may stay in the product's UI language; help names them exactly as they appear on the screen.

Rules (the machine-checkable ones are enforced by `af_guide.lint`, word list in `packages/af-guide/style/ar-lexicon.json`):
1. A 12-year-old understands it on the first read. One idea per sentence; at most 18 words per sentence (`sentence-long`). Address the reader as «أنت».
2. One action per guide step (`one-action`). Start with the verb: «اضغط», «اكتب», «اختر», «افتح».
3. No colloquial function words (`banned-word`):
   - «اللي» becomes «الذي/التي»;
   - «عشان» becomes «حتى/لكي»;
   - «مش» becomes «لا/ليس»;
   - «إزاي» becomes «كيف»;
   - «دلوقتي» becomes «الآن».
4. No technical words (`banned-word`): not «سيرفر», «داتا», «سيستم», «باسورد». Say «الجهاز الرئيسي», «البيانات», «البرنامج», «كلمة السر».
5. No stiff office words either: not «يُرجى», «نظرًا», «يتعذّر», «حيث إن», «بموجب», «وعليه». The lint does not list these yet; the reading pass catches them.
6. Say what to press and what will happen: «اضغط [[shift.save]]. ستظهر كلمة «مفتوحة» أعلى الصفحة.»
   - Button names are written as `[[ui.key]]`. The guide shows the real on-screen label in «» itself, so never add quotes around them (`quoted-ui`).
7. Explain the *why* in one short sentence when a rule might surprise the user (money, permissions, deleting).
8. Numbers, codes and receipt numbers are written with 0-9, never ٠-٩ (`eastern-digits`). Show them inside `<bdi dir="ltr">`.
9. Every problem entry follows this order: **ماذا ترى؟ → لماذا؟ → ماذا تفعل؟ (steps) → إذا لم ينجح ذلك**.

| Too heavy (avoid) | Too colloquial (avoid) | «العربية الميسّرة» (use) |
|---|---|---|
| يتعذّر إتمام العملية نظرًا لعدم توفر الصلاحية اللازمة. | الحساب ده مش مسموح له يعمل الخطوة دي. | دورك لا يسمح بهذه الخطوة. اطلب من المالك أن يعطيك الصلاحية. |
| يُرجى التحقق من الاتصال بالشبكة ثم إعادة المحاولة. | اتأكد إن الجهاز متوصل بالشبكة وبعدين جرّب تاني. | تأكد أن الجهاز متصل بالشبكة. ثم حاول مرة أخرى. |
| تم حفظ البيانات بنجاح. | تمام، اتحفظ. | تم الحفظ. |

## 4. "Solve a problem" coverage checklist (per product)
Sign-in and passwords · permissions denied · printing and receipts · money mistakes and reversals · duplicates (same name,
double click, retry) · power cut and the program closing suddenly · internet or office network down · the main PC off ·
two PCs disagree · backup and restore · subscription ending, grace, renewal · moving to a new PC · Windows warnings on install
(SmartScreen, Smart App Control) · antivirus false alarm · phone link not opening · slow program · full disk · wrong date/time on
the PC · Arabic text or numbers looking wrong · importing from Excel · deleted something by mistake · a new employee · an
employee who left.

## 5. Quality gates (tested, not promised)
`python scripts/factory.py guide <product>/guide --ui … --access … --errors …` runs all of these that a machine can check;
a product also asserts `afguide.errors(…) == []` in its own tests.
- Every guide, problem and question exists in every guide language (`text-missing`, HELP-11).
- Every role has a course; every guide names its permission and fits its role; progress is kept per person on the server (HELP-07).
- Every action step auto-advances or is marked as a manual step; resume after reload works (HELP-07).
- Every "Take me there" link opens an existing page; every "Guide me" step finds its button (browser test).
- Every server error key has a problem entry (`error-unexplained`, HELP-09).
- The wording passes the style lint; with `--release`, lint warnings are errors (HELP-11).
- Every guide is walked in a real browser by `packages/af-guide/testing/walk_guides.py` (HELP-07).
- A reading pass by someone who is not the developer before each release (also for the administrator's setup-first order and for stiff words); record who and when in the release evidence.
- Ticket loop: every support ticket that was a "how do I…" adds or improves a guide or a problem entry in the next release.
