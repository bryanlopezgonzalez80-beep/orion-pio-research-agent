import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyCommand, trustedCommand } from '../site/briefing.js';

// No calendar, traffic, location, network or billable model calls.
for (const [phrase, language] of [
  ['¿Llego a tiempo a mi cita?', 'es'],
  ['¿Llego a tiempo para la reunión?', 'es'],
  ['¿Llego a tiempo al trabajo?', 'es'],
  ['Will I make it to my meeting on time?', 'en'],
  ['Will I make it on time?', 'en'],
]) {
  test('unverified arrival question stays travel-only: '+phrase, () => {
    assert.equal(classifyCommand(phrase), 'travel');
    const result=trustedCommand(phrase, { tasks: [{title:'Private task'}], loaded:true, verifiedAt:Date.now() });
    assert.equal(result.language, language);
    assert.match(result.text, language==='es' ? /No puedo calcular una hora fiable/ : /cannot calculate a reliable departure time/i);
    assert.doesNotMatch(result.text, /Private task|\b\d+ minutes\b|\b\d+ minutos\b/i);
  });
}
test('unrelated phrases do not trigger an arrival claim', () => {
  assert.equal(classifyCommand('Will I make a cake?'), null);
});
