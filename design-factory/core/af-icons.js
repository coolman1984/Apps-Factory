/* Apps Factory original icon vocabulary v1.0.0. Built from primitive geometry; no vendor assets.
   Uses SVG DOM API, controlled allowlisted names, no unsafe HTML strings or remote dependencies. */
"use strict";
(function(window,document){
  const NS="http://www.w3.org/2000/svg";
  const icons=Object.freeze({
    layers:["M12 3 3 8l9 5 9-5-9-5Z","M3 12l9 5 9-5","M3 16l9 5 9-5"],
    orbit:["M12 12m-8 0a8 8 0 1 0 16 0a8 8 0 1 0-16 0","M2.9 7.5c4.2 4.9 10.4 8.1 18.3 9.1","M7 3c-1.8 4.1-1.5 11.6 2.3 17.5"],
    spark:["M12 2l2.5 7.5L22 12l-7.5 2.5L12 22l-2.5-7.5L2 12l7.5-2.5L12 2Z"],
    film:["M3 4h18v16H3z","M7 4v16","M17 4v16","M3 9h4","M3 15h4","M17 9h4","M17 15h4"],
    camera:["M3 7h18v12H3z","M8 7l2-3h4l2 3","M12 13m-3 0a3 3 0 1 0 6 0a3 3 0 1 0-6 0"],
    cube:["M12 2 3 7v10l9 5 9-5V7L12 2Z","M3 7l9 5 9-5","M12 12v10"],
    timeline:["M3 5h18","M3 19h18","M6 12h12","M9 9v6","M15 9v6"],
    palette:["M12 2a10 10 0 0 0 0 20h2a2 2 0 0 0 1-4l-1-1a2 2 0 0 1 1-3h4a3 3 0 0 0 3-3A10 10 0 0 0 12 2Z","M7 9h.1","M9 6h.1","M14 6h.1","M17 9h.1"],
    wave:["M2 12c2.4-7 4.6-7 7 0s4.6 7 7 0 4.6-7 6 0"],
    motion:["M3 17c3-4 5-5 9-5","M8 8l4 4-4 4","M15 7h6","M15 12h4","M15 17h6"],
    play:["M7 4 20 12 7 20V4Z"],
    pause:["M6 4h4v16H6z","M14 4h4v16h-4z"],
    diamond:["M12 2 22 12 12 22 2 12 12 2Z","M12 6v12","M6 12h12"],
    focus:["M9 3H5a2 2 0 0 0-2 2v4","M15 3h4a2 2 0 0 1 2 2v4","M3 15v4a2 2 0 0 0 2 2h4","M21 15v4a2 2 0 0 1-2 2h-4","M9 12h6"]
  });
  function make(name,options){
    if(!Object.hasOwn(icons,name))throw new RangeError("Unknown original Apps Factory icon: "+name);
    const opts=options||{};
    const size=Math.min(160,Math.max(12,Number(opts.size)||24));
    const strokeWidth=Math.min(3.5,Math.max(.8,Number(opts.stroke)||1.8));
    const svg=document.createElementNS(NS,"svg");
    svg.setAttribute("xmlns",NS);
    svg.setAttribute("viewBox","0 0 24 24");
    svg.setAttribute("width",String(size));
    svg.setAttribute("height",String(size));
    svg.setAttribute("fill","none");
    svg.setAttribute("stroke","currentColor");
    svg.setAttribute("stroke-width",String(strokeWidth));
    svg.setAttribute("stroke-linecap","round");
    svg.setAttribute("stroke-linejoin","round");
    svg.style.display="inline-block";
    svg.style.verticalAlign="middle";
    if(opts.label){
      svg.setAttribute("role","img");
      const title=document.createElementNS(NS,"title");title.textContent=String(opts.label);
      svg.append(title);
    }else{svg.setAttribute("aria-hidden","true")}
    for(const d of icons[name]){
      const path=document.createElementNS(NS,"path");path.setAttribute("d",d);svg.append(path);
    }
    return svg;
  }
  function mount(element,name,options){
    if(!(element instanceof Element))throw new TypeError("Expected DOM element");
    const icon=make(name,options);element.replaceChildren(icon);return icon;
  }
  window.AFCreativeIcons=Object.freeze({list:()=>Object.keys(icons),create:make,mount,version:"1.0.0"});
})(window,document);
