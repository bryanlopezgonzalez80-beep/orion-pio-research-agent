// Run: node --test jarvis-staging/tests/trust-time-malformed-voice-coercion-20261121.test.mjs
// No network, credentials or model requests.
import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizedPhrase, classifyCommand, trustedCommand } from '../site/briefing.js';

test('malformed voice input fails closed instead of crashing', () => {
  const bad = [
    { toString() { throw Error('malformed speech'); } },
    Object.create(null),
    Symbol('speech'),
    1n,
    null,
    undefined
  ];
  for (const input of bad) {
    assert.doesNotThrow(() => normalizedPhrase(input));
    assert.doesNotThrow(() => classifyCommand(input));
    assert.doesNotThrow(() => trustedCommand(input));
    assert.equal(classifyCommand(input), null);
    assert.equal(trustedCommand(input), null);
  }
});

test('valid Spanish and English voice commands still classify correctly', () => {
  assert.equal(classifyCommand('JARVIS, ¿qué tengo hoy?'), 'brief');
  assert.equal(classifyCommand('What I got to do today?'), 'brief');
  assert.equal(classifyCommand('¿A qué hora debo salir?'), 'travel');
  assert.equal(classifyCommand('Do I have any appointments?'), 'calendar');
});
