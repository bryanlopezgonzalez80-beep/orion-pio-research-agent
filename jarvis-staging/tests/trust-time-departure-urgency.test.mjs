import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('departure urgency questions fail closed in both languages', () => {
  for (const [phrase, language] of [
    ['How soon should I leave?', 'en'],
    ['How soon do I need to leave?', 'en'],
    ['¿Cuánto falta para salir?', 'es'],
    ['¿Cuánto tiempo tengo para salir?', 'es']
  ]) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    const response = trustedCommand(phrase);
    assert.equal(response?.language, language, phrase);
    assert.match(response.text, language === 'en' ? /cannot calculate a reliable departure time/i : /no puedo calcular una hora fiable/i);
    assert.doesNotMatch(response.text, /\b\d+\s*(?:minutos?|minutes?|mins?)\b/i);
  }
});

test('non-departure questions are not classified as travel', () => {
  for (const phrase of ['How soon can I study?', '¿Cuánto falta para terminar mi tarea?']) {
    assert.notEqual(classifyCommand(phrase), 'travel', phrase);
  }
});


test('urgent appointment departures require verified route data, not invented minutes', () => {
  for (const phrase of ['Should I leave for my appointment now?', 'Do I need to leave for the meeting now?']) {
    assert.equal(classifyCommand(phrase), 'travel', phrase);
    const response=trustedCommand(phrase);
    assert.equal(response?.language, 'en');
    assert.match(response.text,/cannot calculate a reliable departure time/i);
    assert.doesNotMatch(response.text,/\b\d+\s*(?:minutos?|minutes?|mins?)\b/i);
  }
});
