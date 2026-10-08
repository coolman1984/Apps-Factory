import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
const base=path.dirname(fileURLToPath(import.meta.url));
export const sources=JSON.parse(fs.readFileSync(path.join(base,'sources.json'),'utf8')).sources;
export function validate(list=sources){
 const issues=[];const ids=new Set();
 for(const s of list){if(!s.id||ids.has(s.id))issues.push('duplicate/missing id: '+s.id);ids.add(s.id);if(!/^https:\/\/[^\s]+$/.test(s.url||''))issues.push('invalid URL: '+s.id);if(typeof s.enabled!=='boolean')issues.push('invalid enabled: '+s.id);if(!s.license||!s.category)issues.push('missing metadata: '+s.id);}
 if(list.find(s=>s.id==='inspora')?.enabled!==false)issues.push('unverified Inspora must be disabled');
 return issues;
}
export function recommend(category){const terms={pos:['real-app-ux','motion-reference'],website:['web-inspiration','motion-reference'],video:['showreel-reference','motion-workflow'],app:['real-app-ux','motion-reference']};return sources.filter(s=>s.enabled&&(terms[category]||terms.app).includes(s.category));}
export function report(category='app'){return {generatedAt:new Date().toISOString(),category,mode:'offline-reference-registry',sources:recommend(category).map(({id,url,category,purpose,license})=>({id,url,category,purpose,license})),limitations:['No website was crawled','No screenshots were inspected','No design changes were automatically applied','Copyrighted media must not be copied'],nextSteps:['Capture real application screens','Inspect reference sources with permission','Implement one tested design slice','Run responsive, RTL and accessibility checks']};}
if(process.argv[1]&&path.resolve(process.argv[1])===fileURLToPath(import.meta.url)){
 const issues=validate();if(issues.length){console.error(issues.join('\n'));process.exitCode=1;}else{const category=process.argv[2]||'app';if(!['app','pos','website','video'].includes(category)){console.error('Usage: node engine.mjs [app|pos|website|video]');process.exitCode=2;}else console.log(JSON.stringify(report(category),null,2));}
}
