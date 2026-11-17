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
const state={user:null,session:null,rev:0,tasks:[],memories:[],busy:false,pending:null,model:false,conversation:null,lastReply:'',recognition:null,aborters:new Set(),voiceEnabled:false,voicePending:false,activeUtterance:null,dialogEnabled:false,listenSequence:0,rearmTimer:null,speechSequence:0};
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
function transcript(label){
  const el=$('live-transcript');if(el)el.textContent=label;
}
function clearRearm(){
  if(state.rearmTimer!==null){clearTimeout(state.rearmTimer);state.rearmTimer=null}
}
function updateVoiceControl(){
  $('audio-toggle').setAttribute('aria-pressed',String(state.voiceEnabled));
  $('audio-toggle').textContent=state.voiceEnabled?'Desactivar respuestas en voz alta':'Activar respuestas en voz alta';
  $('session-button').setAttribute('aria-pressed',String(state.dialogEnabled));
  $('session-button').textContent=state.dialogEnabled?'Terminar diálogo':'Iniciar diálogo';
  const voiceBusy=!!state.recognition || !!state.activeUtterance;
  if(!voiceBusy)voiceStatus(state.dialogEnabled?'Diálogo activo':state.voiceEnabled?'Voz automática activa':'Voz desactivada');
}
function cancelRecognition(){
  state.listenSequence+=1;
  const rec=state.recognition;
  state.recognition=null;
  if(rec){rec.onresult=rec.onerror=rec.onend=null;try{rec.abort()}catch{}}
  $('listen-button').classList.remove('active');
  $('listen-button').setAttribute('aria-pressed','false');
}
function cancelSpeech(){
  state.speechSequence+=1;
  state.activeUtterance=null;
  if('speechSynthesis' in window)window.speechSynthesis.cancel();
}
function stopVoice(){
  clearRearm();
  state.voicePending=false;
  state.dialogEnabled=false;
  cancelRecognition();
  cancelSpeech();
  transcript('Sesión de voz detenida.');
  updateVoiceControl();
}
function pauseDialogue(reason){
  clearRearm();
  state.dialogEnabled=false;
  cancelRecognition();
  $('session-button').setAttribute('aria-pressed','false');
  $('session-button').textContent='Reanudar diálogo';
  voiceStatus(reason||'Toca Hablar para continuar','paused');
  sayNotice(reason||'La escucha automática se detuvo. Toca Hablar para continuar.');
}
function setVoiceEnabled(enabled){
  if(enabled&&!('speechSynthesis' in window)){
    sayNotice('Este navegador no permite reproducir respuestas por voz.');return;
  }
  if(!enabled){stopVoice();state.voiceEnabled=false;updateVoiceControl();return}
  state.voiceEnabled=true;updateVoiceControl();
  // Debe empezar dentro de una acción del usuario para cumplir las reglas de Safari.
  speak('Voz activada. Ahora puedes hablar conmigo.',{force:true});
}
function scheduleRearm(){
  if(!state.dialogEnabled||!state.voiceEnabled||!ready()||document.hidden)return;
  clearRearm();
  state.rearmTimer=setTimeout(()=>{
    state.rearmTimer=null;
    if(!state.dialogEnabled||state.busy||document.hidden||!ready())return;
    beginListening(true);
  },450);
}
function beginListening(automatic=false){
  if(!ready()||state.busy||document.hidden)return;
  const Speech=window.SpeechRecognition||window.webkitSpeechRecognition;
  if(!Speech){
    pauseDialogue('Safari no ofrece dictado web aquí. Usa el micrófono del teclado.');
    return;
  }
  clearRearm();
  cancelSpeech();
  cancelRecognition();
  const sequence=state.listenSequence;
  let recognition;
  try{
    recognition=new Speech();
    state.recognition=recognition;
    recognition.lang='es-PR';
    recognition.continuous=false;
    recognition.interimResults=true;
    recognition.maxAlternatives=1;
    let gotFinal=false;
    let failed=false;
    recognition.onstart=()=>{
      if(sequence!==state.listenSequence)return;
      voiceStatus('Escuchando...','listening');
      transcript('Puedes hablar ahora. Escuchando...');
    };
    recognition.onresult=event=>{
      if(sequence!==state.listenSequence||!ready())return;
      const all=Array.from(event.results||[]);
      const words=all.map(x=>x[0]?.transcript||'').join(' ').trim();
      if(words)transcript(words);
      const final=all.filter(x=>x.isFinal).map(x=>x[0]?.transcript||'').join(' ').trim();
      if(final&&!gotFinal){
        gotFinal=true;
        voiceStatus('Preparando respuesta...','thinking');
        // Termina el reconocimiento para que no grabe la respuesta de JARVIS.
        recognition.onend=null;
        recognition.onresult=null;
        recognition.onerror=null;
        try{recognition.stop()}catch{}
        state.recognition=null;
        $('listen-button').classList.remove('active');
        $('listen-button').setAttribute('aria-pressed','false');
        void processMessage(final);
      }
    };
    recognition.onerror=event=>{
      if(sequence!==state.listenSequence)return;
      failed=true;
      const code=String(event?.error||'desconocido');
      const reason=code==='not-allowed'||code==='service-not-allowed'
        ?'Safari no tiene permiso para usar el micrófono.'
        :code==='no-speech'?'No detecté voz; toca Hablar para reintentar.'
        :'Safari interrumpió el reconocimiento ('+code+'). Toca Hablar.';
      if(state.dialogEnabled)pauseDialogue(reason);
      else {cancelRecognition();voiceStatus(reason,'paused');sayNotice(reason)}
    };
    recognition.onend=()=>{
      if(sequence!==state.listenSequence)return;
      state.recognition=null;
      $('listen-button').classList.remove('active');
      $('listen-button').setAttribute('aria-pressed','false');
      if(!gotFinal&&!failed){
        const reason='No escuché una instrucción. Toca Hablar para continuar.';
        if(state.dialogEnabled)pauseDialogue(reason);
        else voiceStatus(reason,'paused');
      }
    };
    $('listen-button').classList.add('active');
    $('listen-button').setAttribute('aria-pressed','true');
    voiceStatus(automatic?'Reanudando escucha...':'Activando micrófono...','listening');
    recognition.start();
  }catch(error){
    cancelRecognition();
    const msg=automatic?'Safari requiere tocar Hablar para continuar.':'No se pudo abrir el micrófono. Inténtalo en Safari.';
    if(state.dialogEnabled)pauseDialogue(msg);
    else {voiceStatus(msg,'paused');sayNotice(msg)}
  }
}
function startDialogue(){
  if(!ready())return;
  if(state.dialogEnabled){stopVoice();sayNotice('Diálogo finalizado.');return}
  if(!(window.SpeechRecognition||window.webkitSpeechRecognition)){
    sayNotice('El micrófono web no está disponible. Puedes dictar con el teclado.');return;
  }
  state.dialogEnabled=true;
  transcript('Diálogo activo. Pronuncia una instrucción cuando el indicador diga Escuchando.');
  if(!state.voiceEnabled){
    // Al activar la voz se obtiene el gesto de usuario requerido para TTS.
    setVoiceEnabled(true);
    // La escucha comienza al terminar el saludo, cuando Safari lo permita.
  }else{
    beginListening(false);
  }
  updateVoiceControl();
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
  const command=clean.replace(/^(?:oye[ ,]+)?jarvis[\s,.:;!?-]*/i,'').trim();
  append('user',clean);$('message').value='';
  try{
    if(state.pending&&/^(confirmar accion|confirmar|aceptar)$/.test(normalize(command))){await confirmAction();return}
    if(state.pending&&/^(cancelar accion|cancelar)$/.test(normalize(command))){discard();append('assistant','Propuesta cancelada. No guardé cambios.');return}
    const answer=command?localCommand(command):'Te escucho. Dime qué necesitas.';
    if(answer!==null){append('assistant',answer);return}
    if(!state.model){append('assistant','Todavía no tengo habilitada la conversación libre con OpenAI. Puedo ayudarte con tus tareas y recuerdos sin generar gastos de IA. Di «Qué puedes hacer» para ver las órdenes.');return}
    const data=await request('/v1/chat','POST',{message:command||clean,conversation_id:state.conversation,request_id:crypto.randomUUID()});
    if(data?.conversation_id)state.conversation=data.conversation_id;
    append('assistant',data?.reply||'La respuesta no está disponible; consulta el estado de la solicitud.');
  }catch(e){append('assistant','No pude completar la solicitud: '+e.message)}
  finally{state.busy=false;$('send-button').disabled=false}
}

