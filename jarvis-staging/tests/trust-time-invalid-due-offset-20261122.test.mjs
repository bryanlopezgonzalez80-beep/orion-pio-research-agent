// Run: node --test jarvis-staging/tests/trust-time-invalid-due-offset-20261122.test.mjs
// Uses the real briefing module; no network, credentials, or paid APIs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

const now=new Date('2026-11-22T08:00:00.000Z');
const base={now,verifiedAt:now.getTime(),loaded:true};
function brief(due_at,english=false){
  return dailyBriefing({...base,english,tasks:[{title:'Boundary task',status:'pending',priority:'normal',due_at}]});
}

test('invalid timezone offsets never become verified due times',()=>{
  for(const due of [
    '2026-11-22T09:00:00+14:01',
    '2026-11-22T09:00:00-12:01',
    '2026-11-22T09:00:00+04:60',
    '2026-11-22T09:00:00+99:00',
    '2026-11-22T09:00:00'
  ]){
    for(const english of [false,true]){
      const result=brief(due,english);
      assert.match(result,/Boundary task/);
      assert.doesNotMatch(result,english?/\bdue\s+Nov\b/i:/\bvence\s+nov\b/i,due);
      assert.match(result,/calendar|calendario/i);
    }
  }
});

test('impossible leap dates and hours cannot be normalized into deadlines',()=>{
  for(const due of [
    '2026-02-29T09:00:00Z',
    '2026-11-31T09:00:00Z',
    '2026-11-22T24:00:00Z',
    '2026-11-22T09:60:00Z'
  ]){
    const result=brief(due);
    assert.match(result,/Boundary task/);
    assert.doesNotMatch(result,/\bvence\s+nov\b/i,due);
  }
});

test('valid offset due time is shown as a task, not a confirmed appointment',()=>{
  const result=brief('2026-11-22T09:00:00-04:00',true);
  assert.match(result,/Boundary task/);
  assert.match(result,/due Nov/i);
  assert.match(result,/not appointments/i);
  assert.match(result,/not connected/i);
});
