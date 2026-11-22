// Reproduce: node --test jarvis-staging/tests/trust-time-first-person-late-20261122.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, englishIntent, trustedCommand} from '../site/briefing.js';

test('first-person lateness statements use safe English travel response', () => {
  for (const phrase of ["I'm running late", 'I am running late', "JARVIS, I'm running late"]) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    assert.equal(englishIntent(phrase), true, phrase);
    const answer=trustedCommand(phrase, {
      loaded:true, verifiedAt:Date.now(),
      tasks:[{title:'PRIVATE_FIRST_PERSON_SENTINEL',status:'pending'}],
    });
    assert.equal(answer.language, 'en', phrase);
    assert.match(answer.text, /cannot calculate a reliable departure time/i);
    assert.doesNotMatch(answer.text, /PRIVATE_FIRST_PERSON_SENTINEL/);
  }
});
test('non-lateness statements are not treated as travel', () => {
  for (const phrase of ["I'm running tomorrow", 'I am running a meeting']) {
    assert.notEqual(classifyCommand(phrase), 'travel', phrase);
  }
});
