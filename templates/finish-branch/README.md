# إنهاء الفرع

يدمج هذا المسار الفروع الجاهزة في `main` بدمج squash، بعد نجاح الفحوصات المطلوبة فقط. لا يحذف الفروع، ولا يستخدم صلاحية المدير، ولا يدفع بالقوة.

## الوضعان

- **الجدولة:** كل ساعة عند الدقيقة 23 (قد تتأخر تشغيلات GitHub المجدولة قليلًا). يختار الفروع ما عدا `main` و`dependabot/*` إذا كان آخر إيداع أقدم من ساعة (60 دقيقة) وأحدث من `ACTIVE_SINCE`، والفرع متقدم عن `main`، ولم يُدمج طلب بنفس الإيداع.
- **اليدوي:** فرع واحد تحدده. يرفض `main`، ويوقف التشغيل بخطأ واضح إذا لم يوجد الفرع.

يُتخطى الطلب إن كان مسودة أو عليه العلامة `do-not-merge`. وإن لم يوجد طلب مفتوح، يُفتح طلب بعنوان `Auto-finish: <الفرع>`. ثم تُشغَّل فحوصات `CHECK_WORKFLOWS` إن لم تكن مسجّلة على نفس الإيداع، ويُفعَّل الدمج التلقائي.

## ما يُعدَّل في كل مستودع

في رأس `.github/workflows/finish-branch.yml` فقط:

- `CHECK_WORKFLOWS`: أسماء ملفات الفحص، مفصولة بمسافة.
- `ACTIVE_SINCE`: وقت UTC. الوضع المجدول يتجاهل أي فرع آخر إيداع فيه أقدم من هذا الوقت، فلا تُمس الفروع القديمة الموجودة من قبل.

## إعداد المستودع مرة واحدة
```bash
gh repo edit OWNER/REPO --enable-auto-merge
gh api -X PUT repos/OWNER/REPO/actions/permissions/workflow -f default_workflow_permissions=read -F can_approve_pull_request_reviews=true
gh label create needs-fix -R OWNER/REPO --color B60205 --description "Checks failed"
gh label create do-not-merge -R OWNER/REPO --color F9D0C4 --description "Do not auto-merge"
```
انسخ `templates/finish-branch/finish-branch.yml` إلى `.github/workflows/finish-branch.yml`.

## إيقافه على فرع

اجعل طلب السحب مسودة، أو أضف العلامة `do-not-merge`.

## تشغيل يدوي

```bash
gh workflow run finish-branch.yml -R OWNER/REPO -f branch=BRANCH
```

## حد معروف

الدمج الذي ينفذه `GITHUB_TOKEN` لا يشغّل مسارات الدفع على `main`، ومنها خطوة نشر الإصدار عند الدفع إلى `main`. إذا لزم إصدار بعد دمج تلقائي، ادفع وسمًا `v*` يدويًا.
