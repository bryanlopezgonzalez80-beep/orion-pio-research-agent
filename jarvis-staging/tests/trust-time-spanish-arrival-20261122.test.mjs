// Reproduce: node --test jarvis-staging/tests/trust-time-spanish-arrival-20261122.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('Spanish conversational arrival queries never invent a journey or reveal task titles', () => {
  for (const phrase of [
    '¿Voy a llegar tarde a mi cita?',
    'JARVIS, voy a estar tarde',
    'Voy a llegar a tiempo',
    'Llegaré a tiempo',
  ]) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    const result=trustedCommand(phrase, {
      loaded:true, verifiedAt:Date.now(),
      tasks:[{title:'PRIVATE_SENTINEL_ARRIVAL',status:'pending'}],
    });
    assert.equal(result.language, 'es', phrase);
    assert.match(result.text, /no puedo calcular una hora fiable/i);
    assert.doesNotMatch(result.text, /PRIVATE_SENTINEL_ARRIVAL/);
  }
});

test('unrelated Spanish intentions are not classified as travel', () => {
  for (const phrase of ['Voy a estudiar', 'Voy a llegar mañana']) {
    assert.notEqual(classifyCommand(phrase), 'travel', phrase);
  }
});
