// Run: node --test jarvis-staging/tests/voice-dialogue-integration.test.mjs
import test from 'node:test';
import assert from 'node:assert/strict';
import {readFile} from 'node:fs/promises';
import vm from 'node:vm';

const app=await readFile(new URL('../site/app.js',import.meta.url),'utf8');

async function setup({synthesis=true,throwOnStart=false}={}) {
  const elements=new Map(), recognitions=[], utterances=[], timers=new Map();
  let nextTimer=0, gesture=false;
  function node(){
    return {textContent:'',value:'',dataset:{},hidden:false,children:[],attrs:{},handlers:{},
      classList:{add(){},remove(){},toggle(){}},
      setAttribute(k,v){this.attrs[k]=v},removeAttribute(k){delete this.attrs[k]},
      addEventListener(k,fn){this.handlers[k]=fn},append(...items){this.children.push(...items)},
      replaceChildren(...items){this.children=items},focus(){}};
  }
  const get=id=>{if(!elements.has(id))elements.set(id,node());return elements.get(id)};
  get('recognition-lang').value='es-ES';
  const document={hidden:false,getElementById:get,createElement:node,querySelector:()=>node(),querySelectorAll:()=>[],addEventListener(){}};
  class Recognition {
    constructor(){recognitions.push(this)}
    start(){this.startedInGesture=gesture;if(throwOnStart)throw Error('Recognition unavailable');this.onstart?.()}
    stop(){this.stopped=true}
    abort(){this.aborted=true}
  }
  class Utterance {constructor(content){this.text=content}}
  const synth={speaking:false,getVoices:()=>[],cancel(){this.speaking=false},speak(utterance){if(this.throwOnSpeak)throw Error('Playback unavailable');utterances.push(utterance);this.speaking=true;utterance.onstart?.()}};
  const window={SpeechRecognition:Recognition,addEventListener(){},dispatchEvent(){}};
  if(synthesis)window.speechSynthesis=synth;
  const context={window,document,SpeechSynthesisUtterance:Utterance,Event:class{},
    trustedCommand:()=>null,recentVerification:()=>false,
    createClient:()=>({auth:{onAuthStateChange(){},getSession:async()=>({data:{session:null}})}}),
    setTimeout:(fn,delay)=>{const id=++nextTimer;timers.set(id,{fn,delay});return id},
    clearTimeout:id=>timers.delete(id),queueMicrotask,AbortController,console};
  const source=app.slice(app.indexOf('const SUPABASE_URL='));
  await vm.runInNewContext(`(async()=>{${source}\nglobalThis.testState=state;})()`,context);
  context.testState.user='test-user';context.testState.session={user:{id:'test-user'}};
  return {get,recognitions,utterances,synth,state:context.testState,timers,
    click(id){gesture=true;try{get(id).handlers.click()}finally{gesture=false}},
    runTimer(delay){const entry=[...timers].find(([,timer])=>timer.delay===delay);assert.ok(entry,`missing timer ${delay}`);timers.delete(entry[0]);entry[1].fn()}};
}
function result(recognition,words){recognition.onresult({results:[Object.assign([{transcript:words}],{isFinal:true})]})}

test('dialogue starts recognition in the first gesture, answers, and re-arms after speech',async()=>{
  const h=await setup();
  h.click('session-button');
  assert.equal(h.recognitions.length,1);
  assert.equal(h.recognitions[0].startedInGesture,true);
  assert.equal(h.utterances.length,0,'no greeting delays microphone activation');
  assert.equal(h.get('voice-state').dataset.state,'listening');
  h.recognitions[0].onaudiostart();h.recognitions[0].onspeechstart();
  result(h.recognitions[0],'ayuda');
  assert.equal(h.recognitions[0].stopped,true);
  assert.equal(h.utterances.length,1);
  assert.match(h.utterances[0].text,/Puedo resumir/);
  assert.equal(h.state.busy,false);
  assert.equal(h.get('voice-state').dataset.state,'speaking');
  h.synth.speaking=false;h.utterances[0].onend();
  h.runTimer(450);
  assert.equal(h.recognitions.length,2);
  assert.equal(h.get('voice-state').dataset.state,'listening');
  h.click('stop-button');
  assert.equal(h.recognitions[1].aborted,true);
  assert.equal(h.state.dialogEnabled,false);
  assert.equal([...h.timers.values()].some(t=>t.delay===450),false);
});

