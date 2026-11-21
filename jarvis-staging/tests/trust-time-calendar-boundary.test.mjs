import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, trustedCommand} from '../site/briefing.js';
const now=new Date('2026-11-21T03:59:00.000Z'); // Nov 20 23:59 Puerto Rico
const tasks=[{title:'Preparar informe',status:'pending',priority:'normal',due_at:'2026-11-21T00:30:00-04:00'}];
test('Puerto Rico local date, not UTC date, determines due-today',()=>{
 const out=dailyBriefing({tasks,loaded:true,verifiedAt:now.getTime(),now});
 assert.match(out,/0 con vencimiento más tarde hoy/);
 assert.match(out,/1 pendientes/);
 assert.match(out,/no puedo confirmar reuniones ni horas de salida/i);
});
test('unverified calendar questions do not echo private task titles',()=>{
 const out=trustedCommand('¿Tengo una cita mañana?',{tasks,loaded:true,verifiedAt:now.getTime(),now});
 assert.equal(out.language,'es');
 assert.doesNotMatch(out.text,/Preparar informe/);
 assert.match(out.text,/calendario/);
});
test('departure does not derive durations from task data',()=>{
 const out=trustedCommand('When should I leave?',{tasks,loaded:true,verifiedAt:now.getTime(),now});
 assert.equal(out.language,'en');
 assert.match(out.text,/cannot calculate a reliable departure time/);
 assert.doesNotMatch(out.text,/00:30|Preparar informe/);
});
