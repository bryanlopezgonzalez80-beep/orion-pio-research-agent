// Run: node --test jarvis-staging/tests/trust-time-voice-input-safety.test.mjs
// Regression coverage for hostile or malformed speech-recognition inputs.
// No network, credentials, paid model calls, or private user data.
import test from 'node:test';
import assert from 'node:assert/strict';
import {normalizedPhrase, classifyCommand, englishIntent, safeTaskTitle} from '../site/briefing.js';

test('speech intent tolerates null, numbers and object input without throwing',()=>{
  for(const value of [null,undefined,0,42,{},[],true]){
    assert.doesNotThrow(()=>normalizedPhrase(value));
    assert.doesNotThrow(()=>classifyCommand(value));
    assert.doesNotThrow(()=>englishIntent(value));
  }
});

test('control and bidi characters cannot alter calendar/travel safety classification',()=>{
  assert.equal(classifyCommand('JARVIS, ¿a qué hora debo\u202e salir?'),'travel');
  assert.equal(classifyCommand('Will I make it\u200b to my meeting on time?'),'travel');
  assert.equal(classifyCommand('Do I have any\u2066 meetings?'),'calendar');
});

test('voice output titles remove invisible controls and stay bounded',()=>{
  const title=safeTaskTitle('Private\u202e\u0000 task  '.repeat(30));
  assert.ok(title.length<=120);
  assert.doesNotMatch(title,/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060\u2066-\u2069\ufeff]/);
  assert.equal(safeTaskTitle(null,true),'Untitled');
  assert.equal(safeTaskTitle(null,false),'Sin título');
});
