import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

// Detect fabricated travel durations or clock times in either language.
const inventedTravelEstimate = /\b\d+\s*(?:minutes|minutos)\b|\b\d{1,2}:\d{2}\b/i;

test('estimate guard recognizes invented minutes and departure clock times', () => {
  for (const sample of ['Leave in 15 minutes', 'Sal en 20 minutos', 'Leave at 08:30']) {
    assert.match(sample, inventedTravelEstimate);
  }
  assert.doesNotMatch('Traffic is unavailable', inventedTravelEstimate);
});

test('immediate departure questions fail closed without authorized calendar and traffic', () => {
  for (const [phrase, language] of [
    ['Should I leave now?', 'en'],
    ['Do I need to leave now?', 'en'],
    ['¿Salgo ya?', 'es'],
    ['¿Debo salir ya?', 'es'],
  ]) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    const result = trustedCommand(phrase);
    assert.equal(result?.language, language, phrase);
    assert.match(result.text, /traffic|tráfico/i, phrase);
    assert.doesNotMatch(result.text, inventedTravelEstimate, phrase);
  }
});

test('ordinary task and calendar questions remain separate from travel', () => {
  assert.equal(classifyCommand('What should I do today?'), 'brief');
  assert.equal(classifyCommand('Do I have any meetings today?'), 'calendar');
});
