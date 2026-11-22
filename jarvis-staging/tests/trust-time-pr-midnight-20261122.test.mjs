// Run: node --test jarvis-staging/tests/trust-time-pr-midnight-20261122.test.mjs
// Puerto Rico local midnight must not be confused with UTC midnight. Offline only.
import test from 'node:test';
import assert from 'node:assert/strict';
import {dailyBriefing, trustedCommand} from '../site/briefing.js';

const now=new Date('2026-11-22T03:30:00.000Z'); // Nov 21, 11:30 PM in Puerto Rico
const verifiedAt=now.getTime();
const tasks=[
  {title:'LOCAL_TODAY_21',status:'pending',priority:'normal',due_at:'2026-11-21T23:45:00-04:00'},
  {title:'LOCAL_TOMORROW_22',status:'pending',priority:'normal',due_at:'2026-11-22T00:15:00-04:00'}
];
const context={loaded:true,now,verifiedAt,tasks};

test('local day boundary: only Nov 21 deadline counts as due today',()=>{
  for(const english of [false,true]){
    const response=dailyBriefing({...context,english});
    assert.match(response,english?/1 due later today/:/1 con vencimiento más tarde hoy/);
    assert.match(response,/LOCAL_TODAY_21/);
    assert.match(response,/LOCAL_TOMORROW_22/);
    assert.match(response,english?/not appointments/:/no citas/);
  }
});

test('calendar and travel questions at UTC midnight cannot expose task titles',()=>{
  for(const phrase of ['¿Tengo una reunión?','Do I have a meeting?','¿A qué hora debo salir?','When should I leave?']){
    const response=trustedCommand(phrase,context);
    assert.ok(response,phrase);
    assert.doesNotMatch(response.text,/LOCAL_TODAY_21|LOCAL_TOMORROW_22/,phrase);
    assert.match(response.text,/calendario|calendar|tráfico|traffic/i,phrase);
  }
});
