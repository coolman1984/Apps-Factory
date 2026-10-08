/* Browser QA for actual icon studio render / edit / export, no external requests. */
import {chromium} from "playwright";
import {fileURLToPath,pathToFileURL} from "node:url";
import {dirname,resolve,join} from "node:path";
import {mkdir,writeFile} from "node:fs/promises";
import assert from "node:assert/strict";
const root=resolve(dirname(fileURLToPath(import.meta.url)),"../..");
const file=pathToFileURL(join(root,"icon-studio","index.html")).href;
const output=join(root,"artifacts","icons-v1");
await mkdir(output,{recursive:true});
const browser=await chromium.launch({headless:true});
const report={checks:[],screenshots:[],errors:[],note:"Browser checks and screenshots do not establish artistic approval."};
async function check(name,fn){try{await fn();console.log("PASS",name);report.checks.push({name,result:"PASS"})}catch(e){report.errors.push(name+": "+e.message);console.error("FAIL",name,e.message);report.checks.push({name,result:"FAIL"})}}
try{
const page=await browser.newPage({acceptDownloads:true,viewport:{width:1200,height:850}});
const remote=[];page.on("request",r=>{if(/^https?:\/\//.test(r.url()))remote.push(r.url())});
await check("offline original SVG icon registry",async()=>{
 await page.goto(file,{waitUntil:"load"});
 assert.equal(await page.locator(".gallery .icon-card").count(),14);
 assert.equal(await page.locator("#selectedIcon svg").count(),1);
 assert.equal(await page.locator("#selectedIcon svg path").count(),3);
});
await check("choose different icons and edit vector",async()=>{
 await page.locator('button[data-icon="spark"]').click();
 assert.equal(await page.locator("#selectedName").textContent(),"spark");
 await page.locator("#size").evaluate(el=>{el.value="96";el.dispatchEvent(new Event("input",{bubbles:true}))});
 assert.equal(await page.locator("#selectedIcon svg").getAttribute("width"),"96");
 await page.locator("#stroke").evaluate(el=>{el.value="2.2";el.dispatchEvent(new Event("input",{bubbles:true}))});
 assert.equal(await page.locator("#selectedIcon svg").getAttribute("stroke-width"),"2.2");
});
await check("export SVG original without remote content",async()=>{
 const waiting=page.waitForEvent("download");
 await page.locator("#download").click();
 const dl=await waiting;
 assert.equal(dl.suggestedFilename(),"af-spark.svg");
 assert.deepEqual(remote,[]);
});
for(const viewport of [{name:"desktop",width:1200,height:850},{name:"phone",width:390,height:844}]){
 await check("render icons "+viewport.name,async()=>{
  await page.setViewportSize({width:viewport.width,height:viewport.height});
  const w=await page.evaluate(()=>({scroll:document.documentElement.scrollWidth,viewport:innerWidth}));
  assert.ok(w.scroll<=w.viewport+2,"horizontal overflow "+JSON.stringify(w));
  const path=join(output,viewport.name+".png");await page.screenshot({path,fullPage:true,animations:"disabled"});
  report.screenshots.push(viewport.name+".png");
 });
}
await page.close();
}catch(e){report.errors.push("fatal: "+e.stack)}
finally{await writeFile(join(output,"qa-report.json"),JSON.stringify(report,null,2)+"\n");await browser.close()}
if(report.errors.length)process.exitCode=1;else console.log("Icon Studio interactions, download and responsive checks PASS.");
