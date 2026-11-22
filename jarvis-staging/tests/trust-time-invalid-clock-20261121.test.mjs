// Run: node --test jarvis-staging/tests/trust-time-invalid-clock-20261121.test.mjs
// No network, external providers, or billable requests.
import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing,recentVerification} from '../site/briefing.js';

const privateTask={title:'PRIVATE_CLOCK_CANARY',status:'pending',due_at:'2026-11-22T09:00:00-04:00'};

test('invalid device clock fails closed in Spanish and English without leaking tasks',()=>{
  for(const english of [false,true]){
    for(const now of [new Date(NaN),Symbol('bad clock'),1n,'not-a-date']){
      const response=dailyBriefing({tasks:[privateTask],loaded:true,verifiedAt:Date.now(),now,english});
      assert.equal(typeof response,'string');
      assert.doesNotMatch(response,/PRIVATE_CLOCK_CANARY/);
      assert.match(response,english?/current time is unavailable/:/hora actual no está disponible/);
      assert.match(response,english?/calendar is not connected/:/calendario aún no está conectado/);
    }
  }
});

test('future verification timestamps and exact freshness boundary are not trusted',()=>{
  const now=Date.parse('2026-11-21T23:00:00Z');
  assert.equal(recentVerification(now+1,now),false);
  assert.equal(recentVerification(now-15*60*1000,now),false);
  assert.equal(recentVerification(now-15*60*1000+1,now),true);
  for(const verifiedAt of [now+1,now-15*60*1000]){
    const result=dailyBriefing({tasks:[privateTask],loaded:true,verifiedAt,now:new Date(now)});
    assert.doesNotMatch(result,/PRIVATE_CLOCK_CANARY/);
    assert.match(result,/No puedo verificar tus tareas/);
  }
});
