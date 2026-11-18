// Run with: node --test jarvis-staging/tests/briefing.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const source=await readFile(new URL('../site/briefing.js',import.meta.url),'utf8');
const {classifyCommand,trustedCommand,recentVerification,dailyBriefing}=await import('data:text/javascript;base64,'+Buffer.from(source).toString('base64'));
const now=new Date('2026-11-18T08:00:00Z'); // 4 AM in Puerto Rico
const synced=now.getTime()-10000;
const fixtures=[
 {title:'Informe atrasado',status:'pending',priority:'high',due_at:'2026-11-17T15:00:00Z'},
 {title:'Enviar documento',status:'pending',priority:'normal',due_at:'2026-11-18T14:00:00Z'},
 {title:'Llamada terminada',status:'done',priority:'high',due_at:'2026-11-18T10:00:00Z'},
 {title:'Estudiar inglés',status:'pending',priority:'low',due_at:null}
];
const ctx={tasks:fixtures,loaded:true,verifiedAt:synced,now};
test('Bilingual daily briefing recognition',()=>{
 for(const phrase of ['What I got to do today?','What do I have today?','Jarvis, what I got to do today?','Planifica mi día','Qué tengo hoy']){
  assert.equal(classifyCommand(phrase),'brief',phrase);
 }
});
test('Meetings need a real calendar',()=>{
 for(const phrase of ['Do I have any meetings?','¿Tengo reuniones hoy?','¿Qué reuniones tengo hoy?']){
  const answer=trustedCommand(phrase,ctx);
  assert.ok(answer?.text.includes('calendario')||answer?.text.includes('calendar'));
  assert.ok(!answer.text.includes('9:00'));
 }
});
test('Departure time is never guessed',()=>{
 for(const phrase of ['What time should I leave?','¿A qué hora debería salir?','When should I leave?']){
  const answer=trustedCommand(phrase,ctx);
  assert.ok(answer);
  assert.match(answer.text,/no puedo calcular|cannot calculate/i);
 }
});
test('Verified, unsynced and stale states',()=>{
 assert.equal(recentVerification(synced,now.getTime()),true);
 assert.equal(recentVerification(now.getTime()-900000,now.getTime()),false);
 assert.equal(recentVerification(now.getTime()+10000,now.getTime()),false);
 assert.match(trustedCommand('Qué tengo hoy',{...ctx,loaded:false}).text,/No puedo verificar/);
 assert.match(trustedCommand('Qué tengo hoy',{...ctx,verifiedAt:now.getTime()-3600000}).text,/datos recientes/);
});
test('Four AM briefing never invents meetings',()=>{
 const result=trustedCommand('What do I have today?',ctx);
 assert.equal(result.language,'en');
 assert.match(result.text,/3 pending/);
 assert.match(result.text,/1 overdue/);
 assert.match(result.text,/1 due later today/);
 assert.match(result.text,/not appointments/);
 assert.ok(!result.text.includes('Llamada terminada'));
});
test('Missing dates are not treated as scheduled appointments',()=>{
 const result=dailyBriefing({...ctx,tasks:[{title:'Meeting idea',status:'pending',due_at:null}]});
 assert.match(result,/1 pendientes/);
 assert.match(result,/no puedo confirmar reuniones/);
});
test('Empty task list is not an empty verified calendar',()=>{
 const result=dailyBriefing({...ctx,tasks:[]});
 assert.match(result,/No hay tareas pendientes registradas/);
 assert.match(result,/calendario/);
});
test('Unrelated local commands stay available',()=>{
 for(const phrase of ['Recuerda que estudio los sábados','Agrega tarea comprar café','Qué recuerdas de mí']){
  assert.equal(classifyCommand(phrase),null);
 }
});
test('Rendering avoids dangerous HTML assignment',async()=>{
 const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');
 const html=await readFile(new URL('../site/index.html',import.meta.url),'utf8');
 assert.ok(!/\binnerHTML\s*=/.test(app));
 assert.match(app,/import \{trustedCommand,recentVerification\} from '.\/briefing\.js'/);
 for(const id of ['source-tasks','source-memory','source-calendar','source-traffic','recognition-lang']){
  assert.ok(html.includes('id="'+id+'"'),'Missing '+id);
 }
});

test('Puerto Rico day boundaries are independent of browser timezone',()=>{
 const t=new Date('2026-11-18T03:30:00Z'); // Nov 17, 11:30 PM PR
 const base={loaded:true,verifiedAt:t.getTime()-1000,now:t};
 const today=dailyBriefing({...base,tasks:[{title:'Before midnight',status:'pending',due_at:'2026-11-18T03:45:00Z'}]});
 const tomorrow=dailyBriefing({...base,tasks:[{title:'After midnight',status:'pending',due_at:'2026-11-18T04:15:00Z'}]});
 assert.match(today,/1 con vencimiento más tarde hoy/);
 assert.match(tomorrow,/0 con vencimiento más tarde hoy/);
});
test('Naive and date-only timestamps are not invented deadlines',()=>{
 const t=new Date('2026-11-18T08:00:00Z');
 const base={loaded:true,verifiedAt:t.getTime()-1000,now:t};
 for(const due_at of ['2026-11-18T09:00:00','2026-11-18','tomorrow']){
  const response=dailyBriefing({...base,tasks:[{title:'Unverified deadline',status:'pending',due_at}]});
  assert.match(response,/0 con vencimiento más tarde hoy/);
  assert.ok(!response.includes('vence '));
 }
});

test('Impossible dates, overflow hours and invalid offsets are not confirmed deadlines',()=>{
 const t=new Date('2026-11-18T08:00:00Z');
 const base={loaded:true,verifiedAt:t.getTime()-1000,now:t};
 for(const due_at of ['2026-02-30T09:00:00Z','2026-13-01T09:00:00Z','2026-11-18T25:00:00Z','2026-11-18T09:00:00+24:00','2026-11-18T09:00:00+04:60','2026-11-18T09:00:00Zextra']){
  const result=dailyBriefing({...base,tasks:[{title:'Invalid',status:'pending',due_at}]});
  assert.match(result,/0 con vencimiento más tarde hoy/,due_at);
  assert.ok(!result.includes('vence '),due_at);
 }
 for(const due_at of ['2026-11-18T09:00:00Z','2026-11-18T09:00:00-04:00','2024-02-29T09:00:00Z']){
  const result=dailyBriefing({...base,tasks:[{title:'Valid',status:'pending',due_at}]});
  assert.match(result,/vence /,due_at);
 }
});
