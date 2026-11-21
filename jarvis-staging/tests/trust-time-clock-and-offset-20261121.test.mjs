// Run: node --test jarvis-staging/tests/trust-time-clock-and-offset-20261121.test.mjs
// Offline integration checks against the real briefing module; no accounts or APIs.
import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, recentVerification} from '../site/briefing.js';

const now=new Date('2026-11-22T00:30:00Z'); // Nov 21, 20:30 in Puerto Rico
const base={now,loaded:true,verifiedAt:now.getTime()-1000};

test('UTC midnight does not change the Puerto Rico local day',()=>{
  const result=dailyBriefing({...base,tasks:[{title:'LOCAL_DAY_CANARY',status:'pending',due_at:'2026-11-21T21:00:00-04:00'}]});
  assert.match(result,/1 con vencimiento más tarde hoy/);
  assert.match(result,/LOCAL_DAY_CANARY/);
  assert.doesNotMatch(result,/reuni[oó]n confirmada/i);
});

test('offset-free and impossible due dates are never spoken as appointments or deadlines',()=>{
  const result=dailyBriefing({...base,tasks:[
    {title:'NAIVE_CANARY',status:'pending',due_at:'2026-11-21T22:00:00'},
    {title:'IMPOSSIBLE_CANARY',status:'pending',due_at:'2026-02-30T12:00:00-04:00'},
    {title:'OFFSET_CANARY',status:'pending',due_at:'2026-11-21T22:00:00+15:00'}
  ]});
  assert.match(result,/3 pendientes/);
  assert.doesNotMatch(result,/vence |atrasadas|citas confirmadas/);
  assert.match(result,/0 atrasadas y 0 con vencimiento/);
  assert.match(result,/calendario.*no est[aá]n conectados/i);
});

test('verification at exactly 15 minutes is stale, including across midnight',()=>{
  const stamp=now.getTime()-15*60*1000;
  assert.equal(recentVerification(stamp,now.getTime()),false);
  assert.equal(recentVerification(stamp+1,now.getTime()),true);
  const result=dailyBriefing({...base,verifiedAt:stamp,tasks:[{title:'STALE_PRIVATE_CANARY',status:'pending'}]});
  assert.doesNotMatch(result,/STALE_PRIVATE_CANARY/);
  assert.match(result,/No puedo verificar/);
});
