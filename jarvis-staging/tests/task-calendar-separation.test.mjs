import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, trustedCommand} from '../site/briefing.js';

// Trust & Time Intelligence: never convert task metadata into calendar confirmation.
// Run: node --test jarvis-staging/tests/task-calendar-separation.test.mjs
const now = new Date('2026-11-23T09:00:00Z');
const verifiedAt = now.getTime();
const task = {title:'Doctor appointment at 9 AM',status:'pending',due_at:'2026-11-23T13:00:00Z',priority:'high'};

test('task suggesting an appointment is not proof of a calendar event (EN/ES)', () => {
  for (const english of [false,true]) {
    const briefing = dailyBriefing({loaded:true,tasks:[task],verifiedAt,now,english});
    assert.match(briefing,english?/not appointments/i:/no citas/i);
    assert.match(briefing,english?/calendar and live traffic are not connected/i:/calendario y el tráfico en vivo no están conectados/i);
    assert.doesNotMatch(briefing,/confirmed meeting|reunión confirmada/i);
  }
});

test('calendar and departure intents cannot borrow times from a task title', () => {
  for (const phrase of ['Do I have any appointments?', '¿Tengo una reunión?']) {
    const result = trustedCommand(phrase,{loaded:true,tasks:[task],verifiedAt,now});
    assert.ok(result);
    assert.doesNotMatch(result.text,/9 AM|09:00|13:00/);
    assert.match(result.text,/not connected|no está conectado/i);
  }
  for (const phrase of ['When should I leave?', '¿A qué hora debo salir?']) {
    const result = trustedCommand(phrase,{loaded:true,tasks:[task],verifiedAt,now});
    assert.ok(result);
    assert.match(result.text,/cannot calculate|No puedo calcular/i);
    assert.doesNotMatch(result.text,/9 AM|09:00|13:00/);
  }
});

test('expired task verification cannot leak task titles through briefing', () => {
  const old = verifiedAt - 15*60*1000;
  for (const english of [false,true]) {
    const answer = dailyBriefing({loaded:true,tasks:[task],verifiedAt:old,now,english});
    assert.doesNotMatch(answer,/Doctor appointment/);
    assert.match(answer,english?/cannot verify your tasks/i:/No puedo verificar tus tareas/i);
  }
});
