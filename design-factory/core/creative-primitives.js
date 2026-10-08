/* Apps Factory Creative Primitives v1.0.0 • No third-party runtime, no network.
   Usage: <script src="/creative/creative-primitives.js" defer></script>
   Add .af-depth-scene to scene; children use data-af-depth="0.1" to "1".
   Add .af-soft-in to scroll-reveal content. Motion disabled automatically under reduced motion.
 */
"use strict";
(function(window,document){
  const media=window.matchMedia?window.matchMedia("(prefers-reduced-motion: reduce)"):null;
  const clamp=(n,min,max)=>Math.max(min,Math.min(max,n));
  const instances=new Map();
  let observer=null;
  const reduce=()=>Boolean(media?.matches);
  function normalize(root){
    return root&&typeof root.querySelectorAll==="function"?root:document;
  }
  function setScene(scene,pointer){
    const box=scene.getBoundingClientRect();
    if(!box.width||!box.height)return;
    const x=clamp((pointer.x-box.left)/box.width*2-1,-1,1);
    const y=clamp((pointer.y-box.top)/box.height*2-1,-1,1);
    const intensity=clamp(Number(scene.getAttribute("data-af-intensity")||0.6),0,1);
    scene.querySelectorAll("[data-af-depth]").forEach(child=>{
      const depth=clamp(Number(child.getAttribute("data-af-depth")||0),0,1);
      child.style.setProperty("--af-shift-x",(x*depth*intensity*22).toFixed(2)+"px");
      child.style.setProperty("--af-shift-y",(y*depth*intensity*16).toFixed(2)+"px");
    });
  }
  function resetScene(scene){
    scene.querySelectorAll("[data-af-depth]").forEach(child=>{
      child.style.setProperty("--af-shift-x","0px");
      child.style.setProperty("--af-shift-y","0px");
    });
  }
  function observeReveals(root){
    const els=[...root.querySelectorAll(".af-soft-in")];
    if(!els.length)return;
    if(!("IntersectionObserver" in window)||reduce()){
      els.forEach(x=>x.classList.add("af-soft-in--visible"));
      return;
    }
    if(!observer){
      observer=new IntersectionObserver(records=>{
        records.forEach(record=>{
          if(record.isIntersecting){
            record.target.classList.add("af-soft-in--visible");
            observer.unobserve(record.target);
          }
        });
      },{rootMargin:"0px 0px -25px 0px",threshold:0.08});
    }
    els.forEach(el=>observer.observe(el));
  }
  function init(root){
    const host=normalize(root);
    document.documentElement.classList.add("af-motion-ready");
    host.querySelectorAll(".af-depth-scene").forEach(scene=>{
      if(instances.has(scene))return;
      let raf=0;
      const move=(ev)=>{
        if(reduce()||document.hidden)return;
        if(raf)window.cancelAnimationFrame(raf);
        const xy={x:ev.clientX,y:ev.clientY};
        raf=window.requestAnimationFrame(()=>{raf=0;setScene(scene,xy)});
      };
      const leave=()=>{if(raf)window.cancelAnimationFrame(raf);raf=0;resetScene(scene)};
      scene.addEventListener("pointermove",move,{passive:true});
      scene.addEventListener("pointerleave",leave);
      instances.set(scene,()=>{leave();scene.removeEventListener("pointermove",move);scene.removeEventListener("pointerleave",leave)});
    });
    observeReveals(host);
  }
  function destroy(){
    instances.forEach(clean=>clean());instances.clear();
    if(observer){observer.disconnect();observer=null}
    document.documentElement.classList.remove("af-motion-ready");
  }
  function onMotionChange(){
    if(reduce()){
      instances.forEach((_,scene)=>resetScene(scene));
      document.querySelectorAll(".af-soft-in").forEach(x=>x.classList.add("af-soft-in--visible"));
    }
  }
  media?.addEventListener?.("change",onMotionChange);
  document.addEventListener("visibilitychange",()=>{if(document.hidden)instances.forEach((_,scene)=>resetScene(scene))});
  window.AFCreative=Object.freeze({init,destroy,version:"1.0.0",reducedMotion:reduce});
  if(document.readyState==="loading")document.addEventListener("DOMContentLoaded",()=>init(),{once:true});else init();
})(window,document);
