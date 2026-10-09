# Built-in help, "Guide me" and "Solve a problem" — a core part of every product

Decision: [ADR-0005](decisions/ADR-0005-help-diagnostics-remote.md). Controls: `HELP-01` … `HELP-07`.
Reference implementation: Hessa (`js/views/help.js`, `js/views/guides.js`: guides, a docked coach, situations, learning paths).
Gate: `packages/af-guide` (catalogue rules, learning paths, simple-Arabic register), copied into each product by `scripts/vendor_guide.py`.

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

## 2. The learning path (المنهج) — owner's decision 2026-10-09

A new person must be able to learn the program **alone**, in the right order, without anybody sitting next to them.
So every product has, next to the guide library, a **learning path for every role**: the administrator who installs and
sets up the program, and every daily role after them (cashier, storekeeper, front desk, teacher, dispatcher…).

| Part | What the person sees | Rule |
|---|---|---|
| **Path per role** | "Your path: the administrator — 4 of 9 lessons" with an ordered list of lessons | One path per ready-made role/profile; the administrator's path starts by setting the program up (shop/centre details → lists → people → daily work → safety) |
| **You are here** (أنت هنا) | The first lesson not done yet is marked and has one button: **Start** (it starts *Guide me* for that lesson) | The program finds it by itself: each lesson has, wherever possible, a *fact* the server checks (the shop has a name, a product exists, a shift was opened, a backup was made…); a lesson without a fact is done when its guide was finished |
| **A card on the first page** | Until the path is complete: "Continue your path: lesson 4 — Open the shift" with Start | One card, never a pop-up; it can be hidden |
| **Choose another path** | A person can open any other path to learn more | The default path follows the person's profile |

A lesson **is a guide**: there is one source of steps, the same one *Guide me* walks through. Facts are computed from the
real records (counts), never stored, so the progress is always true — also after an import, a restore or a second PC.

## 3. Language: simple formal Arabic (العربية المبسطة) — owner's decision 2026-10-09

All help (guides, paths, problems, questions, support) is written in **simple formal Arabic**: correct Arabic with the
easiest everyday words, between office Arabic and street Egyptian, so that anyone understands it on the first read and the
words still sound polite and beautiful. (This replaces "polished Egyptian Arabic" of 2026-10-08.)

Rules:
1. A 12-year-old understands it on the first read. One idea per sentence. Short sentences. Address the reader as «أنت».
2. Formal grammar with everyday words: «اضغط»، «اختر»، «اكتب»، «افتح»، «تأكد»، «إذا»، «الذي»، «هذا/هذه»، «زر».
3. No street words: not «ده/دي»، «مش»، «عشان»، «إزاي»، «إيه»، «دلوقتي»، «كده»، «بتاع»، «اللي»، «زرار»، «دوس».
4. No stiff office words: not «يُرجى»، «نظرًا»، «يتعذّر»، «حيث إن»، «بموجب»، «وعليه».
5. Say what to press, where it is, and what happens next. Explain the *why* in one sentence when a rule may surprise.
6. No technical words: not «سيرفر»، «داتابيز»، «سينك». Say «الجهاز الرئيسي»، «البيانات»، «المشاركة بين الأجهزة».
7. Numbers and codes in Western digits inside `<bdi dir="ltr">`.
8. Every problem: **ماذا يحدث؟ → لماذا؟ → ماذا تفعل؟ (خطوات) → إذا استمرت المشكلة**.

| Street Egyptian (avoid) | Stiff (avoid) | Simple formal Arabic (use) |
|---|---|---|
| الحساب ده مش مسموح له يعمل الخطوة دي. | يتعذّر إتمام العملية نظرًا لعدم توفر الصلاحية. | هذا الحساب لا يملك صلاحية هذه الخطوة. اطلب من مدير البرنامج أن يمنحك الصلاحية. |
| اتأكد إن الجهاز متوصل بالشبكة وجرّب تاني. | يُرجى التحقق من الاتصال بالشبكة ثم إعادة المحاولة. | تأكد أن الجهاز متصل بالشبكة، ثم حاول مرة أخرى. |
| دوس على زرار «حفظ» وهيظهرلك إنها اتحفظت. | يتم الضغط على زر الحفظ لإتمام عملية الحفظ. | اضغط زر «حفظ»، وستظهر رسالة تؤكد الحفظ. |

The gate `packages/af-guide` (`register()`) refuses the street and stiff words above in every Arabic help text.

## 4. "Solve a problem" coverage checklist (per product)
Sign-in and passwords · permissions denied · printing and receipts · money mistakes and reversals · duplicates (same name,
double click, retry) · power cut and the program closing suddenly · internet or office network down · the main PC off ·
two PCs disagree · backup and restore · subscription ending, grace, renewal · moving to a new PC · Windows warnings on install
(SmartScreen, Smart App Control) · antivirus false alarm · phone link not opening · slow program · full disk · wrong date/time on
the PC · Arabic text or numbers looking wrong · importing from Excel · deleted something by mistake · a new employee · an
employee who left.

## 5. Quality gates (tested, not promised)
- `afguide.errors(catalogue)` is empty in the product's tests: guides complete in both languages, a path for every role, every page reached, the register.
- Every guide, problem and question exists in both languages (key parity test).
- Every "Take me there" link opens an existing page; every "Guide me" step finds its button (browser test).
- Every server error key has a problem entry or a direct explanation (test).
- A reading pass by someone who is not the developer before each release; record who and when in the release evidence.
- Ticket loop: every support ticket that was a "how do I…" adds or improves a guide or a problem entry in the next release.
