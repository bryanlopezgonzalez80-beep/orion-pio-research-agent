// Run: node --test jarvis-staging/tests/trust-time-private-title-voice-20261122.test.mjs
// No network, credentials, or model calls. Tests the real local briefing module.
import test from 'node:test';
import assert from 'node:assert/strict';
import {trustedCommand, dailyBriefing} from '../site/briefing.js';

const now=new Date('2026-11-22T07:00:00.000Z');
const privateTitle='CONFIDENTIAL-PRIVATE-TASK-DO-NOT-REVEAL';
const context={now,loaded:true,verifiedAt:now.getTime(),tasks:[{title:privateTitle,status:'pending',priority:'high',due_at:'2026-11-22T08:00:00-04:00'}]};

test('calendar queries do not leak a private task title or claim a connected calendar',()=>{
  for(const phrase of ['¿Tengo alguna cita?','Do I have any appointments?','When is my next meeting?']){
    const result=trustedCommand(phrase,context);
    assert.ok(result,phrase);
    assert.equal(result.text.includes(privateTitle),false,phrase);
    assert.match(result.text,/calendario|calendar/i,phrase);
    assert.match(result.text,/no (?:he consultado|calendar events have been checked)|not connected/i,phrase);
  }
});

test('departure questions never infer traffic, location, or meeting from private tasks',()=>{
  for(const phrase of ['¿Llegaré a tiempo?','Can I make it on time?','¿A qué hora debo salir?','When should I leave?']){
    const result=trustedCommand(phrase,context);
    assert.ok(result,phrase);
    assert.equal(result.text.includes(privateTitle),false,phrase);
    assert.match(result.text,/tráfico|traffic/i,phrase);
    assert.doesNotMatch(result.text,/\b\d+\s*(?:minutos|minutes)\b/i,phrase);
  }
});

test('a stale verification does not expose a private task in either language',()=>{
  for(const english of [false,true]){
    const result=dailyBriefing({...context,verifiedAt:now.getTime()-15*60*1000,english});
    assert.equal(result.includes(privateTitle),false);
    assert.match(result,/No puedo verificar|cannot verify/i);
  }
});
