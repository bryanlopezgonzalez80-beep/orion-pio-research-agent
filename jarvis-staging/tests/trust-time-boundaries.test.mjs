import test from 'node:test';
import assert from 'node:assert/strict';
import {recentVerification, dailyBriefing, trustedCommand, MAX_TASK_AGE_MS} from '../site/briefing.js';

const now = new Date('2026-11-20T07:00:00.000Z');
const pending = [{title:'Preparar informe',status:'pending',due_at:'2026-11-20T10:00:00-04:00'}];

test('verification freshness rejects the exact expiry boundary and future timestamps',()=>{
  assert.equal(recentVerification(now.getTime()-MAX_TASK_AGE_MS,now.getTime()),false);
  assert.equal(recentVerification(now.getTime()-MAX_TASK_AGE_MS+1,now.getTime()),true);
  assert.equal(recentVerification(now.getTime()+1,now.getTime()),false);
  assert.equal(recentVerification(NaN,now.getTime()),false);
});

test('expired verification never produces confirmed task counts in either language',()=>{
  for(const english of [false,true]){
    const response=dailyBriefing({tasks:pending,loaded:true,verifiedAt:now.getTime()-MAX_TASK_AGE_MS,now,english});
    assert.match(response,/cannot verify|no puedo verificar/i);
    assert.doesNotMatch(response,/1 pending|1 pendientes|Preparar informe/i);
  }
});

test('calendar and travel answers cannot inherit unverified tasks as appointments',()=>{
  for(const phrase of ['Do I have an appointment tomorrow?','¿Tengo una cita mañana?','What time should I leave?','¿A qué hora debo salir?']){
    const response=trustedCommand(phrase,{tasks:pending,loaded:true,verifiedAt:now.getTime(),now});
    assert.ok(response,phrase);
    assert.doesNotMatch(response.text,/Preparar informe|10:00|confirmed appointment|cita confirmada/i,phrase);
    assert.match(response.text,/calendar|calendario|traffic|tráfico/i,phrase);
  }
});
