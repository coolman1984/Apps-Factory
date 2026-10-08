/* Browser-driven design QA. Screenshots are evidence, not automatic proof of beauty. */
import { chromium } from "playwright";
import { fileURLToPath, pathToFileURL } from "node:url";
import { dirname, join, resolve } from "node:path";
import { mkdir, writeFile } from "node:fs/promises";
import assert from "node:assert/strict";

const folder=resolve(dirname(fileURLToPath(import.meta.url)),"..");
const site=pathToFileURL(join(folder,"reference","index.html")).href;
const destination=join(folder,"artifacts");
await mkdir(destination,{recursive:true});
const browser=await chromium.launch({headless:true});
const summary={source:site,checks:[],screenshots:[],skipped:[],timestamp:new Date().toISOString()};
let errors=[];
async function check(name, fn){
  try{await fn();summary.checks.push({name,result:"PASS"});console.log("PASS",name)}
  catch(error){errors.push(name+": "+error.message);summary.checks.push({name,result:"FAIL",message:error.message});console.error("FAIL",name,error.message)}
}
try{
  const page=await browser.newPage({viewport:{width:1440,height:900},deviceScaleFactor:1});
  let network=[];
  page.on("request",request=>{if(/^https?:\/\//.test(request.url()))network.push(request.url())});
  await check("open local HTML",async()=>{
    const response=await page.goto(site,{waitUntil:"load"});
    assert.equal(response?.status(),200);
    assert.equal(await page.locator("#peopleRows tr").count(),6);
    assert.equal(await page.locator("#metricTotal").textContent(),"6");
  });
  await check("language switching and RTL",async()=>{
    assert.equal(await page.locator("html").getAttribute("dir"),"rtl");
    await page.locator("#langBtn").click();
    assert.equal(await page.locator("html").getAttribute("dir"),"ltr");
    assert.equal(await page.locator("#pageTitle").textContent(),"Overview");
    await page.locator("#langBtn").click();
    assert.equal(await page.locator("html").getAttribute("dir"),"rtl");
  });
  await check("functional creation, filtering and status",async()=>{
    await page.locator("#addBtn").click();
    await page.locator("#personName").fill("سلمى التجربة");
    await page.locator("#personDepartment").fill("الجودة");
    await page.locator("#personState").selectOption("pending");
    await page.locator("#newPersonForm button[type=submit]").click();
    assert.equal(await page.locator("#metricTotal").textContent(),"7");
    assert.equal(await page.locator("#peopleRows tr").count(),7);
    await page.locator("#search").fill("سلمى");
    assert.equal(await page.locator("#peopleRows tr").count(),1);
    await page.locator("#peopleRows button[data-toggle-id]").click();
    assert.equal(await page.locator("#metricActive").textContent(),"6");
    await page.locator("#search").fill("does-not-exist");
    assert.equal(await page.locator("#empty").isVisible(),true);
  });
  await check("actual report navigation",async()=>{
    await page.locator("[data-page=reports]").click();
    assert.equal(await page.locator("#downloadCsv").isVisible(),true);
    assert.equal(await page.locator("#addBtn").isVisible(),false);
    await page.locator("[data-page=settings]").click();
    assert.equal(await page.locator("#settingsTheme").isVisible(),true);
  });
  await check("no external network requests",async()=>{
    assert.deepEqual(network,[]);
  });

  const viewports=[{name:"desktop",width:1440,height:900},{name:"tablet",width:768,height:1024},{name:"phone",width:390,height:844}];
  for(const viewport of viewports){
    for(const lang of ["ar","en"]){
      for(const theme of ["light","dark"]){
        const name=`${viewport.name}-${lang}-${theme}`;
        await check("visual render "+name,async()=>{
          await page.setViewportSize({width:viewport.width,height:viewport.height});
          await page.goto(site,{waitUntil:"load"});
          if(lang==="en")await page.locator("#langBtn").click();
          if(theme==="dark")await page.locator("#themeBtn").click();
          assert.equal(await page.locator("html").getAttribute("dir"),lang==="ar"?"rtl":"ltr");
          assert.equal(await page.locator("html").getAttribute("data-theme"),theme);
          const horizontal=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
          assert.ok(horizontal.scroll<=horizontal.viewport+2,`page overflow: ${JSON.stringify(horizontal)}`);
          const path=join(destination,`${name}.png`);
          await page.screenshot({path,fullPage:true,animations:"disabled"});
          summary.screenshots.push(name+".png");
        });
      }
    }
  }
  await check("phone navigation opens and closes",async()=>{
    await page.setViewportSize({width:390,height:844});
    await page.goto(site);
    await page.locator("#menuBtn").click();
    assert.equal(await page.locator("#menuBtn").getAttribute("aria-expanded"),"true");
    await page.keyboard.press("Escape");
    assert.equal(await page.locator("#menuBtn").getAttribute("aria-expanded"),"false");
  });
  await page.close();
}catch(error){errors.push("unexpected: "+error.stack);console.error(error)}
finally{
  summary.errors=errors;
  await writeFile(join(destination,"report.json"),JSON.stringify(summary,null,2)+"\n",{encoding:"utf8"});
  await browser.close();
}
if(errors.length){console.error(errors.join("\n"));process.exitCode=1}
else console.log("Design Factory browser smoke passed; 12 screenshots captured. Human aesthetic review STILL REQUIRED.");
