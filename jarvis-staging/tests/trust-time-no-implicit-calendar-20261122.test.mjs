// Run: node --test jarvis-staging/tests/trust-time-no-implicit-calendar-20261122.test.mjs
// Integration tests against the real local module. No network, paid API or credentials.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

const privateTask='PRIVATE_DO_NOT_DISCLOSE_427';
const context={
  loaded:true,
  now:new Date('2026-11-22T09:00:00.000Z'),
  verifiedAt:Date.parse('2026-11-22T09:00:00.000Z'),
  tasks:[{title:privateTask,status:'pending',priority:'high',due_at:'2026-11-22T11:00:00-04:00'}]
};

test('calendar voice questions never infer meetings from stored task titles',()=>{
  for(const [phrase,language] of [
    ['¿Tengo alguna cita?', 'es'],
    ['¿A qué hora es mi reunión?', 'es'],
    ['Do I have any appointments?', 'en'],
    ['When is my next meeting?', 'en']
  ]){
    assert.equal(classifyCommand(phrase),'calendar',phrase);
    const response=trustedCommand(phrase,context);
    assert.equal(response?.language,language,phrase);
    assert.doesNotMatch(response.text,/PRIVATE_DO_NOT_DISCLOSE_427/);
    assert.match(response.text,/calendario|calendar/i);
    assert.match(response.text,/no (?:he consultado|calendar events have been checked)/i);
  }
});

test('travel voice questions do not use private tasks as calendar or traffic evidence',()=>{
  for(const [phrase,language] of [
    ['¿Llegaré a tiempo?', 'es'],
    ['¿A qué hora debo salir?', 'es'],
    ['Will I make it on time?', 'en'],
    ['When should I leave?', 'en']
  ]){
    assert.equal(classifyCommand(phrase),'travel',phrase);
    const response=trustedCommand(phrase,context);
    assert.equal(response?.language,language,phrase);
    assert.doesNotMatch(response.text,/PRIVATE_DO_NOT_DISCLOSE_427/);
    assert.match(response.text,/tráfico|traffic/i);
    assert.match(response.text,/no puedo calcular|cannot calculate/i);
  }
});
