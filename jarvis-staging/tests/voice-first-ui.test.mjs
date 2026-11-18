// Run: node --test jarvis-staging/tests/voice-first-ui.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
const html=await readFile(new URL('../site/index.html',import.meta.url),'utf8');
const css=await readFile(new URL('../site/styles.css',import.meta.url),'utf8');
const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');
test('UI IDs remain unique and all direct app element lookups exist',()=>{
 const ids=[...html.matchAll(/\\bid="([^"]+)"/g)].map(m=>m[1]);
 assert.equal(ids.length,new Set(ids).size);
 for(const [,id] of app.matchAll(/\\$\\('([^']+)'\\)/g))assert.ok(ids.includes(id),'missing '+id);
});
test('Voice-first redesign retains all four workspaces and safe disclosure panels',()=>{
 for(const pane of ['conversation','tasks','memories','history'])assert.match(html,new RegExp('id="pane-'+pane+'"'));
 assert.match(html,/<details class="trust-sources"/);
 assert.match(html,/<details class="voice-settings"/);
 assert.equal((html.match(/<details\\b/g)||[]).length,(html.match(/<\\/details>/g)||[]).length);
});
test('Core reflects actual speech states rather than an invented microphone state',()=>{
 assert.match(app,/hero\\.dataset\\.voiceMode=/);
 for(const status of ['listening','speaking','thinking','paused'])assert.ok(app.includes("'"+status+"'"));
 assert.match(css,/data-voice-mode="listening"/);
 assert.match(css,/data-voice-mode="speaking"/);
 assert.match(css,/data-voice-mode="thinking"/);
 assert.match(css,/data-voice-mode="paused"/);
});
test('Mobile voice controls preserve access and reduced motion',()=>{
 assert.match(css,/@media\\(max-width:700px\\)/);
 assert.match(css,/#listen-button\\{min-height:56px/);
 assert.match(css,/@media\\(prefers-reduced-motion:reduce\\)/);
 assert.match(html,/id="listen-button"[^>]*aria-label="Activar micrófono/);
});
test('Voice-first changes do not enable billable model requests',()=>{
 assert.doesNotMatch(app,/ENABLE_MODEL_REQUESTS\\s*[:=]\\s*(?:true|1)/);
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
