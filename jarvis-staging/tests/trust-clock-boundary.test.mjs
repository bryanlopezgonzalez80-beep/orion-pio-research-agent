import test from 'node:test';
import assert from 'node:assert/strict';
import {recentVerification, dailyBriefing, trustedCommand} from '../site/briefing.js';

// Trust & Time Intelligence: fail closed at clock and freshness boundaries.
// Run: node --test jarvis-staging/tests/trust-clock-boundary.test.mjs
test('verification exactly 15 minutes old is stale', () => {
  const now=Date.parse('2026-11-23T04:00:00Z');
  assert.equal(recentVerification(now-15*60*1000,now),false);
  assert.equal(recentVerification(now-15*60*1000+1,now),true);
  assert.equal(recentVerification(now+1,now),false);
});
test('invalid device time never presents stored tasks as verified', () => {
  const result=dailyBriefing({loaded:true,tasks:[{title:'Private task',status:'pending'}],verifiedAt:Date.now(),now:new Date(NaN)});
  assert.match(result,/hora actual no está disponible/i);
  assert.doesNotMatch(result,/Private task/);
});
test('missing recent verification never presents a fabricated empty agenda', () => {
  const result=dailyBriefing({loaded:true,tasks:[],verifiedAt:null,now:new Date('2026-11-23T08:00:00Z'),english:true});
  assert.match(result,/cannot verify your tasks/i);
  assert.doesNotMatch(result,/No pending tasks were recorded/i);
});
test('travel request does not invent departure time or route', () => {
  const answer=trustedCommand('When should I leave?');
  assert.equal(answer?.language,'en');
  assert.match(answer.text,/cannot calculate a reliable departure time/i);
  assert.match(answer.text,/live traffic/i);
  assert.doesNotMatch(answer.text,/\b\d+\s*(?:minutes?|mins?)\b/i);
});
