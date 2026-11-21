import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing} from '../site/briefing.js';

test('invalid clock input fails closed in Spanish and English without throwing', () => {
  for (const [now,english] of [
    ['not-a-date',false],
    ['not-a-date',true],
    [Number.NaN,false],
    [Number.POSITIVE_INFINITY,true]
  ]) {
    const result=assert.doesNotThrow(()=>dailyBriefing({
      now,english,loaded:true,verifiedAt:Date.now(),
      tasks:[{title:'Cita confirmada a las 9, sal en 12 minutos',status:'pending',due_at:'2026-11-21T09:00:00-04:00'}]
    }));
    const answer=dailyBriefing({now,english,loaded:true,verifiedAt:Date.now(),tasks:[{title:'Cita confirmada a las 9, sal en 12 minutos',status:'pending'}]});
    assert.match(answer,english?/current time is unavailable/i:/hora actual no está disponible/i);
    assert.doesNotMatch(answer,/Cita confirmada|12 minutos|\b1 pending\b|\b1 pendientes\b/i);
  }
});

test('valid clock retains normal briefing behavior',()=>{
  const now=new Date('2026-11-21T02:00:00Z');
  const answer=dailyBriefing({now,verifiedAt:now.getTime(),loaded:true,tasks:[]});
  assert.match(answer,/0 pendientes/);
  assert.match(answer,/calendario y el tráfico en vivo no están conectados/);
});
