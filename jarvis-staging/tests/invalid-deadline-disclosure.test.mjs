// Run: node --test jarvis-staging/tests/invalid-deadline-disclosure.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../site/briefing.js',import.meta.url),'utf8');
const {dailyBriefing}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const now=new Date('2026-11-18T08:00:00Z');
const base={loaded:true,verifiedAt:now.getTime()-1000,now};
test('invalid or timezone-less deadlines are disclosed, never spoken as confirmed due times',()=>{
 const tasks=[
  {title:'Naive date',status:'pending',due_at:'2026-11-18T09:00:00'},
  {title:'Impossible date',status:'pending',due_at:'2026-02-30T09:00:00Z'},
  {title:'Valid deadline',status:'pending',due_at:'2026-11-18T14:00:00Z'}
 ];
 const es=dailyBriefing({...base,tasks});
 const en=dailyBriefing({...base,tasks,english:true});
 assert.match(es,/2 fecha\(s\) de vencimiento no se pudieron verificar/);
 assert.match(en,/2 task deadline\(s\) could not be verified/);
 assert.match(es,/1 con vencimiento más tarde hoy/);
 assert.match(en,/1 due later today/);
 assert.doesNotMatch(es,/Naive date, vence|Impossible date, vence/);
 assert.doesNotMatch(en,/Naive date, due|Impossible date, due/);
});
test('null or absent due dates are not falsely flagged as invalid',()=>{
 const tasks=[{title:'Undated',status:'pending',due_at:null},{title:'No field',status:'pending'}];
 const es=dailyBriefing({...base,tasks});
 assert.doesNotMatch(es,/no se pudieron verificar/);
});
test('unverified task data fails closed before discussing individual deadlines',()=>{
 const result=dailyBriefing({...base,verifiedAt:now.getTime()-3600000,tasks:[{title:'Bad',status:'pending',due_at:'tomorrow'}]});
 assert.match(result,/No puedo verificar tus tareas/);
 assert.doesNotMatch(result,/Bad|fecha\(s\) de vencimiento/);
});
