import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, MAX_TASK_AGE_MS } from '../site/briefing.js';

const NOW = Date.parse('2026-11-23T16:00:00.000Z');
const PRIVATE_TITLE = 'Confidential task alpha';
const task = { title: PRIVATE_TITLE, status: 'pending', priority: 'normal', due_at: '2026-11-24T12:00:00Z' };

test('one millisecond before expiry is fresh, exact boundary is not', () => {
  for (const english of [false, true]) {
    const fresh = dailyBriefing({ tasks: [task], loaded: true, verifiedAt: NOW - MAX_TASK_AGE_MS + 1, now: new Date(NOW), english });
    assert.match(fresh, /Confidential task alpha/);
    const expired = dailyBriefing({ tasks: [task], loaded: true, verifiedAt: NOW - MAX_TASK_AGE_MS, now: new Date(NOW), english });
    assert.doesNotMatch(expired, /Confidential task alpha/);
    assert.match(expired, english ? /cannot verify/i : /no puedo verificar/i);
  }
});

test('invalid verification timestamp types fail closed without leaking titles', () => {
  for (const verifiedAt of [null, undefined, '2026-11-23T16:00:00Z', NaN, Infinity, -1, 0]) {
    for (const english of [false, true]) {
      const result = dailyBriefing({ tasks: [task], loaded: true, verifiedAt, now: new Date(NOW), english });
      assert.doesNotMatch(result, /Confidential task alpha/);
      assert.match(result, english ? /cannot verify/i : /no puedo verificar/i);
    }
  }
});
