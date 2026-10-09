# Apps Factory | مصنع التطبيقات 🏭

**Version:** 0.9.0 — telemetry hardening (token transport, nothing lost mid-batch, new PCs wait for approval, alerts sent outside the lock); Telegram is a core owner-alert channel; adds telemetry ingest, incidents, per-person usage and parallel multi-channel alerts to the Control Center, plus a Cloudflare relay template, on top of consent/telemetry (0.7.0) and the guide engine (0.6.0); see [CHANGELOG](CHANGELOG.md) • **Status:** standards, specs and tested shared pieces; first product built on them: [الستور](https://github.com/coolman1984/Store). Nothing here is field-verified yet.

مستودع القواعد الموحدة اللي كل تطبيق تجاري جديد عندك يبدأ منه: بحث السوق، تصميم ثابت، إدارة وصلاحيات، اشتراكات وتراخيص، خصوصية، أمان، بيانات، نسخ احتياطي، اختبار، تشغيل ودعم. **التخصص فقط بيتغير، القاعدة لا تُنسخ عشوائيًا.**

## 🎨 Design Factory — المصنع البصري الموحد
- **[ابدأ من هنا: Design Factory](design-factory/README.md)** مع دليل وكيل التصميم وقواعد الألوان والخطوط وواجهة تجريبية شغالة بدون إنترنت.
- **[افتح واجهة التصميم المحلية](design-factory/reference/index.html)** بعد تنزيل المستودع. عربي / إنجليزي، فاتح / داكن، بحث وجداول ونموذج إضافة حقيقي على بيانات تجريبية.
- ٦ مصادر واجهات ومهارات مربوطة بإصدارات مُثبتة كـ **Git Submodules، وليست Forks شخصية**؛ انظر [المصادر والتراخيص](design-factory/UPSTREAMS.md).
- أي Agent لازم يقرأ [قواعد التصميم](design-factory/AGENTS.md) ويعمل [فحوصات الجودة البصرية](design-factory/QA_CHECKLIST.md) قبل اعتماد الواجهة.

## ✨ Creative Factory v2 — الأيقونات والحركة والطبقات والفيديو
- [المعمل البصري الحي، بدون إنترنت](design-factory/creative-lab/index.html) وفيه مشهد ٤ طبقات، تحكم في العمق والتايم لاين، عربي وإنجليزي، ووصف قابل للتصدير.
- [دستور الحركة والطبقات](design-factory/CREATIVE_ARCHITECTURE.md) و[تعليمات أي وكيل](design-factory/CREATIVE_AGENT_PLAYBOOK.md) و[تدقيق مشاريع الموشن عندنا](design-factory/CREATIVE_REPO_AUDIT.md).
- [١٧ مصدرًا جديدًا بإصدارات مثبتة](design-factory/creative-sources.lock.json) (١٤ خارجي + ٣ مشاريع موجودة عندك) عبر Git Submodules، **مش نسخ كود تجاري داخل المصنع**.
- [وصفات جاهزة](design-factory/creative-recipes/) وبرمجيات خفيفة قابلة للتركيب `design-factory/core/creative-effects.css` و`design-factory/core/creative-primitives.js`.
- أدوات تركيب للمشروع الموجود: `python design-factory/scripts/install.py --target "C:\\My-App" --creative` (معاينة) ثم أضف `--apply` للتثبيت الآمن؛ لا يتم استبدال الملفات الموجودة.
- فحوصات المتصفح: `cd design-factory && npm run test:creative` بعد تثبيت اعتماد الاختبارات وChromium، ولا تدّعي الموافقة الفنية لمجرد نجاحها.

## لوحة تشغيل المصنع
- [افتح لوحة إنشاء مواصفات برنامج جديد](CONTROL_CENTER.html) بعد تنزيل الملف أو استنساخ المشروع. الصفحة محلية، لا ترسل بيانات.
- اختبار القواعد: `python scripts/factory.py doctor`
- إنشاء وصف: `python scripts/factory.py new --id test-app --name "نظام تجريبي" --mode lan --market EG --output test-app.json`
- إنشاء وصف بالباقة الأعلى (مزامنة سحابية + موبايل + فروع + ملاك متعددين): أضف `--tier cloud_sync --sites multi --clients windows_desktop,browser,mobile_pwa --multi-owner`
- فحص مسودة: `python scripts/factory.py check test-app.json`
- اختبار جاهزية بيع **يُفشل المسودات عمدًا**: `python scripts/factory.py check test-app.json --release`
- اختبارات أداة المصنع: `python -m unittest discover -s tests -v`
- اختبارات قطعة الرخص: `cd packages/af-license && pip install -r requirements.txt && python -m unittest discover -s tests -v`

## الجديد في 0.7 ✨
- 🤝 **الموافقة** [packages/af-consent](packages/af-consent/README.md): «أوافق حتى يستطيع [اسم البائع] مساعدتي عن بُعد». الموافقة على مستويين: المنشأة، ثم كل شخص. تستطيع سحب الموافقة في أي وقت.
- 📡 **القياس وبلاغات المشكلات** [packages/af-telemetry](packages/af-telemetry/README.md) • [المعيار](docs/PRIVACY_TELEMETRY_STANDARD.md):
  - يُرسَل فقط أرقام تعريف وعدّادات، ولا تُرسَل أبدًا كلمات السر أو ما يُكتب أو صور الشاشة أو بيانات العملاء أو المبالغ. القيود مطبّقة في الكود والاختبارات.
  - زر «أبلغ عن مشكلة» يعمل بدون موافقة، مع معاينة كاملة لما سيُرسَل.
- 🧪 **القاعدة ROLL-01:** التجربة على بيانات التدريب أولًا، ثم على أجهزة العملاء.

## الجديد في 0.6 ✨
- 🧭 **الدليل التفاعلي** [packages/af-guide](packages/af-guide/README.md) • [المعيار](docs/GUIDED_ONBOARDING_STANDARD.md):
  - طريق لكل دور، ويُحفظ تقدّم كل شخص على الخادم.
  - مرشد ينتقل وحده إلى الخطوة التالية.
  - زر «؟» في كل صفحة، وكل رسالة خطأ تربط بشرح المشكلة.
  - تبديل لغة الدليل، وفحص الأسلوب «العربية الميسّرة».
- فحص الدليل: `python scripts/factory.py guide <product>/guide --release`

## الجديد في 0.5 ✨
- 🔑 **برنامج الأكواد** [apps/licence-studio](apps/licence-studio/README.md): يطلع كود تجربة ١٤ يوم مربوط بجهاز واحد، بشاشة واضحة، والوكيل يتصل بيه بـ MCP.
- 🎨 **نظام التصميم** [packages/af-ui](packages/af-ui/README.md) • [القواعد](docs/DESIGN_SYSTEM.md)
- ⚡ **قسم السرعة** [tools/ui-lab](tools/ui-lab/README.md) • [المعيار](docs/PERFORMANCE_STANDARD.md) — ✅ **قسم الجودة** [docs/QUALITY_SYSTEM.md](docs/QUALITY_SYSTEM.md)
- 🧠 **مخزن المعرفة** [docs/knowledge](docs/knowledge/README.md): خريطة المستودعات، خريطة القدرات، الدروس، مشاريع مشهورة نعتمد عليها.
- 🤖 مهارات جاهزة للوكيل في `.claude/skills/`.

## ابدأ من هنا
1. اقرأ [تعليمات الوكيل](AGENTS.md) و[دستور المصنع](FACTORY_CONSTITUTION.md).
2. افتح [دليل الدراسة](docs/MARKET_AND_STANDARDS.md) و[مراجعة 30 مشروع](docs/REPOSITORY_AUDIT.md).
3. انسخ [وصف المنتج](templates/PRODUCT_BRIEF.md) و[دراسة المنافسين](templates/MARKET_RESEARCH.md)، وحدد نوع التشغيل: `desktop` أو `lan` أو `saas`.
4. حدّد المكونات الإلزامية من [قائمة المعايير](factory/controls.json) ومسار التجربة الأساسية واختبارات القبول؛ استخدم [نموذج الوصف](factory/product.schema.json).
5. لا تبدأ كتابة وظائف العميل قبل إقرار السوق والنطاق والمخاطر؛ ولا تعتبر المنتج صالحًا للبيع دون [بوابات الإصدار](docs/DELIVERY_GATES.md).

**أول مشروع يُطبق عليه القالب:** [حصّة](https://github.com/coolman1984/Teachers) كتجربة، من غير تعديل المستودعات الحالية أو نقل أسرار/بيانات عملاء.

## باقات التشغيل ☁️
| الباقة | `connectivity.tier` | لو الجهاز الرئيسي اتقفل |
|---|---|---|
| جهاز واحد | `standalone` | البرنامج واقف |
| شبكة مكتب | `office_server` | باقي الأجهزة ماتقدرش تسجل |
| شبكة مكتب بنسخة على كل جهاز (زي حصّة) | `office_mesh` | كل جهاز يكمّل لوحده ويتزامن لما يرجع |
| مزامنة سحابية (الأعلى) | `cloud_sync` | كل جهاز يكمل أوفلاين ويتزامن بعدين، موبايل وفروع وملاك متعددين |
| سحابي بالكامل | `cloud_only` | مش فارقة، بس محتاج نت |

🗼 **برج المراقبة (النسخة الأولى شغالة):** [apps/control-center](apps/control-center/README.md) • ✍️ **البداية من غير شهادة ويندوز:** [القرار](docs/decisions/ADR-0004-windows-trust-without-certificate.md) و[دليل التركيب للعميل](templates/CUSTOMER_INSTALL_GUIDE_AR.md)

🛡️ **الحماية والتحديث والدعم:** رخص موقّعة (قطعة جاهزة في `packages/af-license`)، نسخ مترجمة وموقّعة، تحديثات موقّعة مابتلمسش بيانات العميل، وبرج مراقبة للعملاء والأعطال والدعم عن بعد بإذن العميل. [التفاصيل](docs/PROTECTION_UPDATES_AND_SUPPORT.md) • [مواصفات برج المراقبة](examples/vendor-control-center.json)

📌 [خطة البناء](docs/BUILD_PLAN.md) • [قرار المعمارية ADR-0001](docs/decisions/ADR-0001-architecture-and-connectivity-tiers.md) • [قواعد المزامنة](docs/CONNECTIVITY_AND_SYNC.md) • [مثال الباقة الأعلى](examples/multi-branch-reference.json)

## القرار المعماري
- **برنامج واحد من برّه، قطع مستقلة من جوّه:** بايثون + تايب سكريبت + مكونات ويب + قاعدة بيانات محلية، والسحابة كباقة أعلى.
- `Apps-Factory`: المعايير، ملفات المنتجات، الاختبارات العامة، ونواة منصّة مشتركة **لاحقًا وبعد إثباتها**.
- `Business-Template`: محركات الأعمال ووصفات العملاء الموجودة، نتكامل معها **بدل إعادة بنائها**.
- `Perfect-Project-Template`: محرك تقارير وإكسل أوفلاين موجود، لا يُعاد تصميمه هنا.
- يُسمح للتطبيقات بواجهات متخصصة (مثل مساحة الرسم ثلاثي الأبعاد) مع هوية وعمليات مشتركة.
- **ممنوع:** كلمة مرور ثابتة في الإنتاج، دخول مطور سري، حجز بيانات العميل بعد انتهاء الاشتراك، ادعاء شهادة امتثال بلا تدقيق.

## حقيقة التنفيذ
هذه نسخة **مخططات وقواعد مُدوّنة**؛ ملفات المعايير لا تثبت أن المحركات نفسها مبنية أو مختبرة. لكل ميزة حالة: planned / implemented / verified / field-accepted. لا تحويل علامة "مكتوب" إلى "شغال".

المصادر والقوانين للمراجعة العامة وليست مشورة قانونية. قواعد الامتثال تُطبّق حسب الدولة ونوع بيانات العميل.
