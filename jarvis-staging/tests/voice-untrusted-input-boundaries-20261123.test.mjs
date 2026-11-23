import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizedPhrase, trustedCommand, dailyBriefing } from '../site/briefing.js';

test('hostile voice transcription cannot crash command classification', () => {
  const hostile = { toString() { throw new Error('untrusted voice payload'); } };
  assert.equal(normalizedPhrase(hostile), '');
  assert.equal(trustedCommand(hostile), null);
});

test('Unicode voice controls do not turn calendar requests into trusted meetings', () => {
  const result = trustedCommand('JARVIS, ¿tengo\u200b alguna reunión?');
  assert.ok(result);
  assert.equal(result.language, 'es');
  assert.match(result.text, /no puedo confirmar citas ni reuniones/i);
});

test('voice query for departure does not leak task content or invent a travel time', () => {
  const privateTitle = 'CONFIDENTIAL_PERSONAL_TASK_9471';
  const result = trustedCommand('When should I leave?', {
    loaded: true,
    verifiedAt: Date.parse('2026-11-23T19:00:00Z'),
    now: new Date('2026-11-23T19:01:00Z'),
    tasks: [{title:privateTitle,status:'pending'}]
  });
  assert.ok(result);
  assert.equal(result.language, 'en');
  assert.doesNotMatch(result.text, /CONFIDENTIAL_PERSONAL_TASK_9471/);
  assert.match(result.text, /cannot calculate a reliable departure time/i);
  assert.match(result.text, /live traffic/i);
});

test('malformed clock fails closed without disclosing private task titles', () => {
  const privateTitle = 'CONFIDENTIAL_PERSONAL_TASK_9471';
  const result = dailyBriefing({
    loaded: true, verifiedAt: Date.parse('2026-11-23T19:00:00Z'),
    now: Symbol('invalid clock'),
    tasks: [{title:privateTitle,status:'pending'}]
  });
  assert.doesNotMatch(result, /CONFIDENTIAL_PERSONAL_TASK_9471/);
  assert.match(result, /hora actual no está disponible/i);
});
