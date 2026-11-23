import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing } from '../site/briefing.js';

const now = new Date('2026-11-23T14:00:00.000Z');
const verifiedAt = now.getTime() - 1000;
const task = (title, due_at, priority = 'normal') => ({ title, due_at, priority, status: 'pending' });

test('overdue low-priority task is ordered ahead of future high-priority task', () => {
  const text = dailyBriefing({ now, verifiedAt, loaded: true, tasks: [
    task('FutureHighMarker', '2026-11-25T14:00:00Z', 'high'),
    task('OverdueLowMarker', '2026-11-22T14:00:00Z', 'low'),
  ] });
  assert.ok(text.indexOf('OverdueLowMarker') >= 0);
  assert.ok(text.indexOf('FutureHighMarker') >= 0);
  assert.ok(text.indexOf('OverdueLowMarker') < text.indexOf('FutureHighMarker'));
});

test('UTC midnight does not change the Puerto Rico calendar day', () => {
  const text = dailyBriefing({ now: new Date('2026-11-24T00:30:00Z'), verifiedAt: Date.parse('2026-11-24T00:29:00Z'), loaded: true, english: true, tasks: [
    task('PRTodayMarker', '2026-11-23T23:30:00-04:00'),
  ] });
  assert.match(text, /1 due later today/);
});

test('unverified tasks cannot be promoted by priority labels', () => {
  const text = dailyBriefing({ now, verifiedAt: now.getTime() - 900000, loaded: true, tasks: [task('PrivateHighMarker', '2026-11-23T15:00:00Z', 'high')] });
  assert.doesNotMatch(text, /PrivateHighMarker/);
  assert.match(text, /No puedo verificar/);
});
