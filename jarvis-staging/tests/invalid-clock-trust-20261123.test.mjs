import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand } from '../site/briefing.js';

const secret='PRIVATE_TASK_TITLE_DO_NOT_DISCLOSE';
const tasks=[{title:secret,status:'pending',priority:'high',due_at:'2026-11-23T16:00:00-04:00'}];

for (const [label, now] of [
  ['invalid date', new Date(NaN)],
  ['unparseable date string', 'not-a-date'],
  ['Symbol', Symbol('invalid-clock')],
  ['BigInt', 123n],
]) {
  test(`invalid clock fails closed without private task disclosure: ${label}`, () => {
    for (const english of [false,true]) {
      const response=dailyBriefing({tasks,loaded:true,verifiedAt:Date.now(),now,english});
      assert.equal(typeof response,'string');
      assert.ok(!response.includes(secret));
      assert.match(response,english?/cannot verify your tasks/i:/no puedo verificar tus tareas/i);
    }
  });
}

test('calendar and travel intents do not disclose task titles even with invalid clock',()=>{
  for (const input of ['¿Tengo reuniones hoy?','Do I have any appointments?','¿A qué hora debo salir?','When should I leave?']) {
    const result=trustedCommand(input,{tasks,loaded:true,verifiedAt:Date.now(),now:new Date(NaN)});
    assert.ok(result,`Expected trusted intent: ${input}`);
    assert.ok(!result.text.includes(secret));
    assert.match(result.text,/calendario|calendar|tráfico|traffic|route|rutas|minutos|duration/i);
  }
});
