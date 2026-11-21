import test from 'node:test';
import assert from 'node:assert/strict';
import { trustedCommand, dailyBriefing } from '../site/briefing.js';

// Trust & Time Intelligence: unavailable providers must never become fabricated events.
test('calendar unavailable: Spanish and English answers disclose missing source', () => {
  for (const [question, language] of [
    ['¿Tengo alguna reunión hoy?', 'es'],
    ['Do I have any appointments?', 'en'],
  ]) {
    const answer = trustedCommand(question, {
      tasks: [{ title: 'Private: meeting at 09:00 in San Juan', status: 'pending' }],
      loaded: true, verifiedAt: Date.now(), now: new Date()
    });
    assert.equal(answer?.language, language);
    assert.match(answer.text, language === 'es' ? /calendario.*no.*conectado/i : /calendar is not connected/i);
    assert.doesNotMatch(answer.text, /Private:|09:00|San Juan/i);
  }
});

test('travel unavailable: bilingual answers do not invent ETA or departure', () => {
  for (const [question, language] of [
    ['¿A qué hora debo salir?', 'es'],
    ['When should I leave?', 'en'],
  ]) {
    const answer = trustedCommand(question, { tasks: [{title:'Drive 12 minutes',status:'pending'}] });
    assert.equal(answer?.language, language);
    assert.doesNotMatch(answer.text, /Drive 12 minutes/i);
    assert.match(answer.text, language === 'es' ? /no puedo calcular/i : /cannot calculate/i);
  }
});

test('failed synchronization is not an empty agenda or confirmed zero tasks', () => {
  for (const english of [false, true]) {
    const answer = dailyBriefing({ tasks: [], loaded: false, verifiedAt: Date.now(), english });
    assert.match(answer, english ? /cannot verify/i : /no puedo verificar/i);
    assert.doesNotMatch(answer, /0 pending|0 pendientes|No pending tasks were recorded|No hay tareas pendientes registradas/i);
  }
});
