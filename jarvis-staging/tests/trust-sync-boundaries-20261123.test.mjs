import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand, MAX_TASK_AGE_MS } from '../site/briefing.js';

const NOW = Date.parse('2026-11-23T16:00:00.000Z');
const task = { title: 'Private appointment-like task', status: 'pending', priority: 'high', due_at: '2026-11-23T18:00:00Z' };

test('freshness expires at the exact 15-minute boundary in both languages', () => {
  for (const english of [false, true]) {
    const output = dailyBriefing({ tasks: [task], loaded: true, verifiedAt: NOW - MAX_TASK_AGE_MS, now: new Date(NOW), english });
    assert.doesNotMatch(output, /Private appointment-like task/);
    assert.match(output, english ? /cannot verify/i : /no puedo verificar/i);
  }
});

test('a future verification must not authorize a task briefing', () => {
  for (const english of [false, true]) {
    const output = dailyBriefing({ tasks: [task], loaded: true, verifiedAt: NOW + 1, now: new Date(NOW), english });
    assert.doesNotMatch(output, /Private appointment-like task/);
    assert.match(output, english ? /cannot verify/i : /no puedo verificar/i);
  }
});

test('calendar and departure requests never leak private task titles or invent events', () => {
  for (const query of ['¿Tengo alguna reunión hoy?', 'Do I have any appointments?', '¿A qué hora debo salir?', 'When should I leave?']) {
    const response = trustedCommand(query, { tasks: [task], loaded: true, verifiedAt: NOW, now: new Date(NOW) });
    assert.ok(response, query);
    assert.doesNotMatch(response.text, /Private appointment-like task/);
    assert.match(response.text, /calendario|calendar|tráfico|traffic/i);
  }
});
