import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, recentVerification } from '../site/briefing.js';

const now = new Date('2026-11-20T16:00:00Z');
const verifiedAt = now.getTime();
const task = (due_at) => ({ title: 'Revisar documento', status: 'pending', due_at });

test('freshness expires at exactly 15 minutes, never accepts future verification', () => {
  const n = now.getTime();
  assert.equal(recentVerification(n - 15 * 60_000 + 1, n), true);
  assert.equal(recentVerification(n - 15 * 60_000, n), false);
  assert.equal(recentVerification(n + 1, n), false);
});

test('invalid date offsets and impossible timestamps never become due times', () => {
  const invalid = [
    '2026-11-20T09:00:00',
    '2026-02-30T09:00:00Z',
    '2026-11-20T09:00:00+14:30',
    '2026-11-20T09:00:00-12:30',
    '2026-11-20T25:00:00Z',
    '2026-11-20T09:61:00Z',
  ];
  for (const due_at of invalid) {
    const answer = dailyBriefing({ tasks: [task(due_at)], loaded: true, verifiedAt, now });
    assert.match(answer, /1 pendientes/);
    assert.doesNotMatch(answer, /vence /, `Unexpected confirmed due time for ${due_at}`);
    assert.match(answer, /calendario.*no est[aá]n conectados|calendario.*no est[aá] conectado/i);
  }
});

test('cancelled and completed tasks never count as pending', () => {
  const tasks = ['cancelled', 'canceled', 'done', 'completed', 'complete'].map(status => ({title:'Cita cancelada',status}));
  const answer = dailyBriefing({tasks,loaded:true,verifiedAt,now});
  assert.match(answer,/0 pendientes/);
  assert.doesNotMatch(answer,/Cita cancelada/);
});
