# خط باتشات العملاء: إيجنت Claude Code · Customer patch agent

**الحالة: قالب جاهز ومش متفعّل.** الملفات هنا في `templates/`، فـGitHub مش بيشغّلها.
**Status: ready template, NOT active.** Files in `templates/` never run.

| الملف · File | الدور · Role |
|---|---|
| `claude-patch-agent.yml` | الإيجنت اللي بيصلّح بلاغ العميل ويفتح PR، وبعدها يبعتلك رسالة تليجرام. · Fixes a customer report, opens a PR, then sends you a Telegram notice. |
| `notify-pr-awaiting-approval.yml` | رسالة تليجرام لما PR تاني (تصليحك انت) يتفتح لبلاغ عميل. · Telegram notice for other PRs (your own fixes) that close a customer-report issue. |

---

## 1. بيعمل إيه · What it does

**بالعربي:**
1. بلاغ من عميل بيتحوّل لـIssue عليه علامة `customer-report`.
2. الإيجنت بيشتغل **بس** لو العلامة دي موجودة **و** المفتاح `PATCH_AGENT_ENABLED` = `true`.
3. يقرا الخطأ من الـIssue، ويدوّر على السبب الحقيقي، ويعمل أصغر تصليح ممكن.
4. يضيف أو يعدّل تست، ويشغّل تستات الريبو كلها.
5. يفتح PR واحد على `main` من فرع `patch/issue-<رقم>`، ومكتوب فيه `Fixes #<رقم>`.
6. يبعتلك رسالة تليجرام فيها لينك الـPR وعنوان البلاغ.
7. **عمره ما بيدمج، ولا بيعمل tag، ولا بيطلّع إصدار.**

لو الخطأ مش واضح أو التستات ما عدّتش، ما بيفتحش PR. بيكتب تعليق على الـIssue باللي ناقص.

**English:** on an issue labelled `customer-report` (and only when the repo variable `PATCH_AGENT_ENABLED` is `true`),
Claude Code reads the customer's error, finds the root cause, makes the minimal fix, adds/adjusts a test, runs the
repo's tests, and opens one PR to `main` (`Fixes #N`) from `patch/issue-N`. It then sends you a Telegram notice. It never
merges, tags or releases. If the error is unclear or tests fail, it comments on the issue instead of opening a PR.

**الإعدادات · Settings** (في الملف · in the file):

```yaml
on:
  issues:
    types: [opened, labeled]
jobs:
  patch:
    if: >-
      vars.PATCH_AGENT_ENABLED == 'true' &&
      github.event.issue.state == 'open' &&
      contains(github.event.issue.labels.*.name, 'customer-report') &&
      (github.event.action == 'opened' || github.event.label.name == 'customer-report')
    timeout-minutes: 30
    concurrency: { group: patch-agent-issue-<N>, cancel-in-progress: true }
    ...
          claude_args: |
            --model claude-sonnet-5-5
            --effort high
            --max-budget-usd 2
            --max-turns 40
```

**قواعد ثابتة · Hard rules:**
- ما يلمسش ملفات المصنع المنسوخة، اللي أولها `Vendored from Apps-Factory … do not edit here`. وفيه خطوة بعد التشغيل بتوقّع الـjob بعلامة حمرا لو حصل.
  Never edits vendored factory files; a post-run guard step fails the job if it does.
- ما يجمعش أي بيانات خاصة، ولا يكتبها: لا أسماء، ولا أرقام، ولا إيميلات، ولا مبالغ، ولا أكواد ترخيص. أرقام وعدّادات بس.
  No private data collected or written; ids and counts only.
- ما يلمسش `.github/workflows/` ولا أي سر. ومقفول عليه الدمج والإصدارات والـforce push.
  No workflow or secret edits; merge, release, tag and force-push are disallowed tools.
- نص الـIssue بيتعامل معاه كبيانات من العميل، مش كأوامر.
  The issue text is treated as data, not instructions.
- بيمشي على قواعد `CLAUDE.md` و`AGENTS.md` في الريبو. · Follows the repo's `CLAUDE.md` / `AGENTS.md`.

## 2. التفعيل لكل برنامج · Activate per product repo

1. انسخ الملف · Copy: `templates/patch-pipeline/claude-patch-agent.yml` → `.github/workflows/claude-patch-agent.yml`
   (محتاج صلاحية `workflow` · needs the `workflow` permission).
