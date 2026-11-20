import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizedPhrase, trustedCommand } from '../site/briefing.js';

test('voice transcription smart apostrophes preserve English medical calendar intent', () => {
  for (const apostrophe of ['\u2019', '\u2018', '\u02bc', "'"]) {
    const query = `What time is my doctor${apostrophe}s appointment?`;
    const answer = trustedCommand(query);
    assert.equal(answer?.language, 'en', query);
    assert.match(answer?.text ?? '', /calendar is not connected/i, query);
    assert.doesNotMatch(answer?.text ?? '', /\b(?:9:00|20 minutes)\b/i, query);
  }
});

test('normalization retains Spanish accents and does not fabricate calendar events', () => {
  assert.equal(normalizedPhrase('¿Qué tengo hoy?'), 'que tengo hoy');
  const answer = trustedCommand('¿Tengo cita médica mañana?');
  assert.equal(answer?.language, 'es');
  assert.match(answer?.text ?? '', /no puedo confirmar citas ni reuniones/i);
});
