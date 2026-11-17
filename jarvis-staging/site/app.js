let createClient;
try {
  ({createClient}=await import('https://cdn.jsdelivr.net/npm/@supabase/supabase-js@2.57.0/+esm'));
} catch (firstError) {
  try {({createClient}=await import('https://esm.sh/@supabase/supabase-js@2.57.0?bundle'))}
  catch (secondError) {
    const el=document.getElementById('login-message');
    if(el)el.textContent='No pude iniciar el módulo de acceso. Recarga la página e inténtalo nuevamente.';
    throw secondError;
  }
}

const SUPABASE_URL='https://fdmfyguhpyiiyvjfimio.supabase.co';
const PUBLISHABLE_KEY='sb_publishable_nfx_KpRm43JGbluEAk7YmA_MFDmxMVI';
const API='https://orion-jarvis-api.onrender.com';
const supabase=createClient(SUPABASE_URL,PUBLISHABLE_KEY,{auth:{detectSessionInUrl:true,persistSession:true,autoRefreshToken:true}});
const $=id=>document.getElementById(id);
const state={user:null,session:null,rev:0,tasks:[],memories:[],busy:false,pending:null,model:false,conversation:null,lastReply:'',recognition:null,aborters:new Set(),voiceEnabled:false,voicePending:false,activeUtterance:null};
let noticeTimer;
function sayNotice(text){$('notice').textContent=text;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').textContent='',5500)}
function text(el,text){el.textContent=text??'';return el}
function element(tag,cls,str){const el=document.createElement(tag);if(cls)el.className=cls;if(str!==undefined)text(el,str);return el}
function ready(){return !!state.user&&!!state.session}
function setStatus(label,ok){$('status-label').textContent=label;$('status-led').classList.toggle('ok',ok)}
function visible(id,on){$(id).hidden=!on}
function voiceStatus(label,status='idle'){
  const el=$('voice-state');if(!el)return;
  el.textContent=label;el.dataset.state=status;
}
function updateVoiceControl(){
  $('audio-toggle').setAttribute('aria-pressed',String(state.voiceEnabled));
  $('audio-toggle').textContent=state.voiceEnabled?'Desactivar respuestas en voz alta':'Activar respuestas en voz alta';
  if(!state.recognition&&!(window.speechSynthesis?.speaking))voiceStatus(state.voiceEnabled?'Voz automática activa':'Voz desactivada');
}
function stopVoice(){
  state.voicePending=false;
  const recognition=state.recognition;state.recognition=null;
  if(recognition){recognition.onresult=recognition.onerror=recognition.onend=null;try{recognition.abort()}catch{}}
  if('speechSynthesis' in window)window.speechSynthesis.cancel();
  state.activeUtterance=null;
  $('listen-button').classList.remove('active');$('listen-button').setAttribute('aria-pressed','false');
  updateVoiceControl();
}
function setVoiceEnabled(enabled){
  if(enabled&&!('speechSynthesis' in window)){
    sayNotice('Este navegador no permite reproducir respuestas por voz.');return;
  }
  if(!enabled){stopVoice();state.voiceEnabled=false;updateVoiceControl();return}
  state.voiceEnabled=true;updateVoiceControl();
  // Safari necesita que el primer audio comience por un toque real.
  speak('Voz activada. Ahora puedes hablar conmigo.',{force:true});
}
function clearIdentity(){
  state.rev++;state.user=null;state.session=null;state.tasks=[];state.memories=[];state.pending=null;state.model=false;state.conversation=null;state.lastReply='';
  for(const controller of state.aborters){controller.abort()}state.aborters.clear();stopVoice();state.voiceEnabled=false;updateVoiceControl();
  $('thread').replaceChildren();$('task-list').replaceChildren();$('memory-list').replaceChildren();visible('action-box',false);
}
function updateIdentity(session){
  const userId=session?.user?.id??null;
  if(userId===state.user){state.session=session;return}
  clearIdentity();state.user=userId;state.session=session;
  visible('login',!session);visible('workspace',!!session);
  if(session){$('user-label').textContent=session.user.email||'Sesión privada';setStatus('SESIÓN ACTIVA',true);append('assistant','Conexión privada establecida. Puedes consultarme tus tareas y recuerdos, y utilizar las órdenes de voz. La IA generativa permanece bloqueada hasta que se autorice.');void loadWorkspace();}
  else setStatus('SIN SESIÓN',false);
}
async function request(path,method='GET',body){
  const rev=state.rev;
  const {data:{session},error}=await supabase.auth.getSession();
  if(error||!session||!state.user||session.user.id!==state.user||rev!==state.rev)throw Error('Sesión no disponible');
  const controller=new AbortController();state.aborters.add(controller);
  const timeout=setTimeout(()=>controller.abort(),65000);
  try{
    const response=await fetch(API+path,{method,headers:{Authorization:'Bearer '+session.access_token,'Content-Type':'application/json'},body:body===undefined?undefined:JSON.stringify(body),signal:controller.signal,cache:'no-store'});
    const result=response.status===204?null:await response.json().catch(()=>null);
    if(rev!==state.rev||session.user.id!==state.user)throw Error('La sesión cambió');
    if(!response.ok){const detail=result?.detail;throw Error(typeof detail==='string'?detail:detail?.message||'Solicitud fallida ('+response.status+')')}
    return result;
  }finally{clearTimeout(timeout);state.aborters.delete(controller)}
}
async function loadWorkspace(){
  if(!ready())return;
  const revision=state.rev;
  try{
    const [tasks,memories]=await Promise.all([request('/v1/tasks'),request('/v1/memories')]);
    if(revision!==state.rev)return;
    state.tasks=Array.isArray(tasks)?tasks:[];state.memories=Array.isArray(memories)?memories:[];
    drawTasks();drawMemories();
    try{const r=await fetch(API+'/health',{cache:'no-store'});if(r.ok){const j=await r.json();state.model=j.model_requests_enabled===true;$('model-label').textContent=state.model?'IA DISPONIBLE':'IA EN ESPERA';}}catch{}
  }catch(e){if(revision===state.rev)sayNotice('No se pudo sincronizar: '+e.message)}
}
function append(role,content){
  const item=element('article','message '+(role==='user'?'user':'assistant'));
  item.append(element('div','message-label',role==='user'?'TÚ':'JARVIS'),element('div','message-body',content));
  $('thread').append(item);$('thread').scrollTop=$('thread').scrollHeight;
  if(role==='assistant'){state.lastReply=content;if(state.voicePending){state.voicePending=false;if(state.voiceEnabled)speak(content)}}
  return item;
}
function drawTasks(){
  const root=$('task-list');root.replaceChildren();$('task-count').textContent=String(state.tasks.length);
  if(!state.tasks.length){root.append(element('li','empty','No hay tareas guardadas.'));return}
  for(const task of state.tasks){
    const row=element('li',task.status==='done'?'item-done':'');
    const main=element('div','item-main');
    main.append(element('div','item-title',task.title));
    const due=task.due_at?new Date(task.due_at).toLocaleString('es-PR',{dateStyle:'medium',timeStyle:'short'}):'Sin fecha';
    main.append(element('div','item-sub',(task.priority==='high'?'ALTA':task.priority==='low'?'BAJA':'NORMAL')+' / '+due));
    row.append(main);
    if(task.status!=='done'){const b=element('button','mini','Completar');b.type='button';b.setAttribute('aria-label','Completar tarea '+task.title);b.addEventListener('click',()=>void completeTask(task));row.append(b)}
    root.append(row);
  }
}
function drawMemories(){
  const root=$('memory-list');root.replaceChildren();$('memory-count').textContent=String(state.memories.length);
  if(!state.memories.length){root.append(element('li','empty','Aún no has guardado recuerdos.'));return}
  for(const memory of state.memories){
    const row=element('li');const main=element('div','item-main');
    main.append(element('div','item-title',memory.content),element('div','item-sub',(memory.category||'general').toUpperCase()));
    const b=element('button','mini','Borrar');b.type='button';b.setAttribute('aria-label','Borrar recuerdo');
    b.addEventListener('click',()=>{if(window.confirm('¿Borrar este recuerdo de manera permanente?'))void removeMemory(memory.id)});
    row.append(main,b);root.append(row);
  }
}
async function completeTask(task){
  try{await request('/v1/tasks/'+encodeURIComponent(task.id),'PATCH',{status:'done'});await loadWorkspace();sayNotice('Tarea completada.')}catch(e){sayNotice(e.message)}
}
async function removeMemory(id){
  try{await request('/v1/memories/'+encodeURIComponent(id),'DELETE');await loadWorkspace();sayNotice('Recuerdo eliminado.')}catch(e){sayNotice(e.message)}
}
function setTab(next){
  for(const tab of document.querySelectorAll('.tab')){const active=tab.dataset.tab===next;tab.classList.toggle('active',active);if(active)tab.setAttribute('aria-current','page');else tab.removeAttribute('aria-current')}
  for(const pane of document.querySelectorAll('.pane')){const active=pane.id==='pane-'+next;pane.classList.toggle('active',active);pane.hidden=!active}
}
function normalize(value){return value.toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g,'').trim()}
function toDate(text){
  if(!/manana/i.test(normalize(text)))return null;
  const d=new Date();d.setDate(d.getDate()+1);
  const match=normalize(text).match(/(?:a las|a la)\s*(\d{1,2})(?::(\d{2}))?/);
  if(match){const hour=Number(match[1]),minute=Number(match[2]||0);if(hour>23||minute>59)return null;d.setHours(hour,minute,0,0)}
  else d.setHours(9,0,0,0);
  return d.toISOString();
}
function propose(description,action){
  state.pending={action,description,until:Date.now()+120000};
  $('action-description').textContent=description;visible('action-box',true);
}
function discard(){state.pending=null;visible('action-box',false)}
async function confirmAction(){
  const pending=state.pending;if(!pending)return;
  if(Date.now()>pending.until){discard();append('assistant','La propuesta caducó. Vuelve a darme la instrucción.');return}
  discard();
  try{await pending.action();await loadWorkspace();append('assistant','He guardado el cambio y actualizado tu espacio.')}catch(e){append('assistant','No pude guardarlo: '+e.message)}
}
function localCommand(input){
  const normalized=normalize(input);
  if(/^(resumen( de hoy)?|como va mi dia|mi resumen)/.test(normalized)){
    const pending=state.tasks.filter(x=>x.status!=='done');
    const high=pending.filter(x=>x.priority==='high');
    return 'Tu resumen: '+pending.length+' tarea(s) pendiente(s), '+high.length+' de prioridad alta y '+state.memories.length+' recuerdo(s). '+(pending.length?'Las próximas tareas son: '+pending.slice(0,3).map(x=>x.title).join('; ')+'.':'No tienes pendientes registrados.');
  }
  if(/(que tengo pendiente|mis pendientes|tareas pendientes|que debo hacer)/.test(normalized)){
    const rows=state.tasks.filter(x=>x.status!=='done').slice(0,8);
    return rows.length?'Tus tareas pendientes: '+rows.map((x,i)=>(i+1)+'. '+x.title).join('; ')+'.':'Tu lista de pendientes está vacía.';
  }
  if(/(que recuerdas|mis recuerdos|mi memoria)/.test(normalized)){
    return state.memories.length?'Recuerdo lo siguiente: '+state.memories.slice(0,8).map(x=>x.content).join('; ')+'.':'Aún no has guardado recuerdos.';
  }
  const taskMatch=input.match(/^(?:a[nñ]ade|agrega|crea|crear)\s+(?:una?\s+)?tarea\s+(.+)$/i);
  if(taskMatch){const raw=taskMatch[1].trim();const title=raw.replace(/\s+para\s+ma[nñ]ana(?:\s+a\s+las?\s+\d{1,2}(?::\d{2})?)?\s*$/i,'').trim();
    if(!title)return 'Necesito el título de la tarea.';
    const due_at=toDate(raw);const priority=/prioridad alta/i.test(raw)?'high':'normal';
    propose('¿Guardar la tarea «'+title+'»'+(due_at?' para mañana':'')+'?',()=>request('/v1/tasks','POST',{title,priority,due_at}));
    return 'He preparado la tarea. Confírmala en la pantalla antes de guardar.';
  }
  const memoryMatch=input.match(/^recuerda\s+que\s+(.+)$/i);
  if(memoryMatch){const content=memoryMatch[1].trim();
    propose('¿Guardar el recuerdo «'+content+'»?',()=>request('/v1/memories','POST',{content,category:'general'}));
    return 'He preparado el recuerdo. Confírmalo antes de guardarlo.';
  }
  const doneMatch=input.match(/^(?:completa|termina)\s+tarea\s+(.+)$/i);
  if(doneMatch){const matches=state.tasks.filter(t=>t.status!=='done'&&normalize(t.title)===normalize(doneMatch[1]));
    if(matches.length!==1)return matches.length?'Encontré varias tareas con ese nombre. Usa la sección Tareas.':'No encontré una tarea pendiente con ese título exacto.';
    propose('¿Marcar como completada «'+matches[0].title+'»?',()=>request('/v1/tasks/'+encodeURIComponent(matches[0].id),'PATCH',{status:'done'}));
    return 'La tarea está lista para completar. Confirma en la pantalla.';
  }
  if(/^(ayuda|que puedes hacer|instrucciones)/.test(normalized))return 'Puedo resumir tus pendientes, listar recuerdos, preparar nuevas tareas y guardar recuerdos con confirmación. Prueba: Resumen de hoy, Qué tengo pendiente o Recuerda que estudio los sábados.';
  return null;
}
async function processMessage(input){
  if(!ready()||state.busy)return;
  const clean=String(input||'').trim().slice(0,4000);if(!clean)return;
  state.busy=true;$('send-button').disabled=true;state.voicePending=state.voiceEnabled;
  append('user',clean);$('message').value='';
  try{
    if(state.pending&&/^(confirmar accion|confirmar|aceptar)$/.test(normalize(clean))){await confirmAction();return}
    if(state.pending&&/^(cancelar accion|cancelar)$/.test(normalize(clean))){discard();append('assistant','Propuesta cancelada. No guardé cambios.');return}
    const answer=localCommand(clean);
    if(answer!==null){append('assistant',answer);return}
    if(!state.model){append('assistant','Todavía no tengo habilitada la conversación libre con OpenAI. Puedo ayudarte con tus tareas y recuerdos sin generar gastos de IA. Di «Qué puedes hacer» para ver las órdenes.');return}
    const data=await request('/v1/chat','POST',{message:clean,conversation_id:state.conversation,request_id:crypto.randomUUID()});
    if(data?.conversation_id)state.conversation=data.conversation_id;
    append('assistant',data?.reply||'La respuesta no está disponible; consulta el estado de la solicitud.');
  }catch(e){append('assistant','No pude completar la solicitud: '+e.message)}
  finally{state.busy=false;$('send-button').disabled=false}
}
function speak(content,{force=false}={}){
  if(!('speechSynthesis' in window)){sayNotice('Este navegador no permite reproducir audio.');return}
  if(!state.voiceEnabled&&!force)return;
  const words=String(content||'').trim().slice(0,3500);
  if(!words)return;
  const synth=window.speechSynthesis;
  synth.cancel();
  const voices=synth.getVoices();
  const preferred=['es-PR','es-US','es-MX','es-ES'];
  const spanish=preferred.map(lang=>voices.find(v=>v.lang.toLowerCase()===lang.toLowerCase())).find(Boolean) || voices.find(v=>v.lang.toLowerCase().startsWith('es'));
  const utterance=new SpeechSynthesisUtterance(words);
  if(spanish){utterance.voice=spanish;utterance.lang=spanish.lang}
  else utterance.lang='es-ES';
  utterance.rate=1.01;utterance.pitch=.94;utterance.volume=1;
  state.activeUtterance=utterance;
  utterance.onstart=()=>{if(state.activeUtterance===utterance)voiceStatus('JARVIS hablando','speaking')};
  utterance.onend=()=>{if(state.activeUtterance===utterance){state.activeUtterance=null;updateVoiceControl()}};
  utterance.onerror=()=>{if(state.activeUtterance===utterance){state.activeUtterance=null;updateVoiceControl();sayNotice('Audio no disponible. Comprueba el volumen y que la voz esté activada en Safari.')}};
  synth.speak(utterance);
}
function listen(){
  if(!ready())return;
  if(state.busy){sayNotice('JARVIS está preparando tu respuesta.');return}
  if(!state.voiceEnabled){setVoiceEnabled(true);sayNotice('Voz activada. Toca Hablar una vez más.');return}
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Speech){sayNotice('El dictado web no está disponible aquí. Abre JARVIS en Safari o usa el micrófono del teclado.');return}
  stopVoice();
  try{
    const recognition=new Speech();state.recognition=recognition;
    recognition.lang='es-PR';recognition.continuous=false;recognition.interimResults=false;recognition.maxAlternatives=1;
    $('listen-button').classList.add('active');$('listen-button').setAttribute('aria-pressed','true');
    voiceStatus('Escuchando...', 'listening');
    recognition.onresult=event=>{
      const transcript=Array.from(event.results).filter(x=>x.isFinal).map(x=>x[0]?.transcript||'').join(' ').trim();
      if(transcript&&ready()){
        voiceStatus('Respondiendo...', 'thinking');
        void processMessage(transcript);
      }
    };
    recognition.onerror=event=>{
      voiceStatus('Micrófono no disponible', 'idle');
      sayNotice('Dictado no disponible ('+(event.error||'error')+'). Abre en Safari o usa el micrófono del teclado.');
    };
    recognition.onend=()=>{
      state.recognition=null;
      $('listen-button').classList.remove('active');$('listen-button').setAttribute('aria-pressed','false');
      if(!state.busy)updateVoiceControl();
    };
    recognition.start();
  }catch(e){stopVoice();sayNotice('No se pudo abrir el micrófono. Usa Safari e inténtalo otra vez.')}
}
document.querySelectorAll('.tab').forEach(x=>x.addEventListener('click',()=>setTab(x.dataset.tab)));
document.querySelectorAll('[data-phrase]').forEach(x=>x.addEventListener('click',()=>void processMessage(x.dataset.phrase)));
$('message-form').addEventListener('submit',e=>{e.preventDefault();void processMessage($('message').value)});
$('task-form').addEventListener('submit',async e=>{e.preventDefault();const title=$('task-title').value.trim();if(!title)return;
  try{await request('/v1/tasks','POST',{title,priority:$('task-priority').value});$('task-title').value='';await loadWorkspace();sayNotice('Tarea guardada.')}catch(err){sayNotice(err.message)}});
