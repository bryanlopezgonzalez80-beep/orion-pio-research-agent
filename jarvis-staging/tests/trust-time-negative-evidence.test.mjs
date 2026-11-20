import test from 'node:test';
import assert from 'node:assert/strict';
import {trustedCommand, classifyCommand} from '../site/briefing.js';

// A locally stored task must not become evidence of a calendar event or a route.
test('calendar inquiries do not infer meetings from private task titles', () => {
  const context = {loaded:true, verifiedAt:Date.now(), tasks:[{title:'Meeting at 09:00, 10 minute drive',status:'pending'}]};
  for (const [phrase,language] of [['Do I have any meetings today?','en'],['¿Tengo alguna reunión hoy?','es']]) {
    assert.equal(classifyCommand(phrase),'calendar');
    const answer=trustedCommand(phrase,context);
    assert.equal(answer.language,language);
    assert.doesNotMatch(answer.text,/09:00|10 minute drive|Meeting at/);
    assert.match(answer.text,/calendar|calendario/i);
  }
});

test('travel inquiries do not infer departure from task titles or cached task data', () => {
  const context = {loaded:true,verifiedAt:Date.now(),tasks:[{title:'Drive to meeting, leave at 08:30',status:'pending'}]};
  for (const phrase of ['Should I leave now?','¿Debo salir ya?']) {
    assert.equal(classifyCommand(phrase),'travel');
    const answer=trustedCommand(phrase,context);
    assert.doesNotMatch(answer.text,/08:30|Drive to meeting/);
    assert.match(answer.text,/traffic|tráfico/i);
  }
});
