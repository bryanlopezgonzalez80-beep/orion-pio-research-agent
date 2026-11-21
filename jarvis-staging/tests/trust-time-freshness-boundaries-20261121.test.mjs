import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, recentVerification, MAX_TASK_AGE_MS } from '../site/briefing.js';

// Fixed clock: reproducible without network, secrets, model requests or billing.
const now = new Date('2026-11-21T12:00:00.000Z');
const task = { title: 'Private saved task', status: 'pending' };
const run = (verifiedAt, loaded = true, english = true) =>
  dailyBriefing({ tasks: [task], loaded, verifiedAt, now, english });

test('freshness is exclusive at exactly 15 minutes and rejects future timestamps', () => {
  const t = now.getTime();
  assert.equal(MAX_TASK_AGE_MS, 900000);
  assert.equal(recentVerification(t - MAX_TASK_AGE_MS + 1, t), true);
  assert.equal(recentVerification(t - MAX_TASK_AGE_MS, t), false);
  assert.equal(recentVerification(t + 1, t), false);
  assert.equal(recentVerification(Number.NaN, t), false);
});

test('stale or future verification must not disclose private task titles in English', () => {
  for (const stamp of [null, now.getTime() - MAX_TASK_AGE_MS, now.getTime() + 1]) {
    const answer = run(stamp);
    assert.match(answer, /cannot verify your tasks/i);
    assert.doesNotMatch(answer, /Private saved task|1 pending|No pending tasks were recorded/);
  }
});

test('failed load cannot be misreported as an empty task list in Spanish', () => {
  const answer = run(now.getTime() - 1000, false, false);
  assert.match(answer, /No puedo verificar tus tareas/i);
  assert.doesNotMatch(answer, /Private saved task|No hay tareas pendientes registradas|1 pendientes/);
});

test('fresh, loaded task can be described only as a task, never a calendar event', () => {
  const answer = run(now.getTime() - 1000);
  assert.match(answer, /1 pending/);
  assert.match(answer, /Private saved task/);
  assert.match(answer, /not appointments/i);
});
