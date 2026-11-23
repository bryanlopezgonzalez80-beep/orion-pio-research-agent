// Run: node --test jarvis-staging/tests/travel-trust-contract.test.mjs
// Trust & Time acceptance: no route, ETA, meeting or departure time without authorized sources.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand, trustedCommand, dailyBriefing} from '../site/briefing.js';

const cases=[
  ['¿A qué hora debo salir?', 'es'],
  ['¿Voy a llegar tarde?', 'es'],
  ['Should I leave now?', 'en'],
  ['Will I be late?', 'en'],
];
for(const [phrase,language] of cases){
  test(`travel request refuses unsupported ETA: ${phrase}`,()=>{
    assert.equal(classifyCommand(phrase),'travel');
    const response=trustedCommand(phrase,{tasks:[{title:'Meeting at 9',due_at:'2026-11-23T09:00:00-04:00'}],loaded:true,verifiedAt:Date.now()});
    assert.equal(response.language,language);
    assert.match(response.text,language==='es'?/No puedo calcular una hora fiable/:/I cannot calculate a reliable departure time/);
    assert.doesNotMatch(response.text,/\b(?:[0-9]{1,2}:[0-9]{2}|[0-9]+\s*(?:minutos|minutes|km|miles))\b/i);
  });
}
test('calendar cannot be inferred from a task title',()=>{
  const response=trustedCommand('¿Tengo alguna reunión?',{tasks:[{title:'Reunión 9 AM'}],loaded:true,verifiedAt:Date.now()});
  assert.equal(response.language,'es');
  assert.match(response.text,/calendario aún no está conectado/);
  assert.doesNotMatch(response.text,/Reunión 9 AM/);
});
test('stale task cache is not reported as verified',()=>{
  const now=new Date('2026-11-23T12:00:00Z');
  const response=dailyBriefing({tasks:[{title:'Important',status:'pending'}],loaded:true,verifiedAt:now.getTime()-15*60*1000,now,english:true});
  assert.match(response,/cannot verify your tasks with recent data/);
  assert.doesNotMatch(response,/1 pending/);
});
