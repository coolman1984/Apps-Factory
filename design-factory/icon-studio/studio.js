"use strict";
(()=>{
const icons=window.AFCreativeIcons,$=id=>document.getElementById(id);
const names=icons.list();
let selected="layers";
for(const name of names){const opt=document.createElement("option");opt.value=name;opt.textContent=name;$("name").append(opt)}
$("count").textContent=names.length+" VECTOR SYMBOLS";
function render(){
const size=Number($("size").value),stroke=Number($("stroke").value);
const color=$("color").value;
$("sizeVal").textContent=size;
$("strokeVal").textContent=stroke.toFixed(1);
$("selectedName").textContent=selected;
$("selectedIcon").style.color=color;
icons.mount($("selectedIcon"),selected,{size,stroke,label:selected});
$("gallery").querySelectorAll("[data-icon]").forEach(btn=>btn.setAttribute("aria-pressed",String(btn.dataset.icon===selected)));
}
for(const name of names){
 const button=document.createElement("button");button.type="button";button.className="icon-card";button.dataset.icon=name;
 button.setAttribute("aria-label","اختيار "+name);
 const icon=icons.create(name,{size:30,stroke:1.7});icon.style.color="var(--accent)";
 const text=document.createElement("span");text.textContent=name;button.append(icon,text);
 button.addEventListener("click",()=>{selected=name;$("name").value=name;render()});
 $("gallery").append(button);
}
$("name").addEventListener("change",e=>{selected=e.target.value;render()});
for(const id of ["size","stroke","color"])$(id).addEventListener("input",render);
$("download").addEventListener("click",()=>{
const icon=icons.create(selected,{size:24,stroke:Number($("stroke").value),label:selected});
icon.setAttribute("width","24");icon.setAttribute("height","24");icon.setAttribute("color",$("color").value);
icon.removeAttribute("style");
icon.setAttribute("stroke",$("color").value);
const xml='<?xml version="1.0" encoding="UTF-8"?>\n'+new XMLSerializer().serializeToString(icon);
const url=URL.createObjectURL(new Blob([xml],{type:"image/svg+xml;charset=utf-8"}));
const a=document.createElement("a");a.href=url;a.download="af-"+selected+".svg";document.body.append(a);a.click();a.remove();
setTimeout(()=>URL.revokeObjectURL(url),1000);
$("status").textContent="تم تجهيز الملف "+selected;
});
render();
})();
