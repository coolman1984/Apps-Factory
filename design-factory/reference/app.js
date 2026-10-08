/* Apps Factory Design Reference • synthetic in-memory data, no network */
"use strict";
(() => {
  const $ = (id) => document.getElementById(id);
  const root = document.documentElement;
  const dictionary = {
    ar:{
      skip:"تخطي إلى المحتوى",product:"إدارة الفريق",workspace:"مساحة العمل",overview:"نظرة عامة",people:"الموظفون",reports:"التقارير",settings:"الإعدادات",
      local:"يعمل محليًا • وضع تجريبي",owner:"مساحة تجربة",sample:"بيانات اصطناعية بالكامل",demo:"تجربة • بيانات وهمية",
      themeDark:"داكن",themeLight:"فاتح",eyebrow:"لوحة نموذجية، ليست برنامج عميل حقيقي",
      overviewDesc:"إدارة واضحة لكل ما يحتاجه فريقك، بدون ضوضاء.",peopleDesc:"كل أفراد الفريق وحالاتهم، من مكان واحد.",reportsDesc:"أرقام قابلة للتتبع محسوبة من السجلات التجريبية.",settingsDesc:"إعدادات العرض المحلي لهذا المثال.",
      newPerson:"موظف جديد",total:"إجمالي الموظفين",active:"نشط",pending:"قيد المراجعة",registered:"سجلات تجريبية",ready:"متاح للعمل",needReview:"بحاجة إلى مراجعة",
      workflow:"التدفق الأساسي",taskHeading:"كل شيء يبدأ بمهمة واضحة.",taskBody:"أضف موظفًا، راجع حالته، أو ابحث في السجلات من مكان واحد. الأرقام هنا تجريبية وتتحدث مع تغييراتك.",
      viewPeople:"عرض جميع الموظفين",statusMix:"توزيع الحالات",chartNote:"مؤشرات حقيقية محسوبة من البيانات التجريبية",directory:"دليل الفريق",latest:"سجل الموظفين",
      search:"بحث بالاسم أو القسم...",searchLabel:"بحث بالاسم أو القسم",filterLabel:"تصفية الحالة",all:"كل الحالات",person:"الموظف",department:"القسم",state:"الحالة",joined:"أضيف في",action:"الإجراء",
      empty:"لا توجد نتائج مطابقة. جرّب بحثًا آخر.",sampleFoot:"بيانات مرجعية اصطناعية • دون خادم",
      reportsTitle:"ملخص الحالة",reportsBody:"تقرير مباشر من بيانات المثال، يُحدَّث كلما أضفت شخصًا أو غيّرت حالته.",csv:"تصدير CSV",
      settingsTitle:"تخصيص تجربة العرض",settingsBody:"تغيير اللغة والمظهر ينعكس فورًا على كل الشاشات في هذا المثال.",
      changeLanguage:"تغيير اللغة",changeTheme:"تغيير المظهر",footer:"Apps Factory Design System · نسخة مرجعية محلية",
      formEyebrow:"سجل تجريبي جديد",formNote:"البيانات لن تُرسل أو تُحفظ خارج هذه الصفحة.",cancel:"إلغاء",save:"إضافة الموظف",
      toggle:"تغيير الحالة",count:"سجل ظاهر",saved:"تمت إضافة السجل داخل التجربة فقط",changed:"تم تعديل الحالة داخل التجربة فقط",
      exported:"تم تنزيل تقرير تجريبي",nothing:"لا توجد سجلات مطابقة للتصدير"
    },
    en:{
      skip:"Skip to content",product:"People operations",workspace:"WORKSPACE",overview:"Overview",people:"People",reports:"Reports",settings:"Settings",
      local:"Local • demo mode",owner:"Demo workspace",sample:"Fully synthetic data",demo:"DEMO • SYNTHETIC DATA",
      themeDark:"Dark",themeLight:"Light",eyebrow:"Design reference, not real customer software",
      overviewDesc:"Everything your team needs, without the noise.",peopleDesc:"Your team's records and status, in one place.",reportsDesc:"Traceable numbers calculated from the sample records.",settingsDesc:"Local presentation settings for this sample.",
      newPerson:"Add person",total:"Total people",active:"Active",pending:"In review",registered:"Synthetic records",ready:"Ready to work",needReview:"Needs review",
      workflow:"THE CORE WORKFLOW",taskHeading:"Every good workflow starts with clarity.",taskBody:"Add a teammate, review status or find a record from one place. These figures are synthetic and update as you work.",
      viewPeople:"Browse all people",statusMix:"STATUS MIX",chartNote:"Real calculations over synthetic example data",directory:"TEAM DIRECTORY",latest:"People records",
      search:"Search names or departments...",searchLabel:"Search names or departments",filterLabel:"Filter by status",all:"All statuses",person:"Person",department:"Department",state:"Status",joined:"Added on",action:"Action",
      empty:"No matching records. Try another search.",sampleFoot:"Synthetic reference data • no backend",
      reportsTitle:"Status summary",reportsBody:"A live report from the example records, updated whenever you add a person or change a status.",csv:"Export CSV",
      settingsTitle:"Customize this demo",settingsBody:"Language and appearance updates immediately throughout this reference.",
      changeLanguage:"Change language",changeTheme:"Change appearance",footer:"Apps Factory Design System · Offline visual reference",
      formEyebrow:"NEW SYNTHETIC RECORD",formNote:"This data is never uploaded or saved outside this page.",cancel:"Cancel",save:"Add person",
      toggle:"Toggle status",count:"visible records",saved:"Record added to this demo only",changed:"Status updated in this demo only",
      exported:"Synthetic CSV downloaded",nothing:"No matching records to export"
    }
  };
  const people = [
    {id:"AF-001",name:{ar:"أحمد منصور",en:"Ahmed Mansour"},dept:{ar:"العمليات",en:"Operations"},status:"active",date:"2026-09-23"},
    {id:"AF-002",name:{ar:"مريم حسن",en:"Mariam Hassan"},dept:{ar:"خدمة العملاء",en:"Customer support"},status:"active",date:"2026-09-27"},
    {id:"AF-003",name:{ar:"يوسف إبراهيم",en:"Youssef Ibrahim"},dept:{ar:"التخطيط",en:"Planning"},status:"active",date:"2026-09-29"},
    {id:"AF-004",name:{ar:"ندى خالد",en:"Nada Khaled"},dept:{ar:"المالية",en:"Finance"},status:"pending",date:"2026-10-01"},
    {id:"AF-005",name:{ar:"عمر عادل",en:"Omar Adel"},dept:{ar:"الجودة",en:"Quality"},status:"active",date:"2026-10-03"},
    {id:"AF-006",name:{ar:"سارة محمود",en:"Sara Mahmoud"},dept:{ar:"الموارد البشرية",en:"Human resources"},status:"active",date:"2026-10-07"}
  ];
  let locale = "ar", theme = "light", page = "overview";
  const t = (key) => dictionary[locale][key] || key;
  function element(tag, className, content) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (content !== undefined) node.textContent = String(content);
    return node;
  }
  function labeledDate(value) {
    const bits = value.split("-").map(Number);
    return new Intl.DateTimeFormat(locale==="ar"?"ar-EG":"en-GB",{year:"numeric",month:"short",day:"numeric"}).format(
      new Date(Date.UTC(bits[0],bits[1]-1,bits[2],12,0,0))
    );
  }
  function toast(message) {
    const el=$("toast");
    el.textContent=message;el.hidden=false;
  }
  function clearToast(){$("toast").hidden=true}
  function closeMenu() {
    $("workspace").classList.remove("menu-open");
    $("menuBtn").setAttribute("aria-expanded","false");
    $("mobileShade").hidden=true;
  }
  function switchPage(next) {
    page=next;
    document.querySelectorAll("[data-page]").forEach(button=>{
      const active=button.dataset.page===next;
      button.classList.toggle("active",active);
      if(active)button.setAttribute("aria-current","page");else button.removeAttribute("aria-current");
    });
    const overview=next==="overview";
    document.querySelector("[data-panel=overview]").hidden=!overview;
    document.querySelector("[data-panel=people]").hidden=!(overview||next==="people");
    document.querySelector("[data-panel=reports]").hidden=next!=="reports";
    document.querySelector("[data-panel=settings]").hidden=next!=="settings";
    $("pageTitle").textContent=t(next);
    $("breadcrumb").textContent=t(next);
    $("pageDescription").textContent=t(next+"Desc");
    $("addBtn").hidden=next==="reports"||next==="settings";
    closeMenu(); clearToast();
    window.scrollTo({top:0,behavior:"instant"});
  }
  function translate() {
    root.lang=locale;root.dir=locale==="ar"?"rtl":"ltr";
    document.title=locale==="ar"?"مصنع التطبيقات | مرجع التصميم":"Apps Factory | Design Reference";
    document.querySelectorAll("[data-i18n]").forEach(node=>{
      const label=t(node.dataset.i18n);
      if (label) node.textContent=label;
    });
    document.querySelectorAll("[data-i18n-placeholder]").forEach(node=>node.setAttribute("placeholder",t(node.dataset.i18nPlaceholder)));
    $("langLabel").textContent=locale==="ar"?"EN":"ع";
    $("themeLabel").textContent=t(theme==="dark"?"themeLight":"themeDark");
    $("breadcrumb").textContent=t(page);
    $("pageTitle").textContent=t(page);
    $("pageDescription").textContent=t(page+"Desc");
    $("menuBtn").setAttribute("aria-label",locale==="ar"?"فتح القائمة":"Open navigation");
    render();
  }
  function changeTheme(){
    theme=theme==="light"?"dark":"light";root.dataset.theme=theme;
    $("themeIcon").textContent=theme==="light"?"☾":"☀";
    $("themeBtn").setAttribute("aria-pressed",String(theme==="dark"));
    $("themeLabel").textContent=t(theme==="dark"?"themeLight":"themeDark");
  }
  function changeLanguage(){locale=locale==="ar"?"en":"ar";translate()}
  function filtered(){
    const query=$("search").value.trim().toLocaleLowerCase();
    const status=$("statusFilter").value;
    return people.filter(row=>(status==="all"||row.status===status)&&(
      !query||[row.name.ar,row.name.en,row.dept.ar,row.dept.en,row.id].some(v=>v.toLocaleLowerCase().includes(query))
    ));
  }
  function render(){
    const active=people.filter(p=>p.status==="active").length,pending=people.length-active;
    $("metricTotal").textContent=people.length;
    $("metricActive").textContent=active;
    $("metricPending").textContent=pending;
    $("navCount").textContent=people.length;
    const chart=$("chartBars");chart.replaceChildren();
    for(const [value,type] of [[active,"active"],[pending,"pending"]]){
      const bar=element("div","chart-bar");
      bar.style.height=(value?Math.max(7,100*value/Math.max(people.length,1)):5)+"%";
      bar.setAttribute("aria-label",t(type)+": "+value);
      bar.setAttribute("role","img");chart.append(bar);
    }
    const visible=filtered();
    $("recordCount").textContent=visible.length+" "+t("count");
    const tbody=$("peopleRows");tbody.replaceChildren();
    $("empty").hidden=visible.length!==0;
    for(const row of visible){
      const tr=element("tr");
      const tdPerson=element("td"),line=element("div","person-line");
      const avatar=element("div","person-avatar",(row.name[locale]||"A").trim().slice(0,1));
      avatar.setAttribute("aria-hidden","true");
      const info=element("div","person-info");info.append(element("strong","",row.name[locale]),element("span","person-id",row.id));
      line.append(avatar,info);tdPerson.append(line);
      const tdDep=element("td","",row.dept[locale]);
      const tdStatus=element("td");
      const badge=element("span","af-badge",t(row.status));badge.dataset.tone=row.status==="active"?"positive":"warning";tdStatus.append(badge);
      const tdDate=element("td","",labeledDate(row.date));
      const tdAction=element("td");
      const action=element("button","action-link",t("toggle"));
      action.type="button";action.dataset.toggleId=row.id;
      action.setAttribute("aria-label",t("toggle")+": "+row.name[locale]);
      tdAction.append(action);tr.append(tdPerson,tdDep,tdStatus,tdDate,tdAction);tbody.append(tr);
    }
    const report=$("reportStats");report.replaceChildren();
    for(const [label,num] of [[t("total"),people.length],[t("active"),active],[t("pending"),pending]]){
      const box=element("div","report-stat");box.append(element("strong","",num),element("span","",label));report.append(box);
    }
  }
  function safeCsvCell(value){
    let text=String(value);
    if (/^[\s]*[=+\-@]/.test(text)) text="'"+text;
    return '"'+text.replaceAll('"','""')+'"';
  }
  function exportCsv(){
    const rows=filtered();if(!rows.length){toast(t("nothing"));return}
    const data=[["ID",t("person"),t("department"),t("state"),t("joined")],
      ...rows.map(p=>[p.id,p.name[locale],p.dept[locale],t(p.status),p.date])];
    const csv="\ufeff"+data.map(row=>row.map(safeCsvCell).join(",")).join("\r\n")+"\r\n";
    const blob=new Blob([csv],{type:"text/csv;charset=utf-8"});
    const url=URL.createObjectURL(blob);const anchor=element("a");anchor.href=url;anchor.download="apps-factory-demo.csv";
    document.body.append(anchor);anchor.click();anchor.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1500);toast(t("exported"));
  }
  document.querySelectorAll("[data-page]").forEach(el=>el.addEventListener("click",()=>switchPage(el.dataset.page)));
  $("menuBtn").addEventListener("click",()=>{
    const expanded=$("workspace").classList.toggle("menu-open");
    $("menuBtn").setAttribute("aria-expanded",String(expanded));
    $("mobileShade").hidden=!expanded;
  });
  $("mobileShade").addEventListener("click",closeMenu);
  document.addEventListener("keydown",e=>{
    if(e.key==="Escape"&&$("workspace").classList.contains("menu-open"))closeMenu();
  });
  $("langBtn").addEventListener("click",changeLanguage);
  $("settingsLang").addEventListener("click",changeLanguage);
  $("themeBtn").addEventListener("click",changeTheme);
  $("settingsTheme").addEventListener("click",changeTheme);
  $("search").addEventListener("input",render);
  $("statusFilter").addEventListener("change",render);
  $("viewPeople").addEventListener("click",()=>switchPage("people"));
  $("downloadCsv").addEventListener("click",exportCsv);
  $("addBtn").addEventListener("click",()=>{
    $("newPersonForm").reset();$("addDialog").showModal();$("personName").focus()
  });
  $("cancelDialog").addEventListener("click",()=>$("addDialog").close());
  $("newPersonForm").addEventListener("submit",e=>{
    e.preventDefault();
    const name=$("personName").value.trim(),dept=$("personDepartment").value.trim();
    if(name.length<2||!dept){return}
    const id="AF-"+String(people.length+1).padStart(3,"0");
    const date=new Date().toISOString().slice(0,10);
    people.unshift({id,name:{ar:name,en:name},dept:{ar:dept,en:dept},status:$("personState").value,date});
    $("addDialog").close();$("search").value="";$("statusFilter").value="all";
    switchPage("people");render();toast(t("saved"));$("addBtn").focus();
  });
  $("peopleRows").addEventListener("click",e=>{
    const button=e.target.closest("[data-toggle-id]");if(!button)return;
    const row=people.find(r=>r.id===button.dataset.toggleId);if(!row)return;
    row.status=row.status==="active"?"pending":"active";render();toast(t("changed"));
  });
  translate();switchPage("overview");
})();
