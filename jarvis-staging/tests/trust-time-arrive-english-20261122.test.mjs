// Run: node --test jarvis-staging/tests/trust-time-arrive-english-20261122.test.mjs
// Offline, no API requests. Arrival questions must never invent routes or meetings.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('English arrive-on-time questions route to travel safeguards',()=>{
  for(const phrase of [
    'Will I arrive on time?',
    'Can I arrive on time?',
    'Will I arrive to my meeting on time?',
    'Can I arrive to the appointment on time?',
    'JARVIS, will I arrive on time?'
  ]){
    assert.equal(classifyCommand(phrase),'travel',phrase);
    const result=trustedCommand(phrase,{tasks:[{title:'PRIVATE_TASK_NAME',status:'pending'}]});
    assert.equal(result?.language,'en',phrase);
    assert.match(result.text,/cannot calculate a reliable departure time/i,phrase);
    assert.doesNotMatch(result.text,/PRIVATE_TASK_NAME|\b\d+ minutes\b/i,phrase);
  }
});

test('unrelated arrival phrases do not claim verified travel information',()=>{
  for(const phrase of ['Will I arrive at my house?', 'Can I arrive tomorrow?']){
    assert.notEqual(classifyCommand(phrase),'travel',phrase);
  }
});
