// Run: node --test jarvis-staging/tests/trust-time-spanish-arrival-20261121.test.mjs
// Offline regression against the actual local module; no network, paid APIs, or calendar writes.
import test from 'node:test';
import assert from 'node:assert/strict';
import {classifyCommand,trustedCommand} from '../site/briefing.js';

test('Spanish future arrival questions require verified route inputs',()=>{
  for(const phrase of [
    '¿Llegaré a tiempo a mi cita?',
    '¿Llegaré a tiempo a la reunión?',
    '¿Alcanzaré a llegar a tiempo al médico?',
    'Jarvis, ¿llegaré a tiempo al dentista?'
  ]){
    assert.equal(classifyCommand(phrase),'travel',phrase);
    const result=trustedCommand(phrase,{tasks:[{title:'PRIVATE_CANARY',status:'pending'}]});
    assert.equal(result?.language,'es',phrase);
    assert.match(result.text,/No puedo calcular una hora fiable para salir/);
    assert.match(result.text,/punto de partida autorizado/);
    assert.doesNotMatch(result.text,/PRIVATE_CANARY|\b\d+ minutos\b/);
  }
});
test('unrelated Spanish question is not treated as a journey',()=>{
  assert.equal(classifyCommand('¿Llegaré a entender esta lección?'),null);
});
