import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

const now=new Date('2026-11-20T13:00:00.000Z');
const verifiedAt=now.getTime();
const brief=(tasks,english=false)=>dailyBriefing({tasks,loaded:true,verifiedAt,now,english});

test('cancelled and completed tasks are never presented as pending',()=>{
  const result=brief([
    {title:'Cancelled private appointment',status:'cancelled',due_at:'2026-11-20T14:00:00-04:00'},
    {title:'Completed private appointment',status:'completed',due_at:'2026-11-20T14:00:00-04:00'}
  ]);
  assert.doesNotMatch(result,/Cancelled private appointment|Completed private appointment/i);
});

test('timezone-less and invalid calendar dates are not converted to confirmed deadlines',()=>{
  const result=brief([
    {title:'Naive date',status:'pending',due_at:'2026-11-20T10:00:00'},
    {title:'Impossible date',status:'pending',due_at:'2026-02-30T10:00:00-04:00'},
    {title:'Impossible offset',status:'pending',due_at:'2026-11-20T10:00:00+15:00'}
  ],true);
  assert.doesNotMatch(result,/Nov 20|Feb 30|10:00 AM/i);
});

test('task titles with control characters are sanitized in spoken briefing',()=>{
  const result=brief([{title:'Review\u202E hidden\u0000 item',status:'pending'}],true);
  assert.doesNotMatch(result,/[\u0000-\u001f\u007f-\u009f\u202a-\u202e]/);
});
