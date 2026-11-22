// Run: node --test jarvis-staging/tests/trust-time-short-lateness-20261122.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, englishIntent, trustedCommand} from '../site/briefing.js';

test('short bilingual lateness questions route to safe travel response', () => {
  for (const [phrase, language] of [
    ['Am I late?', 'en'],
    ['JARVIS, am I late for my meeting?', 'en'],
    ['Voy tarde?', 'es'],
    ['JARVIS, llegaré tarde a mi cita?', 'es'],
    ['Estoy llegando tarde', 'es'],
  ]) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    assert.equal(englishIntent(phrase), language === 'en', phrase);
    const result=trustedCommand(phrase, {
      loaded:true, verifiedAt:Date.now(),
      tasks:[{title:'PRIVATE_SENTINEL_20261122',status:'pending'}],
    });
    assert.equal(result.language,language,phrase);
    assert.doesNotMatch(result.text,/PRIVATE_SENTINEL_20261122/);
    assert.match(result.text,language==='en' ? /cannot calculate a reliable departure time/i : /no puedo calcular una hora fiable/i);
  }
});

test('unrelated questions do not become travel commands', () => {
  for (const phrase of ['Am I ready?', 'Voy a estudiar', 'Llegaré mañana']) {
    assert.notEqual(classifyCommand(phrase), 'travel', phrase);
  }
});
