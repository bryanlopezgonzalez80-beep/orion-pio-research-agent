// Run: node --test jarvis-staging/tests/trust-time-inactive-task-isolation-20261122.test.mjs
// Offline regression against the actual JARVIS briefing module; no API calls.
import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, trustedCommand } from '../site/briefing.js';

const now = new Date('2026-11-22T14:00:00Z');
const base = { now, loaded: true, verifiedAt: now.getTime() - 30_000 };
const privateTitle = 'PRIVATE-CANCELLED-MEETING';
const tasks = [
  { title: privateTitle, status: 'cancelled', priority: 'high', due_at: '2026-11-22T12:00:00Z' },
  { title: 'PRIVATE-DONE-APPOINTMENT', status: 'completed', priority: 'high', due_at: '2026-11-22T12:00:00Z' },
  { title: 'Verified pending task', status: 'pending', priority: 'normal', due_at: '2026-11-22T15:00:00Z' },
];

test('cancelled and completed items are not outstanding tasks in either language', () => {
  for (const english of [false, true]) {
    const result = dailyBriefing({ ...base, tasks, english });
    assert.match(result, english ? /1 pending, 0 overdue/ : /1 pendientes, 0 atrasadas/);
    assert.match(result, /Verified pending task/);
    assert.doesNotMatch(result, /PRIVATE-CANCELLED-MEETING|PRIVATE-DONE-APPOINTMENT/);
  }
});

test('cancelled task titles cannot be mistaken for calendar evidence', () => {
  for (const query of ['¿Tengo alguna cita?', 'Do I have any appointments?']) {
    const result = trustedCommand(query, { ...base, tasks });
    assert.ok(result);
    assert.doesNotMatch(result.text, /PRIVATE-CANCELLED-MEETING|PRIVATE-DONE-APPOINTMENT/);
    assert.match(result.text, /calendario|calendar/i);
  }
});

test('unverified refresh fails closed even if a completed task contains a meeting title', () => {
  for (const english of [false, true]) {
    const result = dailyBriefing({ ...base, tasks, loaded: false, english });
    assert.doesNotMatch(result, /PRIVATE-CANCELLED-MEETING|PRIVATE-DONE-APPOINTMENT|Verified pending task/);
    assert.match(result, english ? /cannot verify/ : /No puedo verificar/);
  }
});
