import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing } from '../site/briefing.js';

// Fixed clock and verified timestamp: no network, credentials, or paid APIs.
const now = new Date('2026-11-21T12:00:00Z');
const verifiedAt = now.getTime() - 60_000;
const briefing = (tasks, english = true) => dailyBriefing({ tasks, loaded: true, verifiedAt, now, english });

test('completed and cancelled tasks cannot become outstanding commitments', () => {
  const text = briefing([
    { title: 'Completed private appointment', status: 'completed', due_at: '2026-11-21T09:00:00-04:00' },
    { title: 'Cancelled private meeting', status: 'cancelled', due_at: '2026-11-21T10:00:00-04:00' },
    { title: 'Real pending task', status: 'pending', due_at: '2026-11-21T11:00:00-04:00' }
  ]);
  assert.match(text, /1 pending, 0 overdue and 1 due later today/);
  assert.match(text, /Real pending task/);
  assert.doesNotMatch(text, /Completed private appointment|Cancelled private meeting/);
  assert.match(text, /not appointments/i);
});

test('suggested priorities are explicitly suggestions and never calendar events', () => {
  const text = briefing([
    { title: 'Low priority', status: 'pending', priority: 'low' },
    { title: 'High priority', status: 'pending', priority: 'high' },
    { title: 'Normal priority', status: 'pending', priority: 'normal' }
  ]);
  assert.ok(text.indexOf('High priority') < text.indexOf('Normal priority'));
  assert.ok(text.indexOf('Normal priority') < text.indexOf('Low priority'));
  assert.match(text, /Suggested priorities/);
  assert.match(text, /calendar and live traffic are not connected/i);
});

test('malformed task records do not leak into spoken priorities', () => {
  const text = briefing([null, [], {}, { title: 123, status: 'pending' }, { title: 'Valid', status: 'pending' }], false);
  assert.match(text, /1 pendientes/);
  assert.match(text, /Valid/);
  assert.doesNotMatch(text, /123|undefined|null/);
});
