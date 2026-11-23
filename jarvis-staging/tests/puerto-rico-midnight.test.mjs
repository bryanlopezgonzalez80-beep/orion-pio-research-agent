import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

// Reproduce: node --test jarvis-staging/tests/puerto-rico-midnight.test.mjs
// No calendar, network, model, or billable provider is used.
const task = due_at => [{title:'Boundary',status:'pending',due_at}];
const brief = (now,due_at,english=true) => dailyBriefing({
  tasks:task(due_at),loaded:true,verifiedAt:Date.parse(now),now:new Date(now),english
});

test('Puerto Rico midnight changes the local day, not the UTC day',()=>{
  const due='2026-11-23T04:30:00Z'; // Nov 23, 00:30 Puerto Rico
  const before=brief('2026-11-23T03:59:00Z',due);
  const after=brief('2026-11-23T04:00:00Z',due);
  assert.match(before,/0 due later today/);
  assert.match(after,/1 due later today/);
  assert.match(after,/12:30 AM/);
});

test('naive deadline cannot be represented as a verified due time',()=>{
  const result=brief('2026-11-23T08:00:00Z','2026-11-23T09:00:00');
  assert.match(result,/0 due later today/);
  assert.doesNotMatch(result,/due Nov 23/);
});

test('impossible calendar date cannot be normalized into a verified deadline',()=>{
  const result=brief('2026-11-23T08:00:00Z','2026-02-30T09:00:00Z');
  assert.match(result,/0 due later today/);
  assert.doesNotMatch(result,/due Feb/);
});

test('bilingual midnight response never asserts a connected calendar',()=>{
  for(const english of [false,true]){
    const result=brief('2026-11-23T04:00:00Z','2026-11-23T04:30:00Z',english);
    assert.match(result,english?/calendar and live traffic are not connected/i:/calendario y el tráfico en vivo no están conectados/i);
  }
});
