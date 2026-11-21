// Run: node --test jarvis-staging/tests/trust-time-verified-boundary-20261121.test.mjs
// Offline deterministic trust-boundary checks; no external services or personal records.
import test from 'node:test';
import assert from 'node:assert/strict';
import {recentVerification, dailyBriefing, trustedCommand, MAX_TASK_AGE_MS} from '../site/briefing.js';

const now=new Date('2026-11-21T14:00:00-04:00');
const privateTask={title:'PRIVATE_BOUNDARY_CANARY_632',status:'pending',due_at:'2026-11-21T16:00:00-04:00'};

test('verification expires exactly at 15 minutes and rejects future timestamps',()=>{
  assert.equal(recentVerification(now.getTime()-MAX_TASK_AGE_MS+1,now.getTime()),true);
  assert.equal(recentVerification(now.getTime()-MAX_TASK_AGE_MS,now.getTime()),false);
  assert.equal(recentVerification(now.getTime()+1,now.getTime()),false);
  assert.equal(recentVerification(Number.NaN,now.getTime()),false);
});

test('expired data never exposes private task canary or claims an empty agenda',()=>{
  const text=dailyBriefing({tasks:[privateTask],loaded:true,verifiedAt:now.getTime()-MAX_TASK_AGE_MS,now});
  assert.doesNotMatch(text,/PRIVATE_BOUNDARY_CANARY_632/);
  assert.match(text,/actualizar datos/i);
  assert.doesNotMatch(text,/0 pendientes|no hay tareas pendientes/i);
});

test('travel and calendar commands do not repurpose task deadlines as verified events',()=>{
  const ctx={tasks:[privateTask],loaded:true,verifiedAt:now.getTime()-1000,now};
  for(const q of ['¿A qué hora debo salir?','Will I make it to my meeting on time?','¿Tengo una reunión?','Do I have any meetings?']){
    const result=trustedCommand(q,ctx);
    assert.ok(result,'Guarded command required: '+q);
    assert.doesNotMatch(result.text,/PRIVATE_BOUNDARY_CANARY_632/);
    assert.doesNotMatch(result.text,/leave at 3|sal a las 15|confirmed at 4|confirmada a las 16/i);
  }
});
