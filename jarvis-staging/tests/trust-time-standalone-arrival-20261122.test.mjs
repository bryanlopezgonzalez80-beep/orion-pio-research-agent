// Run: node --test jarvis-staging/tests/trust-time-standalone-arrival-20261122.test.mjs
// Tests the actual local briefing module; no network or paid API calls.
import test from 'node:test';
import assert from 'node:assert/strict';
import { classifyCommand, trustedCommand } from '../site/briefing.js';

test('standalone Spanish arrival questions are travel intents', () => {
  for (const input of ['¿Llegaré a tiempo?', '¿Alcanzaré a llegar a tiempo?', '¿Voy a llegar a tiempo?', 'JARVIS, ¿voy a llegar a tiempo?']) {
    assert.equal(classifyCommand(input), 'travel', input);
    const response = trustedCommand(input);
    assert.equal(response?.language, 'es');
    assert.match(response?.text ?? '', /No puedo calcular una hora fiable/);
    assert.match(response?.text ?? '', /tráfico/);
  }
});

test('specific arrival queries remain travel intents; unrelated speech is not', () => {
  for (const input of ['¿Llegaré a tiempo a mi cita?', '¿Voy a llegar a tiempo al médico?', 'Can I make it on time?']) {
    assert.equal(classifyCommand(input), 'travel', input);
  }
  for (const input of ['Quiero llegar a tiempo', '¿Qué tengo hoy?', '¿Tengo alguna cita?']) {
    assert.notEqual(classifyCommand(input), 'travel', input);
  }
});