test('the microphone button interrupts speech and starts the next listening turn',async()=>{
  const h=await setup();h.click('session-button');result(h.recognitions[0],'ayuda');
  const previous=h.utterances[0];
  h.click('listen-button');
  assert.equal(h.recognitions.length,2);
  assert.equal(h.recognitions[1].startedInGesture,true);
  assert.equal(h.synth.speaking,false);
  previous.onend();
  assert.equal([...h.timers.values()].some(t=>t.delay===450),false,'stale speech callback cannot restart listening');
});

test('recognition rejection pauses dialogue without inventing a transcript or retrying',async()=>{
  const h=await setup();h.click('session-button');h.recognitions[0].onerror({error:'not-allowed'});
  assert.equal(h.state.dialogEnabled,false);
  assert.equal(h.get('voice-state').dataset.state,'paused');
  assert.match(h.get('live-transcript').textContent,/not-allowed/);
  assert.equal(h.recognitions.length,1);
  assert.equal([...h.timers.values()].some(t=>t.delay===450),false);
});

test('synchronous recognition startup failure remains visibly paused',async()=>{
  const h=await setup({throwOnStart:true});h.click('session-button');
  assert.equal(h.recognitions.length,1);
  assert.equal(h.recognitions[0].startedInGesture,true);
  assert.equal(h.recognitions[0].aborted,true);
  assert.equal(h.state.dialogEnabled,false);
  assert.equal(h.get('voice-state').dataset.state,'paused');
  assert.match(h.get('voice-state').textContent,/No se pudo iniciar/);
  assert.equal(h.get('session-button').attrs['aria-pressed'],'false');
  assert.equal(h.get('session-button').textContent,'Reanudar diálogo');
  assert.equal([...h.timers.values()].some(t=>t.delay===450),false);
});

test('a start without transcript times out and stops recognition',async()=>{
  const h=await setup();h.click('session-button');h.runTimer(20000);
  assert.equal(h.recognitions[0].aborted,true);
  assert.equal(h.state.dialogEnabled,false);
  assert.match(h.get('live-transcript').textContent,/no entregó transcripción/);
});

test('when speech synthesis is unavailable dialogue does not claim to be active',async()=>{
  const h=await setup({synthesis:false});h.click('session-button');
  assert.equal(h.state.dialogEnabled,false);
  assert.equal(h.recognitions.length,0);
  assert.match(h.get('notice').textContent,/no permite reproducir/);
  h.click('listen-button');
  assert.equal(h.recognitions.length,1,'dictation remains available');
});

test('speech playback error pauses dialogue and leaves the written answer available',async()=>{
  const h=await setup();h.click('session-button');result(h.recognitions[0],'ayuda');
  h.synth.speaking=false;h.utterances[0].onerror({error:'not-allowed'});
  assert.equal(h.state.dialogEnabled,false);
  assert.equal(h.get('voice-state').dataset.state,'paused');
  assert.match(h.get('voice-state').textContent,/no pudo reproducir/);
  assert.equal(h.get('session-button').attrs['aria-pressed'],'false');
  assert.equal(h.get('session-button').textContent,'Reanudar diálogo');
  assert.match(h.state.lastReply,/Puedo resumir/);
  assert.equal([...h.timers.values()].some(t=>t.delay===450),false);
  assert.equal(h.recognitions.length,1);
});

test('synchronous speech playback failure keeps the pause visible and the written answer available',async()=>{
  const h=await setup();h.synth.throwOnSpeak=true;h.click('session-button');result(h.recognitions[0],'ayuda');
  assert.equal(h.state.dialogEnabled,false);
  assert.equal(h.get('voice-state').dataset.state,'paused');
  assert.match(h.get('voice-state').textContent,/no pudo iniciar/);
  assert.equal(h.get('session-button').attrs['aria-pressed'],'false');
  assert.equal(h.get('session-button').textContent,'Reanudar diálogo');
  assert.match(h.state.lastReply,/Puedo resumir/);
  assert.equal([...h.timers.values()].some(t=>t.delay===450),false);
  assert.equal(h.recognitions.length,1);
});
