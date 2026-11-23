import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand } from '../site/briefing.js';

// Trust & Time Intelligence: untrusted task text is never calendar or route evidence.
// Run: node --test jarvis-staging/tests/trust-unverified-task-metadata.test.mjs
const now = new Date('2026-11-23T10:00:00Z');
const verifiedAt = now.getTime();

test('invalid or timezone-free deadlines are not presented as confirmed times', () => {
  for (const due_at of ['2026-11-23T09:00:00', '2026-02-30T09:00:00Z', '2026-11-23T09:00:00+15:00']) {
    for (const english of [false, true]) {
      const answer = dailyBriefing({loaded:true, verifiedAt, now, english,
        tasks:[{title:'Review proposal',status:'pending',due_at,priority:'normal'}]});
      assert.match(answer, /Review proposal/);
      assert.doesNotMatch(answer, /due Nov|vence nov|09:00|9:00/);
      assert.match(answer, english ? /not appointments/i : /no citas/i);
    }
  }
});

test('calendar and travel requests cannot infer facts from task descriptions', () => {
  const tasks=[{title:'Meeting at 9:00 in San Juan; leave at 8:15',status:'pending',
    due_at:'2026-11-23T13:00:00Z',priority:'high'}];
  for (const [phrase, expected] of [
    ['Do I have any appointments?', /calendar is not connected/i],
    ['¿Tengo una reunión?', /calendario aún no está conectado/i],
    ['When should I leave?', /cannot calculate/i],
    ['¿A qué hora debo salir?', /No puedo calcular/i]
  ]) {
    const answer=trustedCommand(phrase,{loaded:true,verifiedAt,now,tasks});
    assert.ok(answer, phrase);
    assert.match(answer.text,expected);
    assert.doesNotMatch(answer.text,/San Juan|8:15|9:00/);
  }
});

test('failed verification cannot disclose a private task title in either language', () => {
  const tasks=[{title:'PRIVATE_CLIENT_SECRET',status:'pending'}];
  for (const english of [false,true]) {
    for (const verified of [null,verifiedAt-15*60*1000,verifiedAt+1000]) {
      const answer=dailyBriefing({tasks,loaded:true,verifiedAt:verified,now,english});
      assert.doesNotMatch(answer,/PRIVATE_CLIENT_SECRET/);
      assert.match(answer,english?/cannot verify/i:/No puedo verificar/i);
    }
  }
});
