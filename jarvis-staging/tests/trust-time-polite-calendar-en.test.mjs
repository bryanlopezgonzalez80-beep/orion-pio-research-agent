import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand} from '../site/briefing.js';

test('polite English calendar checks require calendar evidence', () => {
  for (const phrase of [
    'Can you tell me if I have a meeting tomorrow?',
    'Could you check whether I have an appointment today?',
    'Can you see if there are any meetings?',
    'I have a meeting tomorrow'
  ]) {
    assert.equal(classifyCommand(phrase), 'calendar', phrase);
    const response = trustedCommand(phrase);
    assert.equal(response?.language, 'en', phrase);
    assert.match(response.text, /calendar is not connected/i, phrase);
    assert.doesNotMatch(response.text, /\b\d{1,2}:\d{2}\b/, phrase);
  }
});

test('polite non-calendar requests are not misclassified', () => {
  for (const phrase of [
    'Can you tell me if I have tasks?',
    'Can you check whether I have a reminder?'
  ]) assert.notEqual(classifyCommand(phrase), 'calendar', phrase);
});