$('memory-form').addEventListener('submit',async e=>{e.preventDefault();const content=$('memory-content').value.trim();if(!content)return;
  try{await request('/v1/memories','POST',{content,category:'general'});$('memory-content').value='';await loadWorkspace();sayNotice('Recuerdo guardado.')}catch(err){sayNotice(err.message)}});
$('action-accept').addEventListener('click',()=>void confirmAction());$('action-reject').addEventListener('click',()=>{discard();append('assistant','Propuesta cancelada.')});
$('audio-toggle').addEventListener('click',()=>setVoiceEnabled(!state.voiceEnabled));
$('listen-button').addEventListener('click',listen);$('stop-button').addEventListener('click',()=>{stopVoice();sayNotice('Voz detenida.')});
$('read-button').addEventListener('click',()=>state.lastReply?speak(state.lastReply,{force:true}):sayNotice('No tengo una respuesta para leer.'));
$('signout-button').addEventListener('click',async()=>{clearIdentity();visible('workspace',false);visible('login',true);await supabase.auth.signOut();});
$('login-form').addEventListener('submit',async e=>{e.preventDefault();const email=$('email').value.trim();if(!email)return;
  $('login-button').disabled=true;$('login-message').textContent='Preparando el enlace de acceso...';
  try{const {error}=await supabase.auth.signInWithOtp({email,options:{emailRedirectTo:window.location.origin}});if(error)throw error;
    $('login-message').textContent='Revisa tu correo y abre el enlace desde este iPhone. Si no funciona, comprueba las redirecciones permitidas en Supabase Auth.';}
  catch(err){$('login-message').textContent='No pude enviar el enlace: '+err.message}
  finally{$('login-button').disabled=false}
});
document.addEventListener('visibilitychange',()=>{if(document.hidden)stopVoice()});
supabase.auth.onAuthStateChange((_event,session)=>{queueMicrotask(()=>updateIdentity(session))});
updateVoiceControl();
window.jarvisInitialized=true;
window.dispatchEvent(new Event('jarvis:initialized'));
try {
  const {data:{session}}=await supabase.auth.getSession();
  updateIdentity(session);
} catch (error) {
  visible('login',true);visible('workspace',false);
  setStatus('ERROR DE ACCESO',false);
  $('login-message').textContent='No pude comprobar tu sesión. Recarga la página y vuelve a entrar.';
}
