// Reproduce: node --test jarvis-staging/tests/freshness-ui.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');
const briefing=await readFile(new URL('../site/briefing.js',import.meta.url),'utf8');
const {recentVerification,MAX_TASK_AGE_MS}=await import('data:text/javascript;base64,'+Buffer.from(briefing).toString('base64'));
test('freshness expires after fifteen minutes without network requests',()=>{
 const now=Date.UTC(2026,10,18,3,50);
 assert.equal(MAX_TASK_AGE_MS,900000);
 assert.equal(recentVerification(now-899999,now),true);
 assert.equal(recentVerification(now-900000,now),false);
 assert.equal(recentVerification(now-900001,now),false);
 assert.equal(recentVerification(now+1,now),false);
 assert.equal(recentVerification(null,now),false);
});
test('dashboard counters cannot present stale tasks as verified',()=>{
 for(const expression of [
  "sourceIsRecent('tasks')?String(pending.length)+' pendientes':'Sin verificar'",
  "sourceIsRecent('tasks')?String(pending.length):'—'",
  "sourceIsRecent('tasks')?String(pending.filter(x=>x.priority==='high').length):'—'",
  "sourceIsRecent('tasks')?String(state.tasks.length-pending.length):'—'"
 ])assert.ok(app.includes(expression),expression);
});
test('stale lists and memory counts fail closed',()=>{
 assert.match(app,/if\(!sourceIsRecent\('tasks'\)\)\{root\.append\(element\('li','empty','Tareas sin verificación reciente/);
 assert.match(app,/if\(!sourceIsRecent\('memories'\)\)\{root\.append\(element\('li','empty','Memoria sin verificación reciente/);
 assert.match(app,/sourceIsRecent\('memories'\)\?String\(state\.memories\.length\):'—'/);
});
test('returning from background refreshes trust labels and list counts',()=>{
 assert.match(app,/document\.addEventListener\('visibilitychange',\(\)=>\{/);
 assert.match(app,/if\(document\.hidden\)\{stopVoice\(\);voiceStatus\(/);
 assert.match(app,/window\.addEventListener\('focus',refreshVisibleTrust\)/);
 assert.match(app,/function refreshVisibleTrust\(\)\{\s*if\(document\.hidden\)return;\s*renderTrust\(\);\s*drawTasks\(\);\s*drawMemories\(\)/);
});
test('focus refresh never silently writes or re-fetches private data',()=>{
 const section=app.slice(app.indexOf('function refreshVisibleTrust(){'),app.indexOf("document.addEventListener('visibilitychange'",app.indexOf('function refreshVisibleTrust(){')));
 assert.ok(!/loadWorkspace\s*\(|request\s*\(|fetch\s*\(|supabase\./.test(section));
 assert.match(section,/Pulsa Actualizar/);
});
