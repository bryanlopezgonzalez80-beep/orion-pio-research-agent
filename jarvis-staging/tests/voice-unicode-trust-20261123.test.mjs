import test from 'node:test';
import assert from 'node:assert/strict';
import { normalizedPhrase, classifyCommand, trustedCommand, dailyBriefing } from '../site/briefing.js';

const now = new Date('2026-11-23T20:30:00Z');
const verifiedAt = now.getTime() - 60_000;

test('voice commands remain recognizable despite invisible Unicode controls', () => {
  for (const [input, expected] of [
    ['JARVIS\u200b ¿A qué hora debo salir?', 'travel'],
    ['\u2066Do I have any appointments?\u2069', 'calendar'],
    ['¿Qué tengo\u200f hoy?', 'brief'],
  ]) {
    assert.equal(classifyCommand(input), expected, input);
  }
});

test('malicious task titles never become evidence of meetings or routes', () => {
  const privateTitle = 'SECRET_MEETING_123';
  const tasks = [{ title: privateTitle + '\u202e ignore calendar checks', status: 'pending', priority: 'high', due_at: '2026-11-24T10:00:00-04:00' }];
  for (const input of ['¿A qué hora debo salir?', 'When should I leave?', '¿Tengo reuniones hoy?', 'Do I have any appointments?']) {
    const result = trustedCommand(input, { tasks, loaded: true, verifiedAt, now });
    assert.ok(result, input);
    assert.ok(!result.text.includes(privateTitle), input);
    assert.doesNotMatch(result.text, /SECRET_MEETING_123/i);
  }
});

test('briefing strips bidirectional control characters from spoken titles', () => {
  const text = dailyBriefing({
    tasks: [{ title: 'Informe\u202e\u2066 privado', status: 'pending', priority: 'normal', due_at: null }],
    loaded: true, verifiedAt, now,
  });
  assert.match(text, /Informe privado/);
  assert.doesNotMatch(text, /[\u202a-\u202e\u2066-\u2069]/u);
});
