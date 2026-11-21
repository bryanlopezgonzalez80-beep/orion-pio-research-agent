// Run: node --test jarvis-staging/tests/trust-time-medical-arrival-20261121.test.mjs
// Offline regression against real briefing module; no network, credentials or model calls.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand,englishIntent,trustedCommand} from '../site/briefing.js';

test('medical appointment arrival questions are travel, not inferred appointments',()=>{
  for(const phrase of [
    "Will I make it to my doctor's appointment on time?",
    "Will I make it to my dentist appointment on time?",
    "Will I make it to my meeting on time?"
  ]){
    assert.equal(classifyCommand(phrase),'travel',phrase);
    assert.equal(englishIntent(phrase),true,phrase);
    const answer=trustedCommand(phrase,{tasks:[{title:'PRIVATE_CANARY',status:'pending'}]});
    assert.equal(answer.language,'en');
    assert.match(answer.text,/cannot calculate a reliable departure time/i);
    assert.match(answer.text,/live traffic/i);
    assert.doesNotMatch(answer.text,/PRIVATE_CANARY|\b\d+ minutes\b/i);
  }
});

test('medical arrival questions do not become fabricated calendar events',()=>{
  const answer=trustedCommand("Will I make it to my doctor's appointment on time?");
  assert.ok(answer);
  assert.doesNotMatch(answer.text,/confirmed appointment|appointment at \d/i);
});
