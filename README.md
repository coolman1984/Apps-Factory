# Apps Factory | مصنع التطبيقات 🏭

**Version:** 0.3.0 foundation + connectivity tiers + protection/updates/support • **Status:** standards, specs and one shared package (`af-license`); not a deployable authenticated SaaS. The licence package is unit-tested, not yet field-verified inside a product.

مستودع القواعد الموحدة اللي كل تطبيق تجاري جديد عندك يبدأ منه: بحث السوق، تصميم ثابت، إدارة وصلاحيات، اشتراكات وتراخيص، خصوصية، أمان، بيانات، نسخ احتياطي، اختبار، تشغيل ودعم. **التخصص فقط بيتغير، القاعدة لا تُنسخ عشوائيًا.**

## لوحة تشغيل المصنع
- [افتح لوحة إنشاء مواصفات برنامج جديد](CONTROL_CENTER.html) بعد تنزيل الملف أو استنساخ المشروع. الصفحة محلية، لا ترسل بيانات.
- اختبار القواعد: `python scripts/factory.py doctor`
- إنشاء وصف: `python scripts/factory.py new --id test-app --name "نظام تجريبي" --mode lan --market EG --output test-app.json`
- إنشاء وصف بالباقة الأعلى (مزامنة سحابية + موبايل + فروع + ملاك متعددين): أضف `--tier cloud_sync --sites multi --clients windows_desktop,browser,mobile_pwa --multi-owner`
- فحص مسودة: `python scripts/factory.py check test-app.json`
- اختبار جاهزية بيع **يُفشل المسودات عمدًا**: `python scripts/factory.py check test-app.json --release`
- اختبارات أداة المصنع: `python -m unittest discover -s tests -v`
- اختبارات قطعة الرخص: `cd packages/af-license && pip install -r requirements.txt && python -m unittest discover -s tests -v`

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
