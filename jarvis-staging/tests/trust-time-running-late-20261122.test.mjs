// Reproduce: node --test jarvis-staging/tests/trust-time-running-late-20261122.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, englishIntent, trustedCommand} from '../site/briefing.js';

test('English voice lateness variants use safe travel response', () => {
  for (const phrase of [
    'Am I running late?',
    'JARVIS, am I going to arrive late?',
    'Am I late?',
    'Will I be late?',
  ]) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    assert.equal(englishIntent(phrase), true, phrase);
    const result=trustedCommand(phrase, {
      loaded:true, verifiedAt:Date.now(),
      tasks:[{title:'PRIVATE_SENTINEL_RUNNING_LATE',status:'pending'}],
    });
    assert.equal(result.language, 'en', phrase);
    assert.match(result.text, /cannot calculate a reliable departure time/i);
    assert.doesNotMatch(result.text, /PRIVATE_SENTINEL_RUNNING_LATE/);
    assert.doesNotMatch(result.text, /\b(?:\d+ minutes|traffic is clear)\b/i);
  }
});

test('unrelated English questions are not classified as travel', () => {
  for (const phrase of ['Am I running tomorrow?', 'Am I going to arrive tomorrow?']) {
    assert.notEqual(classifyCommand(phrase), 'travel', phrase);
  }
});
