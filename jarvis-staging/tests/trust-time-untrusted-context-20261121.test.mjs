// Run: node --test jarvis-staging/tests/trust-time-untrusted-context-20261121.test.mjs
// No network, API keys, model requests or personal data.
import test from 'node:test';
import assert from 'node:assert/strict';
import { trustedCommand } from '../site/briefing.js';

const sensitive = 'PRIVATE-TASK-DO-NOT-SPEAK';
const context = {
  tasks: [{ title: sensitive, status: 'pending', due_at: '2026-11-22T09:00:00-04:00' }],
  loaded: true,
  verifiedAt: Date.parse('2026-11-21T22:00:00-04:00'),
  now: new Date('2026-11-21T22:01:00-04:00'),
};

test('calendar and travel queries never leak task titles as verified events', () => {
  for (const phrase of [
    'Do I have any appointments?',
    '¿Tengo alguna cita?',
    'When should I leave?',
    '¿A qué hora debo salir?',
    'Can I make it to my appointment on time?',
    '¿Llegaré a tiempo a mi cita?',
  ]) {
    const result = trustedCommand(phrase, context);
    assert.ok(result, 'must handle: ' + phrase);
    assert.equal(result.text.includes(sensitive), false, 'private task title leaked: ' + phrase);
    assert.doesNotMatch(result.text, /(?:\b\d+\s*(?:minutes?|minutos?)\b)/i, 'invented travel minutes: ' + phrase);
  }
});

test('missing and expired synchronization never expose private titles in briefing', () => {
  for (const verifiedAt of [null, 0, context.now.getTime() - 15 * 60 * 1000, context.now.getTime() + 1000]) {
    for (const phrase of ['¿Qué tengo hoy?', 'What I got to do today?']) {
      const result = trustedCommand(phrase, { ...context, verifiedAt });
      assert.ok(result, 'must handle: ' + phrase);
      assert.equal(result.text.includes(sensitive), false, 'unverified title leaked');
      assert.match(result.text, /(?:actualiza|update)/i, 'must disclose refresh requirement');
    }
  }
});
