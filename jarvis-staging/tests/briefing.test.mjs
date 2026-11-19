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

test('Real-world UTC offsets only: UTC−12 through UTC+14',()=>{
 const t=new Date('2026-11-18T08:00:00Z');
 const base={loaded:true,verifiedAt:t.getTime()-1000,now:t};
 for(const due_at of ['2026-11-18T09:00:00+14:01','2026-11-18T09:00:00-12:01','2026-11-18T09:00:00+15:00','2026-11-18T09:00:00-13:00','2026-11-18T09:00:00+00:60','2026-11-18T09:00:00+23:00']){
  const result=dailyBriefing({...base,tasks:[{title:'Invalid offset',status:'pending',due_at}]});
  assert.ok(!result.includes('vence '),due_at);
 }
 for(const due_at of ['2026-11-18T09:00:00+14:00','2026-11-18T09:00:00-12:00','2026-11-18T09:00:00+05:30','2026-11-18T09:00:00Z']){
  const result=dailyBriefing({...base,tasks:[{title:'Valid offset',status:'pending',due_at}]});
  assert.match(result,/vence /,due_at);
 }
});

test('Cancelled tasks are not reported as pending, overdue or upcoming',()=>{
 const tasks=[
  {title:'Cancelled appointment',status:'cancelled',priority:'high',due_at:'2026-11-17T10:00:00Z'},
  {title:'Canceled meeting',status:'canceled',priority:'high',due_at:'2026-11-18T14:00:00Z'},
  {title:'Actual work',status:'pending',priority:'normal',due_at:'2026-11-18T14:00:00Z'}
 ];
 const result=dailyBriefing({...ctx,tasks});
 assert.match(result,/1 pendientes/);
 assert.match(result,/0 atrasadas/);
 assert.match(result,/1 con vencimiento más tarde hoy/);
 assert.ok(!result.includes('Cancelled appointment'));
 assert.ok(!result.includes('Canceled meeting'));
 assert.match(result,/Actual work/);
});

test('Completed and cancelled task statuses are excluded regardless of casing or whitespace',()=>{
 const tasks=['DONE',' Completed ','complete',' CANCELLED ','Canceled','pending'].map((status,i)=>({title:'Task '+i,status,due_at:'2026-11-17T10:00:00Z'}));
 const result=dailyBriefing({...ctx,tasks});
 assert.match(result,/1 pendientes/);
 assert.match(result,/1 atrasadas/);
 assert.ok(result.includes('Task 5'));
 for(let i=0;i<5;i++)assert.ok(!result.includes('Task '+i));
});

test('Priority labels and ordering normalize casing and whitespace',()=>{
 const tasks=[
  {title:'Low priority',status:'pending',priority:' LOW ',due_at:null},
  {title:'High priority',status:'pending',priority:' HIGH ',due_at:null},
  {title:'Normal priority',status:'pending',priority:'normal',due_at:null}
 ];
 const result=dailyBriefing({...ctx,tasks});
 assert.ok(result.indexOf('High priority')<result.indexOf('Normal priority'));
 assert.ok(result.indexOf('Normal priority')<result.indexOf('Low priority'));
 assert.match(result,/High priority, prioridad alta/);
});

test('Natural calendar questions in Spanish and English are never treated as verified meetings',()=>{
 for(const phrase of ['Do I have meetings today?','Jarvis, do I have appointments tomorrow?','¿Tengo alguna reunión hoy?']){
  assert.equal(classifyCommand(phrase),'calendar',phrase);
  const response=trustedCommand(phrase,ctx);
  assert.match(response.text,/calendar|calendario/i,phrase);
  assert.ok(!response.text.includes('9:00'),phrase);
 }
});

test('Briefing task titles cannot inject control characters or multiline speech',()=>{
 const tasks=[{title:'\u0000\u001bEnviar\n\n informe\r\t urgente\u007f',status:'pending',priority:'normal',due_at:null}];
 const result=dailyBriefing({...ctx,tasks});
 assert.match(result,/Enviar informe urgente/);
 assert.ok(!/[\u0000-\u001f\u007f-\u009f]/.test(result));
 assert.ok(!result.includes('Enviar\n'));
});

test('Combined appointments and meetings queries remain calendar-only and fail closed',()=>{
 for(const phrase of ['Do I have any appointments or meetings?','Are there any meetings or appointments today?','Jarvis, do I have meetings and appointments tomorrow?']){
  assert.equal(classifyCommand(phrase),'calendar',phrase);
  const answer=trustedCommand(phrase,ctx);
  assert.equal(answer.language,'en');
  assert.match(answer.text,/calendar is not connected/i);
  assert.doesNotMatch(answer.text,/9:00|confirmed meeting at/i);
 }
});

test('Bidi direction controls in untrusted task titles are removed before spoken briefing',()=>{
 const tasks=[{title:'Enviar\u202e informe\u2066 urgente\u200f',status:'pending',priority:'normal',due_at:null}];
 const result=dailyBriefing({...ctx,tasks});
 assert.match(result,/Enviar informe urgente/);
 assert.doesNotMatch(result,/[\u200e\u200f\u202a-\u202e\u2066-\u2069]/);
});

test('Zero-width and BOM formatting in task titles is removed without changing stored tasks',()=>{
 const original='Enviar\u200b\u200c\u200d\u2060\ufeff informe';
 const task={title:original,status:'pending',priority:'normal',due_at:null};
 const result=dailyBriefing({...ctx,tasks:[task]});
 assert.match(result,/Enviar informe/);
 assert.doesNotMatch(result,/[\u200b-\u200f\u2060\ufeff]/);
 assert.equal(task.title,original);
});

