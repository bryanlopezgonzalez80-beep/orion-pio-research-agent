import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand, safeTaskTitle, dailyBriefing} from '../site/briefing.js';

const now=new Date('2026-11-20T08:00:00.000Z');
const context={loaded:true,verifiedAt:now.getTime(),now,tasks:[{title:'Private task, not a meeting',status:'pending',due_at:'2026-11-20T09:00:00-04:00'}]};

test('calendar questions never leak task titles as verified appointments',()=>{
  for(const phrase of ['Is my next meeting at nine?','Can you tell me where my next appointment is?','¿Tengo una cita mañana?']){
    assert.equal(classifyCommand(phrase),'calendar',phrase);
    const result=trustedCommand(phrase,context);
    assert.ok(result,phrase);
    assert.doesNotMatch(result.text,/Private task|09:00|confirmed meeting/i,phrase);
    assert.match(result.text,/calendar|calendario/i,phrase);
  }
});

test('travel advice fails closed without authorized routes and calendar',()=>{
  for(const phrase of ['What time should I leave?','¿A qué hora debo salir?']){
    const result=trustedCommand(phrase,context);
    assert.ok(result,phrase);
    assert.doesNotMatch(result.text,/Private task|09:00|\b\d+ minutes\b/i,phrase);
    assert.match(result.text,/traffic|tráfico/i,phrase);
  }
});

test('spoken titles strip invisible direction controls without dropping words',()=>{
  const clean=safeTaskTitle('Review\u202E secret\u2066 notes\u0000',true);
  assert.equal(clean,'Review secret notes');
  assert.doesNotMatch(clean,/[\u0000-\u001f\u007f-\u009f\u202a-\u202e\u2066-\u2069]/);
});

test('invalid and stale synchronization cannot yield task counts',()=>{
  for(const verifiedAt of [null,NaN,now.getTime()+1000,now.getTime()-15*60*1000]){
    const response=dailyBriefing({...context,verifiedAt});
    assert.match(response,/No puedo verificar/i);
    assert.doesNotMatch(response,/Private task|1 pendientes/i);
  }
});
