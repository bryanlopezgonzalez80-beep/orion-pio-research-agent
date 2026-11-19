// Run: node --test jarvis-staging/tests/voice-first-ui.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const html=await readFile(new URL('../site/index.html',import.meta.url),'utf8');
const css=await readFile(new URL('../site/styles.css',import.meta.url),'utf8');
const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');
test('UI IDs remain unique and all direct app element lookups exist',()=>{
 const ids=[...html.matchAll(/\bid="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(ids.length,new Set(ids).size);
 for(const [,id] of app.matchAll(/\$\('([^']+)'\)/g))assert.ok(ids.includes(id),'missing '+id);
});
test('Voice-first redesign retains all four workspaces and safe disclosure panels',()=>{
 for(const pane of ['conversation','tasks','memories','history'])assert.match(html,new RegExp('id="pane-'+pane+'"'));
 assert.match(html,/<details class="trust-sources"/);
 assert.match(html,/<details class="voice-settings"/);
 assert.equal((html.match(/<details\b/g)||[]).length,(html.match(/<\/details>/g)||[]).length);
});
test('Core reflects actual speech states rather than an invented microphone state',()=>{
 assert.match(app,/hero\.dataset\.voiceMode=/);
 for(const status of ['listening','speaking','thinking','paused'])assert.ok(app.includes("'"+status+"'"));
 assert.match(css,/data-voice-mode="listening"/);
 assert.match(css,/data-voice-mode="speaking"/);
 assert.match(css,/data-voice-mode="thinking"/);
 assert.match(css,/data-voice-mode="paused"/);
});
test('Mobile voice controls preserve access and reduced motion',()=>{
 assert.match(css,/@media\(max-width:700px\)/);
 assert.match(css,/#listen-button\{min-height:56px/);
 assert.match(css,/@media\(prefers-reduced-motion:reduce\)/);
 assert.match(html,/id="listen-button"[^>]*aria-label="Activar micrófono/);
});
test('Voice-first changes do not enable billable model requests',()=>{
 assert.doesNotMatch(app,/ENABLE_MODEL_REQUESTS\s*[:=]\s*(?:true|1)/);
 assert.doesNotMatch(html,/sk-(?:proj-)?[A-Za-z0-9_-]{16,}/);
});

test('Microphone accessible name tracks actual listening and speaking states',()=>{
 const body=app.slice(app.indexOf('function voiceStatus('),app.indexOf('function transcript('));
 assert.match(body,/mic\.setAttribute\('aria-label'/);
 for(const status of ['listening','thinking','speaking'])assert.ok(body.includes("status==='"+status+"'"));
 assert.match(body,/Micrófono activo: JARVIS está escuchando/);
 assert.match(body,/Activar micrófono para hablar con JARVIS/);
});

test('A single mic tap starts recognition without requiring TTS or a second tap',()=>{
 const start=app.indexOf('function listen(){');
 const end=app.indexOf("document.querySelectorAll('.tab')",start);
 assert.ok(start>=0&&end>start);
 const handler=app.slice(start,end);
 assert.match(handler,/beginListening\(false\)/);
 assert.doesNotMatch(handler,/setVoiceEnabled\(true\)|toca Hablar nuevamente/);
 assert.match(app,/voiceStatus\(automatic\?'Intentando reanudar micrófono\.\.\.':'Solicitando micrófono\.\.\.','thinking'\)/);
 assert.match(app,/recognition\.onstart=\(\)=>\{[\s\S]*?voiceStatus\('Escuchando\.\.\.','listening'\)/);
});

test('iPhone browser messaging does not claim SpeechRecognition guarantees transcription',()=>{
 assert.match(app,/NO confirma que pueda transcribir/);
 assert.match(app,/Chrome para iPhone o Safari/);
 assert.match(html,/micrófono del teclado de iOS/);
 assert.match(html,/no garantiza una transcripción/);
});

test('Native iPhone dictation fallback focuses existing composer without requesting permissions or saving data',()=>{
 assert.match(html,/id="dictation-button"/);
 const start=app.indexOf("$('dictation-button').addEventListener('click'");
 const end=app.indexOf("$('stop-button').addEventListener",start);
 assert.ok(start>=0&&end>start);
 const handler=app.slice(start,end);
 assert.match(handler,/stopVoice\(\)/);
 assert.match(handler,/field\.focus\(\)/);
 assert.match(handler,/micrófono del teclado del iPhone/);
 assert.doesNotMatch(handler,/request\(|getUserMedia|processMessage\(|signIn|localStorage|fetch\(/);
});

test('Speech failures identify browser events without assuming Chrome is Safari',()=>{
 assert.match(app,/recognition\.onaudiostart=/);
 assert.match(app,/recognition\.onspeechstart=/);
 assert.match(app,/Reconocimiento web \('/);
 assert.match(app,/language-not-supported/);
 assert.match(app,/code==='network'/);
 assert.match(app,/El navegador no entregó transcripción en 20 segundos/);
 assert.doesNotMatch(app,/Diagnóstico Safari:/);
});

test('Speech-end and no-match events report uncertainty without inventing transcribed words',()=>{
 assert.match(app,/recognition\.onspeechend=/);
 assert.match(app,/recognition\.onnomatch=/);
 assert.match(app,/El navegador detectó el final de la voz, pero aún no entregó texto/);
 assert.match(app,/El reconocimiento no encontró palabras coincidentes/);
 assert.match(app,/recognition\.onspeechend=\(\)=>\{if\(sequence===state\.listenSequence&&!gotFinal\)/);
});

test('Malformed recognition results are handled defensively and errors stay browser-neutral',()=>{
 assert.match(app,/all\.map\(x=>String\(x\?\.\[0\]\?\.transcript\|\|''\)\)/);
 assert.match(app,/all\.filter\(x=>x\?\.isFinal\)/);
 assert.match(app,/El navegador rechazó el reconocimiento de voz/);
 assert.match(app,/El navegador terminó sin entregar palabras/);
 assert.doesNotMatch(app,/Safari no tiene permiso para usar el micrófono/);
});

test('Voice recognition failure messages do not misidentify Chrome as Safari',()=>{
 const begin=app.slice(app.indexOf('function beginListening('),app.indexOf('function startDialogue('));
 assert.doesNotMatch(begin,/Safari/);
 assert.match(begin,/El navegador inició el reconocimiento/);
 assert.match(begin,/El navegador no admite este idioma/);
 assert.match(begin,/El navegador interrumpió el reconocimiento/);
});

test('Daily plan refuses stale task snapshots instead of presenting an outdated schedule as current',()=>{
 const body=app.slice(app.indexOf('function localDayPlan(){'),app.indexOf('function localCommand(',app.indexOf('function localDayPlan(){'));
 assert.match(body,/if\(!sourceIsRecent\('tasks'\)\)/);
 assert.match(body,/no tienen verificación reciente/);
 assert.doesNotMatch(body,/if\(!state\.tasksLoaded\)/);
});


test('Speech playback failures give browser-neutral recovery guidance for Chrome and Safari',()=>{
 const body=app.slice(app.indexOf('utterance.onerror=event=>{'),app.indexOf('synth.speak(utterance);'));
 assert.match(body,/El navegador no pudo reproducir la respuesta hablada/);
 assert.match(body,/Comprueba el volumen y pulsa Hablar para continuar/);
 assert.match(body,/vuelve a pulsar Repetir audio/);
 assert.doesNotMatch(body,/Safari no pudo reproducir|volumen y Safari/);
});
