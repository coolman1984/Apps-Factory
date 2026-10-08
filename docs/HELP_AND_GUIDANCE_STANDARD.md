# Built-in help, "Guide me" and "Solve a problem" — a core part of every product

Decision: [ADR-0005](decisions/ADR-0005-help-diagnostics-remote.md). Controls: `HELP-01` … `HELP-07`.
Reference implementation: Hessa (`js/views/help.js`, `js/views/guides.js`: 31 guides, a docked coach, 44 situations).

**Goal:** a customer never needs to call us to learn how to use the program. Help is not a manual at the end; it is a part of
the product, written, tested and released with every feature.

## 1. What every product ships (all tiers)
| Part | What the user sees | Rule |
|---|---|---|
| **Guides** (الدليل) | One short guide per daily job, per role, with steps | Every screen is reachable from at least one guide |
| **Guide me** (ارشدني) | A docked coach that opens the right page and outlines the exact button, step by step, then says "done" | Every guide step that names a button can light it up; a new button gets a stable `data-` hook |
| **Solve a problem** (حلّل المشكلة) | Real problems and edge cases grouped by topic, each: what you see → why → what to do, with a "Take me there" link and a "Guide me" button | Every error message the program can show has an entry; every support ticket that was not a bug adds an entry |
| **Questions** (أسئلة) | Short Q&A with search that understands Arabic spelling variants | Search finds by the words people really type |
| **Contact support** | Self-check, help request, support window ([PROTECTION_UPDATES_AND_SUPPORT.md](PROTECTION_UPDATES_AND_SUPPORT.md)) | Last resort, after the three above |
| **"?" on every page** | Opens the guide and problems of the page you are on | — |

**No welcome slideshow by default.** The first sign-in goes straight to work with one short line that says where help is.
A product may keep a tour only as an opt-in button inside Help.

## 2. Language: polished Egyptian Arabic (عامية مصرية راقية)
Help text (guides, problems, questions, support) is written in **polished Egyptian Arabic**: the way a respectful, educated
professional explains something to a customer. Buttons and labels may stay in the product's UI language; help explains them.

Rules:
1. A 12-year-old understands it on the first read. One idea per sentence. Short sentences.
2. Respectful and professional: «حضرتك» where natural, «من فضلك», no slang, no jokes, no street words.
3. Say what to press, where it is, and what will happen after: «اضغط زرار «حفظ» تحت على الشمال، وهتظهر لك رسالة إن العملية تمت».
4. Explain the *why* in one short sentence when a rule might surprise the user (money, permissions, deleting).
5. No technical words: not «سيرفر», «داتابيز», «سينك». Say «الجهاز الرئيسي», «البيانات», «المشاركة بين الأجهزة».
6. Numbers, codes and receipt numbers in Western digits inside `<bdi dir="ltr">`.
7. Every problem entry follows: **إيه اللي بيحصل؟ → ليه؟ → تعمل إيه؟ (خطوات) → لو لسه المشكلة موجودة**.

| Too heavy (avoid) | Polished Egyptian (use) |
|---|---|
| يتعذّر إتمام العملية نظرًا لعدم توفر الصلاحية اللازمة. | الحساب ده مش مسموح له يعمل الخطوة دي. اطلب من مدير البرنامج يدّيك الصلاحية. |
| يُرجى التحقق من الاتصال بالشبكة ثم إعادة المحاولة. | اتأكد إن الجهاز متوصل بالشبكة، وبعدين جرّب تاني. |
| تم حفظ البيانات بنجاح. | تمام، اتحفظ. |

## 3. "Solve a problem" coverage checklist (per product)
Sign-in and passwords · permissions denied · printing and receipts · money mistakes and reversals · duplicates (same name,
double click, retry) · power cut and the program closing suddenly · internet or office network down · the main PC off ·
two PCs disagree · backup and restore · subscription ending, grace, renewal · moving to a new PC · Windows warnings on install
(SmartScreen, Smart App Control) · antivirus false alarm · phone link not opening · slow program · full disk · wrong date/time on
the PC · Arabic text or numbers looking wrong · importing from Excel · deleted something by mistake · a new employee · an
employee who left.

## 4. Quality gates (tested, not promised)
- Every guide, problem and question exists in both languages (key parity test).
- Every "Take me there" link opens an existing page; every "Guide me" step finds its button (browser test).
- Every server error key has a problem entry or a direct explanation (test).
- A reading pass by someone who is not the developer before each release; record who and when in the release evidence.
- Ticket loop: every support ticket that was a "how do I…" adds or improves a guide or a problem entry in the next release.