2. ركّب Claude GitHub App على الريبو · Install the Claude GitHub App on the repo: <https://github.com/apps/claude>.
3. ضيف السر · Add the secret (Settings → Secrets and variables → Actions → Secrets):
   - `ANTHROPIC_API_KEY` (مفتاح API من Claude Console · from the Claude Console), **أو · or**
   - `CLAUDE_CODE_OAUTH_TOKEN` (اشتراك · subscription, من الأمر · from `claude setup-token`)، وبدّل السطرين في الملف · and swap the two lines in the file.
4. اعمل العلامة · Create the label: `gh label create customer-report -R <owner>/<repo> --color D93F0B --description "Issue created from a customer report"`
5. شغّل المفتاح · Turn it on: `gh variable set PATCH_AGENT_ENABLED -R <owner>/<repo> --body true`
6. اختياري، تليجرام · Optional, Telegram: ضيف السرّين · add secrets `TELEGRAM_BOT_TOKEN` و`TELEGRAM_OWNER_CHAT_ID`.

**الإيقاف · Deactivate:** `gh variable set PATCH_AGENT_ENABLED -R <owner>/<repo> --body false`
(أو امسح المتغير · or delete the variable). أي قيمة غير `true` بالظبط = مقفول · anything but exactly `true` = off.

**ملاحظات · Notes:**
- اللي بيحط العلامة أو بيفتح الـIssue لازم يكون عنده صلاحية كتابة على الريبو. الأكشن بيرفض أي bot، فلو الوسيط بيعمل الـIssues بـGitHub App، ضيف اسمه بس في `allowed_bots`، ومتحطش `*` أبدًا.
  The labeller/opener needs write access. Bots are refused, so if the relay uses a GitHub App, list only that app in `allowed_bots`, never `*`.
- العلامة دي بيحطها الوسيط (الـrelay) لما يفتح Issue من بلاغ عميل. ده لسه **مش متبني** في الوسيط.
  The relay is meant to apply `customer-report` when it opens an issue from a report. This is **not built yet** in the relay.
- الأوامر المسموحة في `--allowedTools` معمولة للمصنع (Python/Node). عدّلها حسب أوامر تستات كل برنامج.
  `--allowedTools` lists factory-style test commands (Python/Node); adjust them to each product's test commands.

## 3. تنبيه تليجرام · Telegram notice

**في الإيجنت · In the agent** (`claude-patch-agent.yml`): خطوة بعد التشغيل بتدوّر على PR مفتوح من `patch/issue-<رقم>`.
لو لقته، بتبعت لـ`TELEGRAM_OWNER_CHAT_ID` رسالة فيها اسم الريبو ورقم البلاغ وعنوانه ولينك الـPR.
A step after the run looks for an open PR from `patch/issue-N` and, if found, sends the repo, issue number and title,
and PR link.

**القالب المنفصل · Separate template** (`notify-pr-awaiting-approval.yml`):
- بيشتغل لما PR يتفتح أو يبقى ready for review على `main`.
  Fires on `pull_request` `opened` / `ready_for_review` to `main`.
- بيقرا من وصف الـPR `Fixes/Closes/Resolves #N`، وبيبعت الرسالة بس لو الـIssue ده عليه `customer-report`.
  Reads those references from the PR body and notifies only for `customer-report` issues.
- بيتخطّى فروع `patch/issue-*`، لأن الإيجنت بعت رسالتها خلاص. يعني ده لتصليحاتك انت.
  Skips `patch/issue-*` branches (the agent already notified), so it covers your own fixes.
- مفتاحه لوحده · Its own switch: `gh variable set PATCH_NOTIFY_ENABLED -R <owner>/<repo> --body true` (والإيقاف `false` · off with `false`).
- صلاحياته قراءة بس · Read-only permissions (`issues: read`, `pull-requests: read`).

**الاتنين · Both:**
- لو `TELEGRAM_BOT_TOKEN` أو `TELEGRAM_OWNER_CHAT_ID` مش موجودين، الخطوة بتتخطّى بهدوء من غير ما توقّع حاجة.
  If either secret is unset, the step skips quietly.