test('Unicode line and paragraph separators do not split voice briefing output',()=>{
 for(const separator of ['\u2028','\u2029']){
  const title='Enviar'+separator+'reporte';
  const task={title,status:'pending',priority:'normal',due_at:null};
  const response=dailyBriefing({...ctx,tasks:[task]});
  assert.match(response,/Enviar reporte/);
  assert.doesNotMatch(response,/[\u2028\u2029]/);
  assert.equal(task.title,title);
 }
});

test('Malformed task records never become fabricated pending commitments',()=>{
 const tasks=[null,4,'fake',false,[],{}, {title:'  ',status:'pending'}, {title:'Real task',status:'pending'}];
 const response=dailyBriefing({...ctx,tasks});
 assert.match(response,/1 pendientes/);
 assert.match(response,/Real task/);
 assert.doesNotMatch(response,/Sin título|fake/);
});

test('Invisible-only task titles cannot become fabricated commitments',()=>{
 const tasks=[{title:'\u200b\u2060\ufeff',status:'pending'},{title:'\u202e\u2066',status:'pending'},{title:'Real task',status:'pending'}];
 const response=dailyBriefing({...ctx,tasks});
 assert.match(response,/1 pendientes/);
 assert.match(response,/Real task/);
 assert.doesNotMatch(response,/Sin título/);
 assert.equal(tasks[0].title,'\u200b\u2060\ufeff');
});

test('Calendar and agenda paraphrases fail closed in Spanish and English',()=>{
 for(const [phrase,language] of [['What is on my calendar today?','en'],["What's on my agenda tomorrow?",'en'],['Show my calendar','en'],['¿Qué tengo en mi calendario hoy?','es'],['Muéstrame mi agenda','es']]){
  const result=trustedCommand(phrase,ctx);
  assert.equal(classifyCommand(phrase),'calendar',phrase);
  assert.equal(result?.language,language,phrase);
  assert.match(result.text,/not connected|no conectado|no está conectado|no está conectad/i,phrase);
  assert.doesNotMatch(result.text,/confirmed at|confirmada a las/i,phrase);
 }
});

test('Only explicitly pending tasks are announced as current commitments',()=>{
 const tasks=[
  {title:'Draft',status:'draft'},
  {title:'Archived',status:'archived'},
  {title:'Blocked',status:'blocked'},
  {title:'Unknown',status:'unexpected'},
  {title:'Current',status:' PENDING '},
  {title:'Legacy task without status'}
 ];
 const result=dailyBriefing({...ctx,tasks});
 assert.match(result,/2 pendientes/);
 assert.match(result,/Current/);
 assert.match(result,/Legacy task without status/);
 for(const title of ['Draft','Archived','Blocked','Unknown'])assert.ok(!result.includes(title),title);
});

test('Bilingual meeting time, location and singular appointment questions fail closed',()=>{
 for(const phrase of ['¿A qué hora es mi reunión?','¿Dónde es mi cita mañana?','¿Tengo una cita hoy?','¿Hay alguna reunión mañana?','What meetings do I have today?','What time is my appointment?','Where is my meeting?','Do I have a meeting tomorrow?']){
  assert.equal(classifyCommand(phrase),'calendar',phrase);
  const answer=trustedCommand(phrase,ctx);
  assert.ok(answer&&/calendar|calendario/i.test(answer.text),phrase);
  assert.doesNotMatch(answer.text,/confirmed at|confirmada a las|9:00/i,phrase);
 }
 for(const phrase of ['Agrega tarea comprar café','¿Qué tengo hoy?','What I got to do today?','¿Cuándo debo salir?']){
  assert.notEqual(classifyCommand(phrase),'calendar',phrase);
 }
});

test('Natural travel-duration questions fail closed without verified route or traffic',()=>{
 for(const phrase of ['How long does it take to get there?','How long will it take to arrive?','How much time does it take to get there?','How much time will it take?']){
  assert.equal(classifyCommand(phrase),'travel',phrase);
  const answer=trustedCommand(phrase,ctx);
  assert.equal(answer?.language,'en',phrase);
  assert.match(answer.text,/cannot calculate a reliable departure time/i,phrase);
  assert.match(answer.text,/live traffic data/i,phrase);
  assert.doesNotMatch(answer.text,/\b\d+ minutes\b|\b\d+ min\b/i,phrase);
 }
});

test('Spanish travel duration paraphrases fail closed without traffic or route',()=>{
 for(const phrase of ['¿Cuánto tiempo tardaré en llegar?','¿Cuánto tiempo tardaría?','¿Cuánto dura el viaje?','¿Cuánto durará el trayecto?','¿Cuánto tiempo se tarda en ir?']){
  assert.equal(classifyCommand(phrase),'travel',phrase);
  const answer=trustedCommand(phrase,ctx);
  assert.equal(answer?.language,'es',phrase);
  assert.match(answer.text,/No puedo calcular una hora fiable para salir/,phrase);
  assert.match(answer.text,/datos reales de tráfico/,phrase);
  assert.doesNotMatch(answer.text,/\\b\\d+ minutos\\b/i,phrase);
 }
 for(const phrase of ['¿Cuánto tiempo tengo para estudiar?','¿Cuánto dura mi tarea?','Agrega tarea comprar café']){
  assert.notEqual(classifyCommand(phrase),'travel',phrase);
 }
});
