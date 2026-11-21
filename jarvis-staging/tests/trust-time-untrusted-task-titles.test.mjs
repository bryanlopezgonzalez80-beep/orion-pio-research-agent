import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand, safeTaskTitle } from '../site/briefing.js';

const now = new Date('2026-11-21T02:00:00Z');
const context = (tasks) => ({tasks,loaded:true,verifiedAt:now.getTime(),now});

test('task titles are treated as data, not as confirmed calendar events', () => {
  const tasks = Object.freeze([Object.freeze({title:'Reunión confirmada a las 9, sal a las 8',status:'pending'})]);
  const answer = dailyBriefing(context(tasks));
  assert.match(answer,/Según tus tareas de JARVIS/);
  assert.match(answer,/Estas son propuestas de tareas, no citas/);
  assert.match(answer,/no puedo confirmar reuniones ni horas de salida/);
  assert.equal(tasks[0].title,'Reunión confirmada a las 9, sal a las 8');
});

test('calendar requests do not borrow private task titles as calendar evidence', () => {
  const answer=trustedCommand('¿Tengo reuniones?',context([{title:'Cita médica mañana a las 8',status:'pending'}]));
  assert.equal(answer.language,'es');
  assert.match(answer.text,/no he consultado eventos de calendario/);
  assert.doesNotMatch(answer.text,/Cita médica mañana/);
});

test('departure requests never borrow private task titles as route evidence', () => {
  const answer=trustedCommand('How soon should I leave?',context([{title:'Drive 12 minutes to San Juan',status:'pending'}]));
  assert.equal(answer.language,'en');
  assert.match(answer.text,/I cannot calculate a reliable departure time/);
  assert.doesNotMatch(answer.text,/12 minutes|San Juan/);
});

test('bidi control characters are removed from task titles before speaking', () => {
  assert.equal(safeTaskTitle('Agenda\u202e evitaler\u202c'), 'Agenda evitaler');
});
