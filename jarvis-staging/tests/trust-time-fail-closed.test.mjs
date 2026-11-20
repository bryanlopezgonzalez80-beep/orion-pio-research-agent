import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, trustedCommand, recentVerification} from '../site/briefing.js';

const now = new Date('2026-11-20T16:00:00Z');
const stale = now.getTime() - 15 * 60 * 1000;

test('expired or future task verification never becomes a confirmed agenda', () => {
  for (const verifiedAt of [null, stale, now.getTime() + 1000]) {
    const answer = dailyBriefing({tasks:[{title:'Meeting at 9',status:'pending'}],loaded:true,verifiedAt,now});
    assert.match(answer, /No puedo verificar tus tareas/);
    assert.doesNotMatch(answer, /1 pendientes|Prioridades sugeridas/);
    assert.equal(recentVerification(verifiedAt,now.getTime()),false);
  }
});

test('task titles cannot establish a calendar meeting or departure time', () => {
  const context={tasks:[{title:'Reunión a las 9:00, viaje 15 minutos',status:'pending'}],loaded:true,verifiedAt:now.getTime(),now};
  for (const question of ['¿Tengo una reunión mañana?', 'Do I have any meetings tomorrow?']) {
    const response=trustedCommand(question,context);
    assert.equal(response?.language,question.startsWith('Do')?'en':'es');
    assert.match(response.text,/calendario|calendar/i);
    assert.doesNotMatch(response.text,/9:00|15 minutos/);
  }
  for (const question of ['¿A qué hora debo salir?', 'When should I leave?']) {
    const response=trustedCommand(question,context);
    assert.match(response.text,/no puedo calcular|cannot calculate/i);
    assert.doesNotMatch(response.text,/9:00|15 minutos/);
  }
});

test('invalid or timezone-naive task deadlines do not become confirmed due times', () => {
  const text=dailyBriefing({tasks:[
    {title:'Fecha sin zona',status:'pending',due_at:'2026-11-20T09:00:00'},
    {title:'Fecha imposible',status:'pending',due_at:'2026-02-30T09:00:00Z'}
  ],loaded:true,verifiedAt:now.getTime(),now});
  assert.match(text,/2 pendientes/);
  assert.doesNotMatch(text,/vence /);
});
