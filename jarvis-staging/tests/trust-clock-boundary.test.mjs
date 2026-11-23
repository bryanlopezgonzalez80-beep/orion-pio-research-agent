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

test('unparseable clock values fail closed in both languages without throwing', () => {
  for (const now of [Symbol('clock'), 123n, 'not-a-date', new Date(NaN)]) {
    for (const english of [false,true]) {
      const response=dailyBriefing({loaded:true,tasks:[{title:'Private task',status:'pending'}],verifiedAt:Date.now(),now,english});
      assert.match(response,english?/current time is unavailable/i:/hora actual no está disponible/i);
      assert.doesNotMatch(response,/Private task/);
    }
  }
});
test('future verification is not treated as fresh', () => {
  const now=Date.parse('2026-11-23T08:00:00Z');
  assert.equal(recentVerification(now+1000,now),false);
  const response=dailyBriefing({loaded:true,tasks:[{title:'Private task',status:'pending'}],verifiedAt:now+1000,now:new Date(now)});
  assert.match(response,/No puedo verificar tus tareas/i);
  assert.doesNotMatch(response,/Private task/);
});

test('nonfinite and absent verification timestamps never establish freshness', () => {
  const now=Date.parse('2026-11-23T08:00:00Z');
  for (const verifiedAt of [null,undefined,NaN,Infinity,-Infinity,0,-1,'2026-11-23T07:59:00Z']) {
    assert.equal(recentVerification(verifiedAt,now),false);
    for (const english of [false,true]) {
      const answer=dailyBriefing({loaded:true,tasks:[{title:'Confidential task',status:'pending'}],verifiedAt,now:new Date(now),english});
      assert.match(answer,english?/cannot verify your tasks/i:/No puedo verificar tus tareas/i);
      assert.doesNotMatch(answer,/Confidential task/);
    }
  }
});

test('a failed or incomplete task load is never reported as an empty task list', () => {
  const now=Date.parse('2026-11-23T08:00:00Z');
  for (const tasks of [null,{},'unavailable']) {
    const answer=dailyBriefing({loaded:true,tasks,verifiedAt:now,now:new Date(now),english:true});
    assert.match(answer,/cannot verify your tasks/i);
    assert.doesNotMatch(answer,/No pending tasks were recorded/i);
  }
  const notLoaded=dailyBriefing({loaded:false,tasks:[],verifiedAt:now,now:new Date(now)});
  assert.match(notLoaded,/No puedo verificar tus tareas/i);
  assert.doesNotMatch(notLoaded,/No hay tareas pendientes registradas/i);
});
