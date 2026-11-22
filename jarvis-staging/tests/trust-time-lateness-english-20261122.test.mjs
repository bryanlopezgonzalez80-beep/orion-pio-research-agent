// Run: node --test jarvis-staging/tests/trust-time-lateness-english-20261122.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, englishIntent, trustedCommand} from '../site/briefing.js';

test('English lateness questions route to travel safety response', () => {
  for (const phrase of ['Am I going to be late?', 'Will I be late?', 'JARVIS, will I be late for my appointment?']) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    assert.equal(englishIntent(phrase), true, phrase);
    const response=trustedCommand(phrase);
    assert.equal(response.language, 'en');
    assert.match(response.text, /cannot calculate a reliable departure time/i);
    assert.match(response.text, /do not have a verified appointment/i);
  }
});

test('English lateness questions never disclose private tasks or invent traffic', () => {
  const response=trustedCommand('Will I be late?', {
    loaded:true, verifiedAt:Date.now(),
    tasks:[{title:'PRIVATE_TASK_SENTINEL',status:'pending'}]
  });
  assert.doesNotMatch(response.text,/PRIVATE_TASK_SENTINEL/);
  assert.match(response.text,/live traffic data/i);
});
