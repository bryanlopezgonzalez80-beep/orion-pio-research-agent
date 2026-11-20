import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('medical appointment time/location questions require verified calendar', () => {
  for (const phrase of [
    "What time is my doctor's appointment?",
    'When is my dentist appointment?',
    'Where is my medical appointment?',
    "When will be my next doctor's visit?"
  ]) {
    assert.equal(classifyCommand(phrase), 'calendar', phrase);
    const result = trustedCommand(phrase);
    assert.equal(result?.language, 'en', phrase);
    assert.match(result.text, /calendar is not connected/i, phrase);
    assert.doesNotMatch(result.text, /\b\d{1,2}:\d{2}\b/, phrase);
  }
});

test('medical task requests do not become appointments', () => {
  for (const phrase of ['What time should I study?', 'When is my medical report due?']) {
    assert.notEqual(classifyCommand(phrase), 'calendar', phrase);
  }
});
