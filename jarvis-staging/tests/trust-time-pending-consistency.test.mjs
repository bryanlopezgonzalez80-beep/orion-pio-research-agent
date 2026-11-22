// Run: node --test jarvis-staging/tests/trust-time-pending-consistency.test.mjs
// Uses synthetic task data. No network, credentials or database mutations.
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';

const briefingSource=await readFile(new URL('../site/briefing.js',import.meta.url),'utf8');
const {pendingTaskRecords,dailyBriefing}=await import('data:text/javascript;charset=utf-8,'+encodeURIComponent(briefingSource));
const appSource=await readFile(new URL('../site/app.js',import.meta.url),'utf8');

// Evaluate only the pure local command handler with mocked dependencies,
// not the DOM application or any Supabase/Render calls.
function isolatedLocalCommand(tasks,proposals=[]){
  const start=appSource.indexOf('function localCommand(');
  const end=appSource.indexOf('async function processMessage(',start);
  assert.ok(start!==-1&&end>start,'local command handler exists');
  const factory=new Function(
    'state','trustedCommand','normalize','sourceIsRecent','propose','request','toDate','localDayPlan','pendingTaskRecords',
    appSource.slice(start,end)+'\nreturn localCommand;'
  );
  const state={tasks,memories:[],replyLanguage:'es'};
  const normalize=value=>value.toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim();
  return factory(state,()=>null,normalize,()=>true,description=>proposals.push(description),()=>{throw Error('Unexpected network request')},()=>null,()=>null,pendingTaskRecords);
}
const fixtures=[
  {id:1,title:'CANCELLED_SENTINEL',status:'cancelled'},
  {id:2,title:'CANCELED_SENTINEL',status:'canceled'},
  {id:3,title:'DONE_SENTINEL',status:'done'},
  {id:4,title:'ARCHIVED_SENTINEL',status:'archived'},
  {id:5,title:'CURRENT_SENTINEL',status:'pending',priority:'high'}
];

test('Shared pending-task rule excludes cancelled, done and archived tasks',()=>{
  assert.deepEqual(pendingTaskRecords(fixtures).map(x=>x.title),['CURRENT_SENTINEL']);
  assert.deepEqual(pendingTaskRecords(null),[]);
  assert.deepEqual(pendingTaskRecords([{title:'Legacy',status:null}]).map(x=>x.title),['Legacy']);
});

test('Trust briefing never announces cancelled tasks as pending',()=>{
  const result=dailyBriefing({tasks:fixtures,loaded:true,verifiedAt:Date.UTC(2026,10,22,18,59),now:new Date(Date.UTC(2026,10,22,19,0))});
  assert.match(result,/1 pendientes/);
  assert.match(result,/CURRENT_SENTINEL/);
  for(const item of fixtures.slice(0,4))assert.doesNotMatch(result,new RegExp(item.title));
});

test('Dashboard and local voice summaries share the safe pending classification',()=>{
  assert.match(appSource,/const pending=pendingTaskRecords\(state\.tasks\)/);
  assert.match(appSource,/state\.tasks\.filter\(x=>x\?\.status==='done'\)\.length/);
  const run=isolatedLocalCommand(fixtures);
  for(const phrase of ['resumen','mis pendientes']){
    const reply=run(phrase);
    assert.match(reply,/CURRENT_SENTINEL/);
    for(const item of fixtures.slice(0,4))assert.doesNotMatch(reply,new RegExp(item.title),phrase);
  }
  assert.match(run('resumen'),/1 tarea\(s\) pendiente\(s\)/);
});

test('Voice completion cannot propose writing cancelled or finished tasks',()=>{
  const proposals=[];
  const run=isolatedLocalCommand(fixtures,proposals);
  for(const title of ['CANCELLED_SENTINEL','CANCELED_SENTINEL','DONE_SENTINEL','ARCHIVED_SENTINEL']){
    assert.match(run('completa tarea '+title),/No encontré una tarea pendiente/);
  }
  assert.equal(proposals.length,0);
  assert.match(run('completa tarea CURRENT_SENTINEL'),/lista para completar/);
  assert.equal(proposals.length,1);
});