- لو تليجرام ما ردّش، بيطلع تحذير بس، والـPR بيفضل زي ما هو.
  A Telegram failure is only a warning; the PR is unaffected.
- الرسالة نص عادي، ومفيهاش أي بيانات عملاء: رقم البلاغ وعنوانه ولينك بس. ولو عنوان الـIssue ممكن يبقى فيه بيانات، الوسيط لازم يكتبه من غيرها.
  Plain text with no customer data: issue number, title and link only. The relay must keep issue titles free of personal data.
- إزاي تجيب القيم دي · Getting the values: `TELEGRAM_BOT_TOKEN` من BotFather (`/newbot`). وابعت أي رسالة لبوتك، وبعدها افتح
  `https://api.telegram.org/bot<TOKEN>/getUpdates` وخد `chat.id`. ده بيبقى `TELEGRAM_OWNER_CHAT_ID`.
  Token from BotFather; message your bot once, then read `chat.id` from `getUpdates`.
- تليجرام ببلاش · Telegram is free.

## 4. مفتاح API ولا اشتراك؟ · API key vs subscription

| | مفتاح API · API key | اشتراك · Subscription (Pro/Max) |
|---|---|---|
| الدفع · Billing | على قد الاستخدام · pay per use | مبلغ ثابت في الشهر · fixed monthly fee |
| الحد الأقصى · Cap | `--max-budget-usd 2` لكل تصليح، وتقدر تحط حد شهري في Claude Console · per fix, plus a monthly limit in the Console | الحصة مشتركة مع استخدامك الشخصي، فلو خلصت، التصليح يقف والعكس · quota is shared with your own use |
| السر · Secret | `ANTHROPIC_API_KEY` | `CLAUDE_CODE_OAUTH_TOKEN` (`claude setup-token`) |
| ملاحظة · Note | الطريق الرسمي المعتاد للأتمتة · the usual route for automation | شروط الاشتراك معمولة لاستخدام شخصي؛ **لازم تتأكد** إنها بتسمح بالتشغيل الأوتوماتيك · subscription terms target personal use; **check them** before relying on it |

**التكلفة · Cost: «⚠️ نقطة مفتوحة»**
- لسه ما اتحددش مين هيدفع، ولا إزاي: مفتاح API بحد أقصى، ولا اشتراك.
  Not decided yet: API key with a cap, or a subscription.
- `--max-budget-usd` بيتحسب على تقدير Claude Code نفسه، فالتشغيل ممكن يعدّي الحد بشوية. ودقايق GitHub Actions ببلاش طول ما الريبو عامة.
  The cap uses Claude Code's own estimate, so a run can pass it slightly. Actions minutes are free on public repos.
- مفيش أي تفعيل قبل قرارك. · Nothing is activated before your decision.

## 5. بوابة الموافقة · Approval gate

- **مفيش EXE بيوصل لأي عميل من غير موافقتك.** الإيجنت بيفتح PR بس. انت اللي بتدمج، وبعدها الـworkflow الموجود بيبني الـEXE ويطلّع الإصدار، وبعدها التوصيل (إشعار جوه البرنامج، وإيميل، وwa.me بضغطة منك).
  **No EXE reaches a customer without your approval.** The agent only opens a PR; you merge; then the existing installer
  workflow builds and releases; then delivery (in-app notice, email, manual wa.me).
- **Patch Reviewer بيتنادى يدوي بس**: «راجع PR رقم كذا في ريبو كذا» ومعاه الخطأ الأصلي. القالب ده **عمره ما بيناديه**.
  **The Patch Reviewer is called manually only**; this template never calls it.
- حماية الفرع `main` (PR + تستات لازم تعدّي + ممنوع force push) بتفضل شغالة على PRs الإيجنت كمان.
  Branch protection on `main` still applies to the agent's PRs.

## 6. مصادر · Sources

- <https://code.claude.com/docs/en/github-actions> (inputs, `claude_args`, `id-token: write`, bot/write-access checks)
- <https://code.claude.com/docs/en/cli-reference> (`--effort`, `--max-budget-usd`, `--max-turns`)
- <https://code.claude.com/docs/en/model-config> (Sonnet 5.5 defaults to `medium`, so `high` is set explicitly)
- <https://github.com/anthropics/claude-code-action> (`action.yml`, `docs/configuration.md`, `docs/security.md`)
