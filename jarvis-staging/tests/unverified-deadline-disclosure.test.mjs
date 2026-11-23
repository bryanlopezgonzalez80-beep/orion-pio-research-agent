import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

// Run: node --test jarvis-staging/tests/unverified-deadline-disclosure.test.mjs
const now=new Date('2026-11-23T14:00:00Z');
function brief(due_at,english=false){
  return dailyBriefing({tasks:[{title:'Private task',status:'pending',due_at}],
    loaded:true,verifiedAt:now.getTime(),now,english});
}
test('timezone-less deadline is disclosed in Spanish without asserting a due time',()=>{
  const result=brief('2026-11-23T16:00:00');
  assert.match(result,/1 vencimiento\(s\).*no se pudieron verificar/);
  assert.match(result,/0 con vencimiento más tarde hoy/);
  assert.doesNotMatch(result,/vence nov/i);
});
test('impossible date is disclosed in English',()=>{
  const result=brief('2026-02-30T12:00:00Z',true);
  assert.match(result,/1 task deadline\(s\) could not be verified/);
  assert.doesNotMatch(result,/due Feb/i);
});
test('legitimate task without a due date is not treated as malformed',()=>{
  assert.doesNotMatch(brief(null,true),/could not be verified/);
});
test('valid offset-aware deadline is not flagged',()=>{
  assert.doesNotMatch(brief('2026-11-23T16:00:00Z'),/no se pudieron verificar/);
});
