import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

test('unconstructable clock inputs fail closed without disclosing task titles',()=>{
  const tasks=[{title:'Private meeting 09:00; depart in 12 minutes',status:'pending',due_at:'2026-11-21T09:00:00-04:00'}];
  for(const now of [Symbol('invalid clock'),1n,{valueOf(){throw new Error('invalid clock');}}]){
    for(const english of [false,true]){
      let answer;
      assert.doesNotThrow(()=>{answer=dailyBriefing({now,english,loaded:true,verifiedAt:Date.now(),tasks});});
      assert.match(answer,english?/current time is unavailable/i:/hora actual no está disponible/i);
      assert.doesNotMatch(answer,/Private meeting|09:00|12 minutes|1 pending|1 pendientes/i);
    }
  }
});

test('valid timestamp still generates task briefing',()=>{
  const now=new Date('2026-11-21T02:00:00Z');
  const answer=dailyBriefing({now,verifiedAt:now.getTime(),loaded:true,tasks:[]});
  assert.match(answer,/0 pendientes/);
  assert.match(answer,/calendario y el tráfico en vivo no están conectados/);
});
