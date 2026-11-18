// Reproduce: node --test jarvis-staging/tests/pagehide-voice.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');
test('pagehide always stops voice before Safari navigates away',()=>{
 assert.match(app,/window\.addEventListener\('pagehide',\(\)=>\{\s*\/\/[^\n]*\n\s*stopVoice\(\);\s*\}\);/);
});
test('background transition independently stops voice',()=>{
 assert.match(app,/document\.addEventListener\('visibilitychange',\(\)=>\{\s*if\(document\.hidden\)\{stopVoice\(\)/);
});
test('stopVoice cancels microphone and speech and disables dialogue',()=>{
 const body=app.slice(app.indexOf('function stopVoice(){'),app.indexOf('function pauseDialogue(',app.indexOf('function stopVoice(){')));
 for(const item of ['state.dialogEnabled=false','cancelRecognition()','cancelSpeech()','clearRearm()'])assert.ok(body.includes(item),item);
});
test('pagehide handler does not make requests or alter user data',()=>{
 const body=app.slice(app.indexOf("window.addEventListener('pagehide'"),app.indexOf("window.addEventListener('focus'",app.indexOf("window.addEventListener('pagehide'")));
 assert.doesNotMatch(body,/fetch\(|request\(|supabase\.|localStorage|loadWorkspace\(|saveTask\(/);
});

test('voice shutdown invalidates delayed recognition callbacks',()=>{
 const cancel=app.slice(app.indexOf('function cancelRecognition(){'),app.indexOf('function cancelSpeech(){'));
 assert.match(cancel,/state\.listenSequence\s*\+=\s*1/);
 assert.match(cancel,/rec\.onresult=rec\.onerror=rec\.onend=null/);
 assert.match(cancel,/rec\.abort\(\)/);
});
test('voice shutdown invalidates delayed speech callbacks',()=>{
 const cancel=app.slice(app.indexOf('function cancelSpeech(){'),app.indexOf('function stopVoice(){'));
 assert.match(cancel,/state\.speechSequence\s*\+=\s*1/);
 assert.match(cancel,/state\.activeUtterance=null/);
 assert.match(cancel,/speechSynthesis\.cancel\(\)/);
});
test('pagehide never triggers automatic rearming of the microphone',()=>{
 const handler=app.slice(app.indexOf("window.addEventListener('pagehide'"),app.indexOf("window.addEventListener('focus'",app.indexOf("window.addEventListener('pagehide'")));
 assert.doesNotMatch(handler,/scheduleRearm|beginListening|startDialogue|setVoiceEnabled/);
});
