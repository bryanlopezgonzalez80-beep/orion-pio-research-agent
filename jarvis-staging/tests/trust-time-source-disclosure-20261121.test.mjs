// Run: node --test jarvis-staging/tests/trust-time-source-disclosure-20261121.test.mjs
// Deterministic, offline checks: no network, credentials or user records.
import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, trustedCommand} from '../site/briefing.js';

const now=new Date('2026-11-21T14:00:00-04:00');
const context={now,loaded:true,verifiedAt:now.getTime()-1000,tasks:[
  {title:'CANARY_PRIVATE_TASK_91',status:'pending',due_at:'2026-11-21T17:00:00-04:00',priority:'high'}
]};

test('bilingual briefing identifies task source and does not claim calendar access',()=>{
  for(const english of [false,true]){
    const response=dailyBriefing({...context,english});
    assert.match(response,english?/JARVIS tasks verified at/i:/tareas de JARVIS verificadas a las/i);
    assert.match(response,english?/calendar.*not connected/i:/calendario.*no est[aá]n conectados/i);
    assert.match(response,/CANARY_PRIVATE_TASK_91/);
    assert.doesNotMatch(response,/meeting confirmed|reuni[oó]n confirmada|calendar synced|calendario sincronizado/i);
  }
});

test('calendar and departure requests never reveal private task or fabricate an ETA',()=>{
  for(const utterance of ['Do I have any meetings?','¿Tengo una reunión?','When should I leave?','¿A qué hora debo salir?']){
    const response=trustedCommand(utterance,context);
    assert.ok(response,'Expected guarded response: '+utterance);
    assert.doesNotMatch(response.text,/CANARY_PRIVATE_TASK_91/);
    assert.match(response.text,/calendar|calendario|traffic|tr[aá]fico|tr[aá]nsito/i);
    assert.doesNotMatch(response.text,/\b(?:15|20|30|45) (?:minutes|minutos)\b/i);
  }
});

test('failed refresh cannot leak task titles or claim there are no pending tasks',()=>{
  for(const english of [false,true]){
    const response=dailyBriefing({...context,loaded:false,english});
    assert.doesNotMatch(response,/CANARY_PRIVATE_TASK_91/);
    assert.doesNotMatch(response,/0 pending|0 pendientes|no pending tasks|no hay tareas pendientes/i);
    assert.match(response,english?/cannot verify/i:/no puedo verificar/i);
  }
});