function speak(content,{force=false}={}){
  if(!('speechSynthesis' in window)){sayNotice('No se puede reproducir audio en este navegador.');return}
  if(!state.voiceEnabled&&!force)return;
  const words=String(content||'').trim().slice(0,3500);
  if(!words)return;
  cancelSpeech();
  const synth=window.speechSynthesis;
  const sequence=state.speechSequence;
  const voices=synth.getVoices();
  const preferred=['es-PR','es-US','es-MX','es-ES'];
  const spanish=preferred.map(lang=>voices.find(v=>v.lang.toLowerCase()===lang.toLowerCase())).find(Boolean) || voices.find(v=>v.lang.toLowerCase().startsWith('es'));
  const utterance=new SpeechSynthesisUtterance(words);
  if(spanish){utterance.voice=spanish;utterance.lang=spanish.lang}
  else utterance.lang='es-ES';
  utterance.rate=1;utterance.pitch=.94;utterance.volume=1;
  state.activeUtterance=utterance;
  utterance.onstart=()=>{
    if(sequence===state.speechSequence)voiceStatus('JARVIS hablando','speaking');
  };
  utterance.onend=()=>{
    if(sequence!==state.speechSequence||state.activeUtterance!==utterance)return;
    state.activeUtterance=null;
    updateVoiceControl();
    scheduleRearm();
  };
  utterance.onerror=event=>{
    if(sequence!==state.speechSequence)return;
    state.activeUtterance=null;
    if(state.dialogEnabled)pauseDialogue('Safari no pudo reproducir el audio; toca Hablar para continuar.');
    else sayNotice('No se pudo reproducir la voz. Comprueba el volumen y Safari.');
    updateVoiceControl();
  };
  synth.speak(utterance);
}
function listen(){
  if(!ready())return;
  if(state.busy){sayNotice('JARVIS está terminando la respuesta.');return}
  if(!state.voiceEnabled){setVoiceEnabled(true);sayNotice('Voz activada; toca Hablar nuevamente.');return}
  // Pulsar Hablar mientras JARVIS habla interrumpe su voz.
  beginListening(false);
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
$('session-button').addEventListener('click',startDialogue);
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
document.addEventListener('visibilitychange',()=>{if(document.hidden){stopVoice();voiceStatus('Modo detenido: la página no está visible.','paused')}});
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
