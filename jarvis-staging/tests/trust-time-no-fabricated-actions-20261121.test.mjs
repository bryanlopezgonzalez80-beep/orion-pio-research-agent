// Run: node --test jarvis-staging/tests/trust-time-no-fabricated-actions-20261121.test.mjs
// Trust & Time: no fabricated calendar, traffic, or action confirmations.
// Offline, deterministic; no credentials, network, paid APIs or private records.
import test from 'node:test';
import assert from 'node:assert/strict';
import {trustedCommand} from '../site/briefing.js';

const now=new Date('2026-11-21T14:00:00-04:00');
const context={
  now,
  loaded:true,
  verifiedAt:now.getTime()-1000,
  tasks:[{title:'PRIVATE_CANARY_MEETING_917',status:'pending',due_at:'2026-11-21T16:00:00-04:00'}]
};

test('calendar questions never disclose private task titles as verified appointments',()=>{
  for(const question of ['¿Tengo alguna reunión?','Do I have any meetings?']){
    const result=trustedCommand(question,context);
    assert.ok(result,'Expected a guarded calendar response');
    assert.doesNotMatch(result.text,/PRIVATE_CANARY_MEETING_917/);
    assert.match(result.text,/calendario|calendar/i);
    assert.doesNotMatch(result.text,/confirmad[ao]s? a las 16|confirmed at 4/i);
  }
});

test('departure questions never infer a route or departure time from saved task deadlines',()=>{
  for(const question of ['¿A qué hora debo salir?','Will I make it to my meeting on time?']){
    const result=trustedCommand(question,context);
    assert.ok(result,'Expected a guarded travel response');
    assert.doesNotMatch(result.text,/PRIVATE_CANARY_MEETING_917/);
    assert.match(result.text,/tráfico|traffic/i);
    assert.doesNotMatch(result.text,/sal a las 15|leave at 3/i);
  }
});

test('stale task verification does not turn into a false empty agenda',()=>{
  const stale={...context,verifiedAt:now.getTime()-15*60*1000};
  for(const question of ['¿Qué tengo hoy?','What do I have today?']){
    const result=trustedCommand(question,stale);
    assert.ok(result,'Expected a guarded briefing');
    assert.doesNotMatch(result.text,/PRIVATE_CANARY_MEETING_917/);
    assert.match(result.text,/actualizar datos|update data/i);
    assert.doesNotMatch(result.text,/0 pendientes|0 pending|no pending tasks were recorded/i);
  }
});
