import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, recentVerification, trustedCommand, MAX_TASK_AGE_MS} from '../site/briefing.js';

const now=new Date('2026-11-21T12:00:00Z');
const privateTask={title:'Private planning note',status:'pending',due_at:'2026-11-21T14:00:00Z'};
const context=(verifiedAt)=>({tasks:[privateTask],loaded:true,verifiedAt,now});

test('a verification timestamp from the future is never trusted',()=>{
  const future=now.getTime()+1000;
  assert.equal(recentVerification(future,now.getTime()),false);
  const answer=dailyBriefing({...context(future),english:true});
  assert.match(answer,/cannot verify your tasks/i);
  assert.doesNotMatch(answer,/Private planning note/);
});

test('exactly 15 minutes old is stale; just inside the limit is fresh',()=>{
  const atLimit=now.getTime()-MAX_TASK_AGE_MS;
  assert.equal(recentVerification(atLimit,now.getTime()),false);
  assert.equal(recentVerification(atLimit+1,now.getTime()),true);
  const stale=dailyBriefing({...context(atLimit),english:true});
  assert.match(stale,/cannot verify your tasks/i);
  assert.doesNotMatch(stale,/Private planning note/);
  const fresh=dailyBriefing({...context(atLimit+1),english:true});
  assert.match(fresh,/Private planning note/);
});

test('unverified task titles never become calendar or travel evidence',()=>{
  const stale=context(now.getTime()-MAX_TASK_AGE_MS);
  for(const question of ['What time is my appointment?','When should I leave?']){
    const result=trustedCommand(question,stale);
    assert.ok(result);
    assert.doesNotMatch(result.text,/Private planning note/);
    assert.doesNotMatch(result.text,/\b(?:15|30|45) minutes\b/i);
  }
});

test('a failed load does not pretend there are zero pending tasks',()=>{
  const answer=dailyBriefing({...context(now.getTime()-1000),loaded:false});
  assert.match(answer,/No puedo verificar tus tareas/i);
  assert.doesNotMatch(answer,/0 pendientes/);
  assert.doesNotMatch(answer,/Private planning note/);
});
