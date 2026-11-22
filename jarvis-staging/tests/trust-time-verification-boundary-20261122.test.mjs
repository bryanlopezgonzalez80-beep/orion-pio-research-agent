// Run: node --test jarvis-staging/tests/trust-time-verification-boundary-20261122.test.mjs
// Offline safety regression: never accept future, missing or expired verification timestamps.
import test from 'node:test';
import assert from 'node:assert/strict';
import {recentVerification, dailyBriefing, trustedCommand, MAX_TASK_AGE_MS} from '../site/briefing.js';

const now = Date.parse('2026-11-22T13:00:00.000Z');
const privateTask = [{title:'PRIVATE_TASK_SENTINEL',status:'pending',due_at:'2026-11-22T14:00:00Z'}];

test('verification timestamps fail closed at exact freshness boundary',()=>{
  for(const timestamp of [null,undefined,NaN,Infinity,-1,0,now+1,now-MAX_TASK_AGE_MS,now-MAX_TASK_AGE_MS-1]){
    assert.equal(recentVerification(timestamp,now),false,String(timestamp));
  }
  assert.equal(recentVerification(now-MAX_TASK_AGE_MS+1,now),true);
  assert.equal(recentVerification(now,now),true);
});

test('stale, future and missing verification never disclose private task titles in bilingual voice',()=>{
  for(const verifiedAt of [null,0,now+1,now-MAX_TASK_AGE_MS]){
    for(const english of [false,true]){
      const text=dailyBriefing({tasks:privateTask,loaded:true,verifiedAt,now:new Date(now),english});
      assert.doesNotMatch(text,/PRIVATE_TASK_SENTINEL/);
      assert.match(text,english?/cannot verify your tasks/i:/no puedo verificar tus tareas/i);
    }
  }
});

test('voice briefing refuses to claim unverified task data',()=>{
  for(const phrase of ['¿Qué tengo hoy?','What I got to do today?']){
    const result=trustedCommand(phrase,{tasks:privateTask,loaded:true,verifiedAt:now+1,now:new Date(now)});
    assert.ok(result,phrase);
    assert.doesNotMatch(result.text,/PRIVATE_TASK_SENTINEL/);
    assert.match(result.text,/no puedo verificar|cannot verify/i);
  }
});
