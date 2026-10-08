/* Apps Factory Creative v2. Original deterministic scene. Zero network requests/dependencies. */
"use strict";
(() => {
  const root = document.documentElement;
  const $ = (id) => document.getElementById(id);
  const dict = {
    ar: {
      skip:"تخطي إلى الاستوديو",studio:"الاستوديو",principles:"المبادئ",library:"المكتبة",localDemo:"تجربة محلية",
      eyebrow:"بناء المستقبل البصري",headlineA:"اصنع",headlineB:"عمقًا",headlineC:"يتحرك.",
      heroDesc:"طبقات حقيقية، حركة مضبوطة، وانتقالات سينمائية. كلها مصنوعة بالكود، من غير فيديو أو اتصال بالإنترنت.",
      play:"شغّل المشهد",pause:"إيقاف",reduce:"حركة أقل",explore:"جرّب التحكم بنفسك ↗",
      demoNote:"عرض أصلي ببيانات تجريبية • ليس تصويرًا لمنتج",controlLabel:"لوحة التحكم",controlTitle:"المشهد تحت سيطرتك.",
      controlDesc:"جرّب شدة العمق والتحريك، أو أوقف الحركة تمامًا. كل تغيير ينعكس فورًا.",
      ready:"جاهز",style:"الأسلوب البصري",cinematic:"سينمائي متعدد الطبقات",editorial:"هادئ واحترافي",playful:"إبداعي جريء",
      intensity:"شدة العمق",timeline:"المشهد بالثواني",motionPolicy:"إعدادات الحركة",
      export:"تنزيل وصف المشهد",builtIn:"CSS + JavaScript فقط، بدون مكتبات خارجية",
      how:"كيف يعمل",principlesTitle:"مش مؤثرات عشوائية. دي لغة بصرية.",
      depth:"طبقات ذات عمق",depthDesc:"كل مستوى بيتحرك بسرعة محسوبة علشان يدي إحساس بالمسافة، من غير زحمة.",
      motion:"حركة لها معنى",motionDesc:"الانتقالات توجه العين للفكرة الأهم، وتفضل اختيارية للمستخدم.",
      access:"سهولة الوصول أولًا",accessDesc:"المحتوى موجود حتى لو الجهاز ضعيف أو المستخدم قافل الحركة.",
      libraryTitle:"قطعة واحدة. ألف احتمال.",libraryDesc:"نفس الوصفات تتوصل ببرامج ويندوز، ومواقع التسويق، أو استوديو الفيديو حسب نوع المشروع.",
      readDocs:"اقرأ المعمارية ↗",footer:"مشهد أصلي • محلي • قابل لإعادة الاستخدام",
      running:"المشهد شغّال",stopped:"تم إيقاف المشهد",reduced:"تم تفعيل الحركة البسيطة",
      normal:"تم تفعيل الحركة",downloaded:"تم تنزيل وصف المشهد",profileChanged:"تم تغيير الأسلوب"
    },
    en: {
      skip:"Skip to creative lab",studio:"Studio",principles:"Principles",library:"Library",localDemo:"LOCAL DEMO",
      eyebrow:"BUILDING VISUAL FUTURES",headlineA:"MAKE",headlineB:"DEPTH",headlineC:"MOVE.",
      heroDesc:"Real depth planes, considered motion and cinematic transitions. Built entirely with code, without video or internet.",
      play:"Play scene",pause:"Pause",reduce:"Reduce motion",explore:"Explore the controls ↗",
      demoNote:"Original synthetic composition • not real product footage",controlLabel:"THE CONTROL DESK",
      controlTitle:"Direction in your hands.",controlDesc:"Dial in depth, scrub the timeline or pause everything. Every choice is reflected instantly.",
      ready:"READY",style:"Visual direction",cinematic:"Cinematic layered",editorial:"Quiet editorial",playful:"Expressive playful",
      intensity:"Depth intensity",timeline:"Scene timeline",motionPolicy:"Motion controls",
      export:"Export scene recipe",builtIn:"CSS + JavaScript only, no external libraries",
      how:"THE METHOD",principlesTitle:"Not random effects. A visual language.",
      depth:"Perceived depth",depthDesc:"Each plane moves at its own measured speed, creating distance without the noise.",
      motion:"Purposeful motion",motionDesc:"Transitions guide attention to what matters, and remain optional.",
      access:"Access by default",accessDesc:"Everything remains usable when the device is slow or motion is disabled.",
      libraryTitle:"One component. Infinite stories.",
      libraryDesc:"Use the same scene recipes in Windows apps, marketing websites or code-driven film workflows.",
      readDocs:"Read architecture ↗",footer:"Original scene • offline • reusable",
      running:"Scene playing",stopped:"Scene paused",reduced:"Reduced motion enabled",
      normal:"Motion enabled",downloaded:"Scene recipe downloaded",profileChanged:"Visual profile updated"
    }
  };
  const layers=[...document.querySelectorAll("[data-depth]")];
  const profiles={
    cinematic:{scale:1,color:"#a5ffdb",duration:6000},
    editorial:{scale:0.35,color:"#d7e7ff",duration:6000},
    playful:{scale:1.25,color:"#ffc3e4",duration:6000}
  };
  let locale="ar", profile="cinematic", intensity=0.65, t=0;
  let running=false, reduced=false, raf=0, previous=null, pointer={x:0,y:0};
  const duration=6000;
  const media=window.matchMedia?.("(prefers-reduced-motion: reduce)")||{matches:false,addEventListener:()=>{}};
  const shouldReduce=()=>reduced||media.matches;
  const clamp=(n,min,max)=>Math.min(max,Math.max(min,n));
  const smooth=(v)=>v*v*(3-2*v);
  const fmt=(ms)=>"00:"+String(Math.floor(ms/1000)).padStart(2,"0");
  const words=(key)=>dict[locale][key]||key;
  function alertStatus(key){
    const node=$("notice");
    node.textContent=words(key);node.hidden=false;
  }
  function seek(ms){
    t=clamp(Number(ms)||0,0,duration);
    const phase=t/duration;
    const wave=Math.sin(2*Math.PI*phase);
    const rise=smooth(clamp(phase*3,0,1));
    const amount=shouldReduce()?0:intensity*profiles[profile].scale;
    layers.forEach((el,index)=>{
      const depth=Number(el.dataset.depth);
      const px=clamp(pointer.x*depth*amount*26,-36,36);
      const py=clamp(pointer.y*depth*amount*22,-32,32);
      const offset=(wave*(10+index*7)+(rise-1)*13)*depth*amount;
      el.style.setProperty("--parallax-x",px.toFixed(3)+"px");
      el.style.setProperty("--parallax-y",py.toFixed(3)+"px");
      el.style.setProperty("--timeline-x",(offset*.65).toFixed(3)+"px");
      el.style.setProperty("--timeline-y",offset.toFixed(3)+"px");
    });
    const rx=shouldReduce()?0:clamp(-pointer.y*amount*3.5,-5,5);
    const ry=shouldReduce()?0:clamp(pointer.x*amount*4.5,-7,7);
    $("scene").style.setProperty("--rot-x",rx.toFixed(3)+"deg");
    $("scene").style.setProperty("--rot-y",ry.toFixed(3)+"deg");
    $("time").value=String(t);
    $("timeLabel").textContent=(t/1000).toFixed(1)+"s";
    $("sceneTime").textContent=fmt(t)+" / 00:06";
    return {t,profile,intensity,reduced:shouldReduce()};
  }
  function tick(timestamp){
    if(!running)return;
    if(previous===null)previous=timestamp;
    const dt=clamp(timestamp-previous,0,100);
    previous=timestamp;
    seek((t+dt)%duration);
    raf=window.requestAnimationFrame(tick);
  }
  function pause(show=true){
    running=false;
    if(raf)window.cancelAnimationFrame(raf);
    raf=0;previous=null;
    $("play").setAttribute("aria-pressed","false");
    $("playHero").setAttribute("aria-pressed","false");
    if(show)alertStatus("stopped");
  }
  function play(){
    if(shouldReduce()){pause(false);seek(0);alertStatus("reduced");return}
    if(running)return;
    running=true;previous=null;
    $("play").setAttribute("aria-pressed","true");
    $("playHero").setAttribute("aria-pressed","true");
    raf=window.requestAnimationFrame(tick);
    alertStatus("running");
  }
  function updateReduced(flag){
    reduced=Boolean(flag);
    document.body.dataset.reduce=String(reduced);
    $("reduce").setAttribute("aria-pressed",String(reduced));
    if(shouldReduce()){pause(false);seek(0)}
    else seek(t);
    alertStatus(reduced?"reduced":"normal");
  }
  function updateProfile(value){
    if(!Object.hasOwn(profiles,value))return;
    profile=value;
    $("profileName").textContent=value.toUpperCase();
    $("viewport").style.setProperty("--scene-accent",profiles[profile].color);
    $("viewport").dataset.profile=profile;
    alertStatus("profileChanged");
    seek(t);
  }
  function setLang(value){
    if(!Object.hasOwn(dict,value))return;
    locale=value;
    root.lang=locale;
    root.dir=locale==="ar"?"rtl":"ltr";
    $("language").textContent=locale==="ar"?"EN":"ع";
    document.querySelectorAll("[data-i18n]").forEach(el=>{
      const label=words(el.dataset.i18n);if(label)el.textContent=label;
    });
    document.title=locale==="ar"?"مصنع التصميم | معمل الطبقات والحركة":"Creative Factory | Motion & Layers Lab";
  }
  function recipe(){
    return {schema_version:"1.0",id:"creative-factory-depth-scene",category:"layered-hero",
      source:"Apps Factory original Creative Lab",profile,
      layers:layers.map((el,i)=>({id:el.classList[1]||("layer"+i),depth:Number(el.dataset.depth),kind:"dom"})),
      motion:{mode:"deterministic",duration_ms:duration,intensity:Number(intensity.toFixed(2)),
        respects_reduced_motion:true,uses_transform_only:true,animation_default:"paused",
        mobile_fallback:"static_content"},
      export_note:"This is an authoring recipe for an original synthetic demo, not final production UI, video or copyrighted asset pack."};
  }
  function exportRecipe(){
    const blob=new Blob([JSON.stringify(recipe(),null,2)+"\n"],{type:"application/json;charset=utf-8"});
    const url=URL.createObjectURL(blob),a=document.createElement("a");a.href=url;a.download="creative-scene.json";
    document.body.append(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(url),1000);
    alertStatus("downloaded");
  }
  function theme(){
    const current=root.dataset.mode==="light"?"dark":"light";root.dataset.mode=current;
    $("appearance").setAttribute("aria-pressed",String(current==="light"));
  }
  $("language").addEventListener("click",()=>setLang(locale==="ar"?"en":"ar"));
  $("appearance").addEventListener("click",theme);
  $("play").addEventListener("click",play);$("playHero").addEventListener("click",play);
  $("pause").addEventListener("click",()=>pause());
  $("reduce").addEventListener("click",()=>updateReduced(!reduced));
  $("profile").addEventListener("change",event=>updateProfile(event.target.value));
  $("intensity").addEventListener("input",event=>{
    intensity=Number(event.target.value)/100;
    $("intensityLabel").textContent=Math.round(intensity*100)+"%";
    seek(t);
  });
  $("time").addEventListener("input",event=>{pause(false);seek(Number(event.target.value))});
  $("export").addEventListener("click",exportRecipe);
  $("viewport").addEventListener("pointermove",event=>{
    if(shouldReduce())return;
    const r=$("viewport").getBoundingClientRect();
    pointer={x:clamp((event.clientX-r.left)/r.width*2-1,-1,1),
             y:clamp((event.clientY-r.top)/r.height*2-1,-1,1)};
    seek(t);
  },{passive:true});
  $("viewport").addEventListener("pointerleave",()=>{pointer={x:0,y:0};seek(t)});
  document.addEventListener("visibilitychange",()=>{if(document.hidden)pause(false)});
  media.addEventListener?.("change",()=>{if(shouldReduce())pause(false);seek(0)});
  window.__AF_CREATIVE__=Object.freeze({
    seek,play,pause,recipe,getState:()=>({t,profile,intensity,reduced:shouldReduce(),running}),
    setProfile:(value)=>{$("profile").value=value;updateProfile(value)},
    setReduced:updateReduced
  });
  setLang("ar");updateProfile("cinematic");seek(0);
})();
