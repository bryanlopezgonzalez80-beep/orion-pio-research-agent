import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand, BRIEFING_TIME_ZONE } from '../site/briefing.js';

const now = new Date('2026-11-21T03:30:00.000Z'); // Nov 20, 23:30 in Puerto Rico
const verifiedAt = now.getTime();

test('Puerto Rico calendar day does not silently follow UTC day', () => {
  assert.equal(BRIEFING_TIME_ZONE, 'America/Puerto_Rico');
  const tasks = [{title:'Entrega nocturna',status:'pending',due_at:'2026-11-20T23:45:00-04:00'}];
  const text = dailyBriefing({tasks,loaded:true,verifiedAt,now});
  assert.match(text,/1 con vencimiento más tarde hoy/);
  assert.match(text,/Entrega nocturna/);
});

test('briefing and trusted command do not mutate private task records', () => {
  const tasks = Object.freeze([
    Object.freeze({title:'Revisar informe',status:'pending',priority:'high',due_at:'2026-11-21T09:00:00-04:00'}),
    Object.freeze({title:'Tarea terminada',status:'done',due_at:null})
  ]);
  const context = Object.freeze({tasks,loaded:true,verifiedAt,now});
  const first = dailyBriefing(context);
  const second = trustedCommand('¿Qué tengo hoy?',context);
  assert.equal(second?.text,first);
  assert.equal(tasks[0].title,'Revisar informe');
  assert.equal(tasks[0].status,'pending');
  assert.equal(tasks[1].status,'done');
});

test('missing calendar or traffic is not replaced by task-title evidence', () => {
  const tasks = [{title:'Reunión confirmada a las 9; salir en 20 minutos',status:'pending'}];
  const context = {tasks,loaded:true,verifiedAt,now};
  const calendar = trustedCommand('¿Tengo reuniones mañana?',context);
  const travel = trustedCommand('¿A qué hora debo salir?',context);
  assert.equal(calendar?.language,'es');
  assert.match(calendar?.text??'',/no puedo confirmar citas ni reuniones/i);
  assert.doesNotMatch(calendar?.text??'',/20 minutos|a las 9/i);
  assert.match(travel?.text??'',/no puedo calcular una hora fiable/i);
  assert.doesNotMatch(travel?.text??'',/20 minutos|a las 9/i);
});
