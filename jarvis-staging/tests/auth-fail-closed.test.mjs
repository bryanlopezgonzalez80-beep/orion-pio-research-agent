// Run: node --test jarvis-staging/tests/auth-fail-closed.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');
const failure=app.slice(app.lastIndexOf('} catch (error) {'));
test('initial session lookup failure clears private state before showing login',()=>{
 assert.match(failure,/clearIdentity\(\);\s*visible\('login',true\)/);
});
test('clearIdentity aborts pending private requests and resets voice',()=>{
 const body=app.slice(app.indexOf('function clearIdentity(){'),app.indexOf('function updateIdentity(session)'));
 for(const required of ['state.user=null','state.session=null','state.tasks=[]','state.memories=[]','controller.abort()','stopVoice()','state.voiceEnabled=false'])assert.ok(body.includes(required),required);
});
test('auth failure does not call a paid model or write private data',()=>{
 assert.doesNotMatch(failure,/ENABLE_MODEL_REQUESTS|fetch\(|saveTask\(|saveMemory\(/);
});
