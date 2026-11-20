import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

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
    assert.doesNotMatch(result.text, /\\b\\d+\\s*(?:minutes|minutos)\\b|\\b\\d{1,2}:\\d{2}\\b/i, phrase);
  }
});

test('ordinary task and calendar questions remain separate from travel', () => {
  assert.equal(classifyCommand('What should I do today?'), 'brief');
  assert.equal(classifyCommand('Do I have any meetings today?'), 'calendar');
});
