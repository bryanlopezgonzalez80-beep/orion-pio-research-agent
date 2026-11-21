import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';
const now=new Date('2026-11-21T12:00:00Z');
const verifiedAt=now.getTime()-1000;
const base={loaded:true,verifiedAt,now};

test('impossible due date never becomes an overdue commitment',()=>{
 const result=dailyBriefing({...base,tasks:[{title:'Review report',status:'pending',priority:'normal',due_at:'2026-02-30T09:00:00-04:00'}],english:true});
 assert.match(result,/1 pending, 0 overdue and 0 due later today/);
 assert.doesNotMatch(result,/due Feb/);
 assert.match(result,/not appointments/);
});

test('naive due date never acquires an invented timezone',()=>{
 const result=dailyBriefing({...base,tasks:[{title:'Check draft',status:'pending',due_at:'2026-11-21T08:00:00'}],english:true});
 assert.match(result,/1 pending, 0 overdue and 0 due later today/);
 assert.doesNotMatch(result,/due Nov/);
});

test('valid offset timestamp counts overdue in Puerto Rico',()=>{
 const result=dailyBriefing({...base,tasks:[{title:'Review notes',status:'pending',due_at:'2026-11-21T07:00:00-04:00'}],english:true});
 assert.match(result,/1 pending, 1 overdue and 0 due later today/);
 assert.match(result,/due Nov 21/);
});
