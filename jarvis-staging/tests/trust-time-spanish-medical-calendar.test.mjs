import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('Spanish medical appointments require authorized calendar evidence', () => {
  for (const phrase of [
    '¿Tengo cita médica mañana?',
    '¿Tengo una consulta médica hoy?',
    '¿Hay alguna cita con el dentista?',
    '¿Tengo cita con la doctora?',
    '¿Tengo una cita del médico?',
  ]) {
    assert.equal(classifyCommand(phrase), 'calendar', phrase);
    const answer = trustedCommand(phrase);
    assert.equal(answer?.language, 'es', phrase);
    assert.match(answer.text, /calendario.*no.*conectado/i, phrase);
    assert.doesNotMatch(answer.text, /\b\d{1,2}:\d{2}\b/, phrase);
  }
});

test('medical task discussions are not silently treated as confirmed calendar entries', () => {
  for (const phrase of ['Necesito comprar medicamentos', 'Mi tarea es llamar al dentista']) {
    assert.notEqual(classifyCommand(phrase), 'calendar', phrase);
  }
});
