// Run: node --test jarvis-staging/tests/trust-time-can-i-arrive-20261121.test.mjs
// Offline tests against real briefing.js. No network or paid API calls.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand,englishIntent,trustedCommand} from '../site/briefing.js';

test('can I make it on time stays a travel question in English',()=>{
  for(const phrase of [
    'Can I make it on time?',
    'Can I make it to my meeting on time?',
    "Can I make it to my doctor's appointment on time?",
    'Can I make it to my dentist appointment on time?'
  ]){
    assert.equal(classifyCommand(phrase),'travel',phrase);
    assert.equal(englishIntent(phrase),true,phrase);
    const result=trustedCommand(phrase,{tasks:[{title:'PRIVATE_CANARY',status:'pending'}]});
    assert.equal(result.language,'en');
    assert.match(result.text,/cannot calculate a reliable departure time/i);
    assert.match(result.text,/live traffic/i);
    assert.doesNotMatch(result.text,/PRIVATE_CANARY|\b\d+ minutes\b/i);
  }
});

test('unrelated question does not get a fabricated answer',()=>{
  assert.equal(trustedCommand('Can I make it better?'),null);
});
