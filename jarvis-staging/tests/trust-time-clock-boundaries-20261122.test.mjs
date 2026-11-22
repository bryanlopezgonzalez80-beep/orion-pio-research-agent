// Run from repository root: node --test jarvis-staging/tests/trust-time-clock-boundaries-20261122.test.mjs
// Integration tests against the actual briefing module; no network or paid APIs.
import test from 'node:test';
import assert from 'node:assert/strict';
import { dailyBriefing, recentVerification, trustedCommand } from '../site/briefing.js';

const now = new Date('2026-11-22T06:00:00.000Z'); // 02:00 in Puerto Rico
const task = {title:'Revisar informe',status:'pending',priority:'high',due_at:'2026-11-22T03:00:00-04:00'};

test('verification expires at the exact 15-minute boundary, in both languages', () => {
  const t = now.getTime();
  assert.equal(recentVerification(t - 899999,t),true);
  assert.equal(recentVerification(t - 900000,t),false);
  for(const english of [false,true]){
    const output=dailyBriefing({tasks:[task],loaded:true,verifiedAt:t-900000,now,english});
    assert.doesNotMatch(output,/Revisar informe/);
    assert.match(output,english?/cannot verify/i:/No puedo verificar/i);
  }
});

test('invalid device time fails closed without leaking private task titles', () => {
  for(const invalid of [new Date(NaN), Symbol('invalid'), 1n]){
    for(const english of [false,true]){
      const output=dailyBriefing({tasks:[task],loaded:true,verifiedAt:now.getTime(),now:invalid,english});
      assert.doesNotMatch(output,/Revisar informe/);
      assert.match(output,english?/current time is unavailable/i:/hora actual no está disponible/i);
    }
  }
});

test('arrival queries do not infer departure from a saved task', () => {
  for(const input of ['¿Llegaré a tiempo?', 'Can I make it on time?']){
    const response=trustedCommand(input,{tasks:[task],loaded:true,verifiedAt:now.getTime(),now});
    assert.ok(response);
    assert.doesNotMatch(response.text,/Revisar informe/);
    assert.match(response.text,/tráfico|traffic/i);
    assert.doesNotMatch(response.text,/\b\d+\s*(?:minutos|minutes)\b/i);
  }
});
