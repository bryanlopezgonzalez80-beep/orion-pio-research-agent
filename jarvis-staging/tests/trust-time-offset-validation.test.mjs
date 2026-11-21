import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing } from '../site/briefing.js';

// Trust & Time Intelligence: never silently normalize impossible offsets or dates.
// Keep a fixed Puerto Rico clock to make these checks reproducible.
const now = new Date('2026-11-21T12:00:00Z');
const verifiedAt = now.getTime() - 60_000;
function brief(due_at) {
  return dailyBriefing({
    tasks: [{ title: 'Verify time zone', status: 'pending', due_at }],
    loaded: true, verifiedAt, now, english: true
  });
}
test('reject impossible UTC offsets instead of inventing due times', () => {
  for (const due_at of [
    '2026-11-21T09:00:00+14:01',
    '2026-11-21T09:00:00-12:01',
    '2026-11-21T09:00:00+02:60',
    '2026-11-21T09:00:00+99:00',
    '2026-11-21T09:00:00',
  ]) {
    const result = brief(due_at);
    assert.match(result, /1 pending/);
    assert.match(result, /Verify time zone/);
    assert.doesNotMatch(result, /, due /, due_at);
    assert.match(result, /calendar and live traffic are not connected/i);
  }
});
test('accept real UTC offsets while preserving Puerto Rico calendar day', () => {
  const result = brief('2026-11-21T10:00:00-04:00');
  assert.match(result, /1 pending/);
  assert.match(result, /due Nov 21, 10:00 AM/i);
  assert.match(result, /due later today/i);
});
test('reject impossible leap dates without silently rolling into March', () => {
  for (const due_at of ['2026-02-29T09:00:00-04:00', '2026-02-30T09:00:00Z']) {
    assert.doesNotMatch(brief(due_at), /, due /);
  }
});
