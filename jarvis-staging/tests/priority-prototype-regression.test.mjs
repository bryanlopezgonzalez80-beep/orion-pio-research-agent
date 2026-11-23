// Run: node --test jarvis-staging/tests/priority-prototype-regression.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

test('unknown inherited-object priority labels do not outrank high priority',()=>{
  const now=new Date('2026-11-22T12:00:00Z');
  const tasks=[
    {title:'Unknown prototype label',priority:'constructor',status:'pending'},
    {title:'High priority task',priority:'high',status:'pending'}
  ];
  const text=dailyBriefing({tasks,loaded:true,verifiedAt:now.getTime(),now,english:true});
  assert.match(text,/2 pending/);
  assert.ok(text.indexOf('High priority task')<text.indexOf('Unknown prototype label'),text);
});

test('unknown __proto__ priority label remains a normal priority',()=>{
  const now=new Date('2026-11-22T12:00:00Z');
  const tasks=[
    {title:'Prototype label',priority:'__proto__',status:'pending'},
    {title:'High priority task',priority:'high',status:'pending'}
  ];
  const text=dailyBriefing({tasks,loaded:true,verifiedAt:now.getTime(),now,english:false});
  assert.ok(text.indexOf('High priority task')<text.indexOf('Prototype label'),text);
});
