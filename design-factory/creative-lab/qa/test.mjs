/* Browser QA for original Creative Lab. Running this doesn't replace human aesthetic review. */
import {chromium} from "playwright";
import {fileURLToPath,pathToFileURL} from "node:url";
import {dirname,join,resolve} from "node:path";
import {mkdir,writeFile} from "node:fs/promises";
import assert from "node:assert/strict";

const root=resolve(dirname(fileURLToPath(import.meta.url)),"../..");
const file=pathToFileURL(join(root,"creative-lab","index.html")).href;
const folder=join(root,"artifacts","creative-v2");
await mkdir(folder,{recursive:true});
const browser=await chromium.launch({headless:true});
const result={timestamp:new Date().toISOString(),url:file,checks:[],screenshots:[],errors:[],limits:["A human must inspect the screenshots and playback; no artistic quality certification."]};
async function test(name,fn){
  try{await fn();result.checks.push({name,result:"PASS"});console.log("PASS",name)}
  catch(e){result.errors.push(name+": "+e.message);result.checks.push({name,result:"FAIL",error:e.message});console.error("FAIL",name,e.message)}
}
try{
  const page=await browser.newPage({viewport:{width:1440,height:900},acceptDownloads:true,deviceScaleFactor:1});
  const remote=[];
  page.on("request",r=>{if(/^https?:\/\//.test(r.url()))remote.push(r.url())});
  await test("offline load + original 4-layer composition",async()=>{
    await page.goto(file,{waitUntil:"load"});
    assert.equal(await page.locator("[data-depth]").count(),4);
    assert.equal(await page.locator("html").getAttribute("dir"),"rtl");
    const engine=await page.evaluate(()=>typeof window.__AF_CREATIVE__?.seek);
    assert.equal(engine,"function");
    assert.equal(await page.locator("#profileName").textContent(),"CINEMATIC");
  });
  await test("deterministic seek and manual scrub",async()=>{
    await page.locator("#intensity").fill("80");
    await page.locator("#time").fill("1650");
    const a=await page.evaluate(()=>{window.__AF_CREATIVE__.seek(2500);return document.querySelector('[data-depth="0.88"]').getAttribute("style")});
    const b=await page.evaluate(()=>{window.__AF_CREATIVE__.seek(2500);return document.querySelector('[data-depth="0.88"]').getAttribute("style")});
    assert.equal(a,b);
    assert.equal((await page.evaluate(()=>window.__AF_CREATIVE__.getState())).t,2500);
  });
  await test("play + pause + reduced-motion override",async()=>{
    await page.locator("#play").click();
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().running),true);
    await page.locator("#pause").click();
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().running),false);
    await page.locator("#reduce").click();
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().reduced),true);
    await page.locator("#play").click();
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().running),false);
    await page.locator("#reduce").click();
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().reduced),false);
  });
  await test("visual profile switch and export valid JSON",async()=>{
    await page.locator("#profile").selectOption("editorial");
    assert.equal(await page.locator("#profileName").textContent(),"EDITORIAL");
    const waiting=page.waitForEvent("download");
    await page.locator("#export").click();
    const dl=await waiting;
    assert.equal(dl.suggestedFilename(),"creative-scene.json");
    const recipe=await page.evaluate(()=>window.__AF_CREATIVE__.recipe());
    assert.equal(recipe.profile,"editorial");
    assert.equal(recipe.layers.length,4);
    assert.equal(recipe.motion.respects_reduced_motion,true);
  });
  await test("browser OS reduced-motion support",async()=>{
    await page.emulateMedia({reducedMotion:"reduce"});
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().reduced),true);
    await page.locator("#play").click();
    assert.equal(await page.evaluate(()=>window.__AF_CREATIVE__.getState().running),false);
    await page.emulateMedia({reducedMotion:"no-preference"});
  });
  await test("no network/third-party calls",async()=>{
    assert.deepEqual(remote,[]);
  });
  for(const viewport of [{name:"desktop",width:1440,height:900},{name:"tablet",width:768,height:1024},{name:"phone",width:390,height:844}]){
    for(const locale of ["ar","en"]){
      for(const theme of ["dark","light"]){
        const name=viewport.name+"-"+locale+"-"+theme;
        await test("render "+name,async()=>{
          await page.setViewportSize({width:viewport.width,height:viewport.height});
          await page.goto(file,{waitUntil:"load"});
          if(locale==="en")await page.locator("#language").click();
          if(theme==="light")await page.locator("#appearance").click();
          assert.equal(await page.locator("html").getAttribute("dir"),locale==="ar"?"rtl":"ltr");
          assert.equal(await page.locator("html").getAttribute("data-mode"),theme);
          assert.equal(await page.locator("#viewport").isVisible(),true);
          const width=await page.evaluate(()=>({page:document.documentElement.scrollWidth,viewport:window.innerWidth}));
          assert.ok(width.page<=width.viewport+2,"horizontal overflow "+JSON.stringify(width));
          const path=join(folder,name+".png");
          await page.screenshot({path,fullPage:true,animations:"disabled"});
          result.screenshots.push(name+".png");
        });
      }
    }
  }
  await test("keyboard focus and scene accessible",async()=>{
    await page.goto(file);await page.keyboard.press("Tab");
    assert.equal(await page.evaluate(()=>document.activeElement?.classList.contains("skip")),true);
    assert.equal(await page.locator("#viewport").getAttribute("role"),"img");
  });
  await page.close();
}catch(e){result.errors.push("fatal: "+e.stack)}
finally{
  await writeFile(join(folder,"qa-report.json"),JSON.stringify(result,null,2)+"\n");
  await browser.close();
}
console.log("Screenshots captured:",result.screenshots.length);
if(result.errors.length)process.exitCode=1;
else console.log("Creative Lab browser tests PASS; human motion/art direction assessment still required.");
