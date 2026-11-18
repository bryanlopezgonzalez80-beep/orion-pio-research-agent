import {classifyCommand,englishIntent,trustedCommand,recentVerification} from './briefing.js';
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
const state={user:null,session:null,rev:0,tasks:[],memories:[],busy:false,pending:null,model:false,conversation:null,lastReply:'',recognition:null,aborters:new Set(),voiceEnabled:false,voicePending:false,activeUtterance:null,dialogEnabled:false,listenSequence:0,rearmTimer:null,speechSequence:0,recognitionWatchdog:null,syncSerial:0,tasksLoaded:false,memoriesLoaded:false,historyLoaded:false,historySerial:0,historyDetailSerial:0,conversations:[],editingTaskId:null,editingMemoryId:null,tasksVerifiedAt:null,memoriesVerifiedAt:null,replyLanguage:'es'};
let noticeTimer;
function sayNotice(text){$('notice').textContent=text;clearTimeout(noticeTimer);noticeTimer=setTimeout(()=>$('notice').textContent='',5500)}
function text(el,text){el.textContent=text??'';return el}
function element(tag,cls,str){const el=document.createElement(tag);if(cls)el.className=cls;if(str!==undefined)text(el,str);return el}
function ready(){return !!state.user&&!!state.session}
function setStatus(label,ok){$('status-label').textContent=label;$('status-led').classList.toggle('ok',ok)}
function visible(id,on){$(id).hidden=!on}
function updateVoiceCompatibility(){
  const el=$('voice-compat');if(!el)return;
  const recognition=Boolean(window.SpeechRecognition||window.webkitSpeechRecognition);
  const synthesis='speechSynthesis' in window;
  if(!recognition&&!synthesis){
    el.textContent='Este navegador no ofrece reconocimiento ni lectura de voz web. Usa el dictado del teclado.';
  }else if(!recognition){
    el.textContent='Lectura de voz disponible. El micrófono web no está disponible; usa el dictado del teclado.';
  }else if(!synthesis){
    el.textContent='Reconocimiento de voz detectado. La lectura en voz alta no está disponible.';
  }else{
    el.textContent='Micrófono web y lectura de voz detectados. Safari puede limitar las conversaciones continuas.';
  }
}

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
function clearRecognitionWatchdog(){
  if(state.recognitionWatchdog!==null){clearTimeout(state.recognitionWatchdog);state.recognitionWatchdog=null}
}
function armRecognitionWatchdog(current,sequence){
  clearRecognitionWatchdog();
  state.recognitionWatchdog=setTimeout(()=>{
    state.recognitionWatchdog=null;
    if(state.recognition===current&&sequence===state.listenSequence){
      const msg='Safari dejó de responder al micrófono. Toca Hablar para continuar.';
      if(state.dialogEnabled)pauseDialogue(msg);
      else {cancelRecognition();voiceStatus(msg,'paused');sayNotice(msg)}
    }
  },20000);
}
function cancelRecognition(){
  clearRecognitionWatchdog();
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
  speak('Voz activada. Ahora puedes hablar conmigo.',{force:true,language:'es'});
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
    recognition.lang=$('recognition-lang').value==='en-US'?'en-US':'es-PR';
    recognition.continuous=false;
    recognition.interimResults=true;
    recognition.maxAlternatives=1;
    let gotFinal=false;
    let failed=false;
    recognition.onstart=()=>{
      if(sequence!==state.listenSequence)return;
      voiceStatus('Escuchando...','listening');
      transcript('Puedes hablar ahora. Escuchando...');
      armRecognitionWatchdog(recognition,sequence);
    };
    recognition.onresult=event=>{
      if(sequence!==state.listenSequence||!ready())return;
      const all=Array.from(event.results||[]);
      const words=all.map(x=>x[0]?.transcript||'').join(' ').trim();
      if(words){transcript(words);armRecognitionWatchdog(recognition,sequence)}
      const final=all.filter(x=>x.isFinal).map(x=>x[0]?.transcript||'').join(' ').trim();
      if(final&&!gotFinal){
        gotFinal=true;
        clearRecognitionWatchdog();
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
      clearRecognitionWatchdog();
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
      clearRecognitionWatchdog();
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
    armRecognitionWatchdog(recognition,sequence);
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

let calendarToken = '';
function resetCalendar(){
  calendarToken = '';
  $('icloud-choice').replaceChildren();
  $('icloud-key').value = $('icloud-account').value = '';
  $('icloud-read').disabled = $('icloud-end').disabled = true;
  $('source-calendar').textContent = 'Calendario: no conectado';
}
$('icloud-connect').addEventListener('click', async () => {
  if (!ready() || !$('icloud-account').reportValidity()) return;
  const rev = state.rev;
  $('icloud-connect').disabled = true;
  try {
    const body = {email:$('icloud-account').value.trim(), password:$('icloud-key').value};
    $('icloud-key').value = '';
    const result = await request('/v1/calendar/icloud/connect','POST',body);
    resetCalendar();
    calendarToken = result.connection;
    $('icloud-choice').append(new Option('Selecciona un calendario',''));
    for (const calendar of result.calendars) $('icloud-choice').append(new Option(calendar.name,calendar.id));
    $('icloud-end').disabled = false;
    $('source-calendar').textContent = 'iCloud conectado. Selecciona un calendario.';
  } catch (e) {
    if (rev === state.rev) $('source-calendar').textContent = 'Conexión no verificada. '+e.message;
  } finally { $('icloud-connect').disabled = false; }
});
$('icloud-choice').addEventListener('change', () => {
  $('icloud-read').disabled = !$('icloud-choice').value;
  $('source-calendar').textContent = 'iCloud conectado. Agenda pendiente de consulta.';
});
$('icloud-end').addEventListener('click', async () => {
  const token = calendarToken;
  try {
    await request('/v1/calendar/icloud/disconnect','POST',{connection:token});
    if (calendarToken === token) resetCalendar();
  } catch(e) {
    if (calendarToken === token) $('source-calendar').textContent = 'Desconexión sin verificar. '+e.message;
  }
});
async function calendarToday(english){
  const rev = state.rev, token = calendarToken, id = $('icloud-choice').value;
  const source = $('icloud-choice').selectedOptions[0]?.textContent;
  let answer;
  try {
    const result = await request('/v1/calendar/icloud/today','POST',{connection:token, calendar:id});
    const clock = date => new Date(date).toLocaleTimeString(english?'en-US':'es-PR',{timeZone:'America/Puerto_Rico',hour:'numeric',minute:'2-digit'});
    const stamp = new Date(result.checked).toLocaleString(english?'en-US':'es-PR',{timeZone:'America/Puerto_Rico',month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
    const events = result.events.slice(0,12).map(event => (event.start.length===10?(english?'All day':'Todo el día'):clock(event.start))+' · '+event.title);
    answer = (english?'Today in ':'Hoy en ')+source+' (iCloud, '+stamp+', Puerto Rico). '+(events.join('. ') || (english?'No events listed.':'No hay eventos registrados.'));
    if(result.events.length>12) answer += english?' Showing the first 12 events.':' Se muestran los primeros 12 eventos.';
  } catch {
    answer = english?'I could not verify today’s iCloud calendar.':'No pude verificar la agenda de hoy en iCloud. Si han pasado 30 minutos, vuelve a conectarlo.';
  }
  if(rev!==state.rev || token!==calendarToken || id!==$('icloud-choice').value) return null;
  $('source-calendar').textContent = answer;
  return answer;
}
$('icloud-read').addEventListener('click', () => void calendarToday(false));

function clearIdentity(){
  resetCalendar();
  state.rev++;state.user=null;state.session=null;state.tasks=[];state.memories=[];state.pending=null;state.model=false;state.conversation=null;state.lastReply='';state.tasksLoaded=false;state.memoriesLoaded=false;state.syncSerial+=1;state.historyLoaded=false;state.historySerial+=1;state.historyDetailSerial+=1;state.conversations=[];state.editingTaskId=null;state.editingMemoryId=null;state.tasksVerifiedAt=null;state.memoriesVerifiedAt=null;state.replyLanguage='es';
  for(const controller of state.aborters){controller.abort()}state.aborters.clear();stopVoice();state.voiceEnabled=false;updateVoiceControl();
  $('thread').replaceChildren();$('task-list').replaceChildren();$('memory-list').replaceChildren();$('history-list').replaceChildren();$('history-messages').replaceChildren();visible('history-detail',false);visible('action-box',false);resetTaskEditor();resetMemoryEditor();$('task-search').value='';$('memory-search').value='';$('memory-filter').value='all';syncStatus('Sesión cerrada','idle');renderTrust();
}
function updateIdentity(session){
  const userId=session?.user?.id??null;
  if(userId===state.user){
    state.session=session;
    if(!session){
      visible('login',true);
      visible('workspace',false);
      setStatus('SIN SESIÓN',false);
      syncStatus('Inicia sesión para conectar tus datos.','idle');
    }else{
      visible('login',false);
      visible('workspace',true);
      setStatus('SESIÓN ACTIVA',true);
    }
    return;
  }
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
function sourceIsRecent(kind){
 return kind==='tasks'?state.tasksLoaded&&recentVerification(state.tasksVerifiedAt):state.memoriesLoaded&&recentVerification(state.memoriesVerifiedAt);
}
function renderTrust(){
 const display=(kind,label)=>{
  const stamp=kind==='tasks'?state.tasksVerifiedAt:state.memoriesVerifiedAt;
  if(!sourceIsRecent(kind))return label+': sin verificación reciente';
  return label+': verificado · '+new Date(stamp).toLocaleString('es-PR',{month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});
 };
 $('source-tasks').textContent=display('tasks','Tareas (Supabase)');
 $('source-memory').textContent=display('memories','Memoria (Supabase)');
}
function syncStatus(message,status='idle'){
  const label=$('sync-status');
  const dot=$('sync-indicator');
  if(label)label.textContent=message;
  if(dot){dot.classList.toggle('ok',status==='ok');dot.classList.toggle('error',status==='error')}
}
async function loadWorkspace(){
  if(!ready())return;
  const revision=state.rev;
  const serial=++state.syncSerial;
  $('sync-button').disabled=true;
  state.tasksLoaded=false;state.memoriesLoaded=false;
  state.tasksVerifiedAt=null;state.memoriesVerifiedAt=null;
  renderTrust();drawTasks();drawMemories();
  syncStatus('Sincronizando tareas y memoria...','idle');
  try{
    const results=await Promise.allSettled([
      request('/v1/tasks'),
      request('/v1/memories'),
      fetch(API+'/health',{cache:'no-store'}).then(async r=>{
        if(!r.ok)throw Error('Servidor indisponible');
        return r.json();
      })
    ]);
    if(revision!==state.rev||serial!==state.syncSerial)return;
    const issues=[];
    const tasks=results[0],memories=results[1],health=results[2];
    if(tasks.status==='fulfilled'&&Array.isArray(tasks.value)){
      state.tasks=tasks.value;state.tasksLoaded=true;state.tasksVerifiedAt=Date.now();drawTasks();
    }else{
      state.tasksLoaded=false;
      issues.push('tareas');
      drawTasks();
    }
    if(memories.status==='fulfilled'&&Array.isArray(memories.value)){
      state.memories=memories.value;state.memoriesLoaded=true;state.memoriesVerifiedAt=Date.now();drawMemories();
    }else{
      state.memoriesLoaded=false;
      issues.push('memoria');
      drawMemories();
    }
    if(health.status==='fulfilled'){
      const h=health.value;
      state.model=h?.model_requests_enabled===true;
      $('model-label').textContent=state.model?'IA DISPONIBLE':'IA EN ESPERA';
    }else{state.model=false;$('model-label').textContent='SERVIDOR POR VERIFICAR';issues.push('servidor')}
    renderTrust();
    if(issues.length){
      syncStatus('No se pudo verificar: '+issues.join(', ')+'. Pulsa Actualizar.','error');
      sayNotice('Conexión parcial. Tus datos existentes no se han borrado.');
    }else{
      const stamp=new Date().toLocaleTimeString('es-PR',{hour:'numeric',minute:'2-digit'});
      syncStatus('Datos sincronizados · '+stamp,'ok');
    }
  }catch(e){
    if(revision!==state.rev||serial!==state.syncSerial)return;
    renderTrust();
    syncStatus('No se pudo sincronizar. Pulsa Actualizar.','error');
    sayNotice(e.message||'Error de conexión');
  }finally{
    if(revision===state.rev&&serial===state.syncSerial)$('sync-button').disabled=false;
  }
}
function append(role,content){
  const item=element('article','message '+(role==='user'?'user':'assistant'));
  item.append(element('div','message-label',role==='user'?'TÚ':'JARVIS'),element('div','message-body',content));
  $('thread').append(item);$('thread').scrollTop=$('thread').scrollHeight;
  if(role==='assistant'){state.lastReply=content;if(state.voicePending){state.voicePending=false;if(state.voiceEnabled)speak(content)}}
  return item;
}
function taskLabel(task){
  const due=task.due_at?new Date(task.due_at):null;
  const overdue=due&&Number.isFinite(due.getTime())&&due.getTime()<Date.now()&&task.status!=='done';
  const date=due&&Number.isFinite(due.getTime())?due.toLocaleString('es-PR',{dateStyle:'medium',timeStyle:'short'}):'Sin fecha';
  const priority={high:'ALTA',normal:'NORMAL',low:'BAJA'}[task.priority]||'NORMAL';
  return priority+' / '+(overdue?'ATRASADA · ':'')+date;
}
function taskSort(a,b){
  if(a.status!==b.status)return a.status==='done'?1:-1;
  const ad=a.due_at?Date.parse(a.due_at):Infinity,bd=b.due_at?Date.parse(b.due_at):Infinity;
  if(ad!==bd)return ad-bd;
  const p={high:0,normal:1,low:2};
  return (p[a.priority]??1)-(p[b.priority]??1);
}
function actionButton(label,description,handler){
  const button=element('button','mini',label);
  button.type='button';button.setAttribute('aria-label',description);
  button.addEventListener('click',()=>void handler());
  return button;
}
function drawTasks(){
  const root=$('task-list');root.replaceChildren();
  const pending=state.tasks.filter(x=>x.status!=='done');
  $('task-count').textContent=sourceIsRecent('tasks')?String(pending.length)+' pendientes':'Sin verificar';
  $('dash-pending').textContent=sourceIsRecent('tasks')?String(pending.length):'—';
  $('dash-high').textContent=sourceIsRecent('tasks')?String(pending.filter(x=>x.priority==='high').length):'—';
  $('dash-done').textContent=sourceIsRecent('tasks')?String(state.tasks.length-pending.length):'—';
  if(!sourceIsRecent('tasks')){root.append(element('li','empty','Tareas sin verificación reciente. Pulsa Actualizar.'));return}
  if(!state.tasks.length){root.append(element('li','empty','No hay tareas guardadas.'));return}
  const search=normalize($('task-search').value);
  const filter=$('task-filter').value;
  const filtered=[...state.tasks].filter(task=>{
    if(filter==='pending'&&task.status==='done')return false;
    if(filter==='done'&&task.status!=='done')return false;
    return !search||normalize(task.title).includes(search);
  }).sort(taskSort);
  if(!filtered.length){root.append(element('li','empty','No hay tareas que coincidan con el filtro.'));return}
  for(const task of filtered){
    const row=element('li',task.status==='done'?'item-done':'');
    const main=element('div','item-main');
    main.append(element('div','item-title',task.title),element('div','item-sub',taskLabel(task)));
    const actions=element('div','item-actions');
    actions.append(
      actionButton(task.status==='done'?'Reabrir':'Completar',(task.status==='done'?'Reabrir':'Completar')+' tarea '+task.title,()=>updateTask(task,{status:task.status==='done'?'pending':'done'})),
      actionButton('Editar','Editar tarea '+task.title,()=>editTask(task)),
      actionButton('Borrar','Borrar tarea '+task.title,()=>removeTask(task))
    );
    row.append(main,actions);root.append(row);
  }
}
function drawMemories(){
  const root=$('memory-list');root.replaceChildren();
  $('memory-count').textContent=sourceIsRecent('memories')?String(state.memories.length):'—';
  if(!sourceIsRecent('memories')){root.append(element('li','empty','Memoria sin verificación reciente. Pulsa Actualizar.'));return}
  if(!state.memories.length){root.append(element('li','empty','Aún no has guardado recuerdos.'));return}
  const search=normalize($('memory-search').value);
  const category=$('memory-filter').value;
  const filtered=state.memories.filter(memory=>(category==='all'||memory.category===category)&&(!search||normalize(memory.content).includes(search)||normalize(memory.category||'').includes(search)));
  if(!filtered.length){root.append(element('li','empty','No hay recuerdos que coincidan con la búsqueda.'));return}
  for(const memory of filtered){
    const row=element('li');
    const main=element('div','item-main');
    main.append(element('div','item-title',memory.content),element('div','item-sub',(memory.category||'general').toUpperCase()));
    const actions=element('div','item-actions');
    actions.append(
      actionButton('Editar','Editar recuerdo',()=>editMemory(memory)),
      actionButton('Borrar','Borrar recuerdo',async()=>{
        if(window.confirm('¿Borrar este recuerdo permanentemente?'))await removeMemory(memory.id);
      })
    );
    row.append(main,actions);root.append(row);
  }
}
async function updateTask(task,patch){
  try{await request('/v1/tasks/'+encodeURIComponent(task.id),'PATCH',patch);await loadWorkspace();sayNotice('Tarea actualizada.')}
  catch(e){sayNotice('No se pudo actualizar: '+e.message)}
}
function localDateTimeValue(iso){
  if(!iso)return '';
  const d=new Date(iso);
  if(!Number.isFinite(d.getTime()))return '';
  const local=new Date(d.getTime()-d.getTimezoneOffset()*60000);
  return local.toISOString().slice(0,16);
}
function resetTaskEditor(){
  state.editingTaskId=null;
  $('task-title').value='';
  $('task-due').value='';
  $('task-priority').value='normal';
  $('task-submit').textContent='Añadir tarea';
  visible('task-cancel-edit',false);
}
function editTask(task){
  state.editingTaskId=task.id;
  $('task-title').value=task.title;
  $('task-due').value=localDateTimeValue(task.due_at);
  $('task-priority').value=task.priority||'normal';
  $('task-submit').textContent='Guardar cambios';
  visible('task-cancel-edit',true);
  setTab('tasks');
  $('task-title').focus();
  sayNotice('Editando tarea. Puedes cambiar título, prioridad y fecha.');
}
async function removeTask(task){
  if(!window.confirm('¿Eliminar permanentemente la tarea «'+task.title+'»?'))return;
  try{await request('/v1/tasks/'+encodeURIComponent(task.id),'DELETE');await loadWorkspace();sayNotice('Tarea eliminada.')}
  catch(e){sayNotice('No se pudo eliminar: '+e.message)}
}
function resetMemoryEditor(){
  state.editingMemoryId=null;
  $('memory-content').value='';
  $('memory-category').value='general';
  $('memory-submit').textContent='Guardar recuerdo';
  visible('memory-cancel-edit',false);
}
function editMemory(memory){
  state.editingMemoryId=memory.id;
  $('memory-content').value=memory.content||'';
  const selector=$('memory-category');
  selector.value=[...selector.options].some(o=>o.value===memory.category)?memory.category:'general';
  $('memory-submit').textContent='Guardar cambios';
  visible('memory-cancel-edit',true);
  setTab('memories');
  $('memory-content').focus();
  sayNotice('Puedes corregir el texto y la categoría del recuerdo.');
}
async function removeMemory(id){
  try{await request('/v1/memories/'+encodeURIComponent(id),'DELETE');await loadWorkspace();sayNotice('Recuerdo eliminado.')}
  catch(e){sayNotice('No se pudo eliminar: '+e.message)}
}
async function exportUserData(){
  if(!ready())return;
  // La exportación contiene datos privados: solicitar consentimiento antes de
  // consultar el servidor y generar un archivo local en un dispositivo compartido.
  const confirmed=window.confirm('Esta copia descargará tus tareas, recuerdos e historial privado en un archivo sin cifrar. Evita hacerlo en dispositivos compartidos. ¿Deseas continuar?');
  if(!confirmed)return;
  if(!ready())return;
  $('export-button').disabled=true;
  try{
    const backup=await request('/v1/data/export');
    if(!backup||typeof backup!=='object'||typeof backup.data!=='object')throw Error('Respuesta incompleta');
    const blob=new Blob([JSON.stringify(backup,null,2)],{type:'application/json'});
    const href=URL.createObjectURL(blob);
    const a=document.createElement('a');
    a.href=href;a.download='JARVIS-copia-'+new Date().toISOString().slice(0,10)+'.json';
    document.body.appendChild(a);a.click();a.remove();
    setTimeout(()=>URL.revokeObjectURL(href),30000);
    sayNotice('Copia preparada. Revisa las descargas de Safari; contiene datos personales.');
  }catch(e){sayNotice('No fue posible exportar: '+e.message)}
  finally{$('export-button').disabled=false}
}

async function loadHistory(){
  if(!ready())return;
  const revision=state.rev;
  const serial=++state.historySerial;
  $('history-refresh').disabled=true;
  $('history-status').textContent='Consultando el historial privado...';
  try{
    const conversations=await request('/v1/conversations');
    if(revision!==state.rev||serial!==state.historySerial)return;
    if(!Array.isArray(conversations))throw Error('Respuesta del servidor no válida');
    state.conversations=conversations;
    state.historyLoaded=true;
    drawHistory();
    const count=conversations.length;
    $('history-status').textContent=count?count+' conversación(es) guardada(s) en el servidor.':'Todavía no hay conversaciones guardadas. Los comandos locales no se almacenan aquí.';
  }catch(e){
    if(revision!==state.rev||serial!==state.historySerial)return;
    state.historyLoaded=false;
    $('history-status').textContent='No se pudo consultar el historial: '+e.message;
  }finally{
    if(revision===state.rev&&serial===state.historySerial)$('history-refresh').disabled=false;
  }
}
function drawHistory(){
  const root=$('history-list');root.replaceChildren();
  if(!state.historyLoaded){
    root.append(element('li','empty','Historial no verificado. Consulta el servidor.'));return;
  }
  if(!state.conversations.length){
    root.append(element('li','empty','Sin conversaciones de IA guardadas.'));return;
  }
  for(const conversation of state.conversations){
    if(!conversation||!conversation.id)continue;
    const row=element('li');
    const main=element('div','item-main');
    const created=new Date(conversation.created_at);
    const date=Number.isFinite(created.getTime())?created.toLocaleString('es-PR',{dateStyle:'medium',timeStyle:'short'}):'Sin fecha';
    main.append(element('div','item-title',conversation.title||'Conversación'),element('div','item-sub',date));
    const button=element('button','mini','Abrir');
    button.type='button';button.setAttribute('aria-label','Abrir '+(conversation.title||'conversación'));
    button.addEventListener('click',()=>void openHistory(conversation.id));
    row.append(main,button);root.append(row);
  }
}
async function openHistory(id){
  if(!ready()||!state.conversations.some(x=>x.id===id))return;
  const revision=state.rev;
  const serial=++state.historyDetailSerial;
  const conversation=state.conversations.find(x=>x.id===id);
  $('history-title').textContent=conversation?.title||'Conversación';
  $('history-messages').replaceChildren();
  $('history-messages').append(element('div','empty','Cargando mensajes...'));
  visible('history-detail',true);
  try{
    const messages=await request('/v1/conversations/'+encodeURIComponent(id)+'/messages');
    if(revision!==state.rev||serial!==state.historyDetailSerial)return;
    if(!Array.isArray(messages))throw Error('Formato de mensajes no válido');
    const root=$('history-messages');root.replaceChildren();
    if(!messages.length){root.append(element('div','empty','Esta conversación aún no tiene mensajes.'));return}
    for(const message of messages){
      const role=message.role==='user'?'user':'assistant';
      const item=element('article','message '+role);
      item.append(
        element('div','message-label',role==='user'?'TÚ':'JARVIS'),
        element('div','message-body',String(message.content||''))
      );
      root.append(item);
    }
  }catch(e){
    if(revision===state.rev&&serial===state.historyDetailSerial){
      $('history-messages').replaceChildren(element('div','empty','No se pudieron cargar los mensajes: '+e.message));
    }
  }
}
function closeHistory(){
  state.historyDetailSerial+=1;
  visible('history-detail',false);
  $('history-messages').replaceChildren();
}
function setTab(next){
  if(next==='history'&&!state.historyLoaded&&ready())void loadHistory();
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
function dateKey(date){
  return date.getFullYear()+'-'+String(date.getMonth()+1).padStart(2,'0')+'-'+String(date.getDate()).padStart(2,'0');
}
function localDayPlan(){
  if(!state.tasksLoaded)return 'No puedo preparar un plan fiable sin comprobar primero tus tareas. Pulsa Actualizar datos.';
  const now=new Date();
  const today=dateKey(now);
  const tomorrow=new Date(now.getFullYear(),now.getMonth(),now.getDate()+1);
  const sevenDays=new Date(now.getFullYear(),now.getMonth(),now.getDate()+7);
  const pending=state.tasks.filter(t=>t.status!=='done');
  if(!pending.length)return 'No tienes tareas pendientes registradas. Puedes añadir una tarea en la sección Tareas para preparar tu siguiente plan.';
  const dueDate=t=>{if(!t.due_at)return null;const d=new Date(t.due_at);return Number.isFinite(d.getTime())?d:null};
  const overdue=pending.filter(t=>{const d=dueDate(t);return d&&d.getTime()<now.getTime()});
  const todayPending=pending.filter(t=>{const d=dueDate(t);return d&&dateKey(d)===today&&d.getTime()>=now.getTime()});
  const nextSeven=pending.filter(t=>{const d=dueDate(t);return d&&d>=tomorrow&&d<sevenDays});
  const undated=pending.filter(t=>!dueDate(t));
  const future=pending.filter(t=>{const d=dueDate(t);return d&&d>=sevenDays});
  const countLabel=(n,one,many)=>n+' '+(n===1?one:many);
  const priority={high:0,normal:1,low:2};
  const ordered=[...pending].sort((a,b)=>{
    const as=priority[a.priority]??1,bs=priority[b.priority]??1;
    const ad=dueDate(a),bd=dueDate(b);
    const aUrgency=ad?ad.getTime()<now.getTime()?-2:ad.getTime()<sevenDays.getTime()?-1:0:1;
    const bUrgency=bd?bd.getTime()<now.getTime()?-2:bd.getTime()<sevenDays.getTime()?-1:0:1;
    return aUrgency-bUrgency||as-bs||(ad?.getTime()??Infinity)-(bd?.getTime()??Infinity);
  });
  const starters=ordered.slice(0,3).map((t,i)=>(i+1)+'. '+t.title+(t.priority==='high'?' (prioridad alta)':'')).join('; ');
  return 'Tu plan sugerido de hoy se basa únicamente en tus tareas guardadas. Tienes '+countLabel(pending.length,'tarea pendiente','tareas pendientes')+': '+countLabel(overdue.length,'atrasada','atrasadas')+', '+countLabel(todayPending.length,'por vencer hoy','por vencer hoy')+', '+countLabel(nextSeven.length,'en los próximos seis días','en los próximos seis días')+', '+countLabel(future.length,'con fecha posterior','con fecha posterior')+' y '+countLabel(undated.length,'sin fecha','sin fecha')+'. Te sugiero empezar por: '+starters+'. Este orden es una propuesta; no he cambiado tu calendario.';
}
function localCommand(input){
  const verified=trustedCommand(input,{tasks:state.tasks,loaded:state.tasksLoaded,verifiedAt:state.tasksVerifiedAt});
  if(verified){state.replyLanguage=verified.language;return verified.text;}
  state.replyLanguage='es';
  const normalized=normalize(input);
  if(/^(planifica (mi |el )?(dia|jornada)|planea (mi |el )?dia|organiza (mi |el )?dia|plan de hoy|mis prioridades de hoy)/.test(normalized))return localDayPlan();
  if(/^(resumen( de hoy)?|como va mi dia|mi resumen)/.test(normalized)){
    if(!sourceIsRecent('tasks')||!sourceIsRecent('memories'))return 'Todavía no puedo confirmar tus datos. Pulsa Actualizar datos e inténtalo de nuevo.';
    const pending=state.tasks.filter(x=>x.status!=='done');
    const high=pending.filter(x=>x.priority==='high');
    return 'Tu resumen: '+pending.length+' tarea(s) pendiente(s), '+high.length+' de prioridad alta y '+state.memories.length+' recuerdo(s). '+(pending.length?'Las próximas tareas son: '+pending.slice(0,3).map(x=>x.title).join('; ')+'.':'No tienes pendientes registrados.');
  }
  if(/(que tengo pendiente|mis pendientes|tareas pendientes|que debo hacer)/.test(normalized)){
    if(!sourceIsRecent('tasks'))return 'No he podido verificar tus tareas. Pulsa Actualizar datos.';
    const rows=state.tasks.filter(x=>x.status!=='done').slice(0,8);
    return rows.length?'Tus tareas pendientes: '+rows.map((x,i)=>(i+1)+'. '+x.title).join('; ')+'.':'Tu lista de pendientes está vacía.';
  }
  if(/(que recuerdas|mis recuerdos|mi memoria)/.test(normalized)){
    if(!sourceIsRecent('memories'))return 'No he podido verificar tu memoria. Pulsa Actualizar datos.';
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
    const kind = classifyCommand(command);
    if (calendarToken && (kind === 'calendar' || kind === 'brief')) {
      const english = englishIntent(command);
      state.replyLanguage = english ? 'en' : 'es';
      if (! $('icloud-choice').value) { append('assistant',english?'Choose an iCloud calendar first.':'Selecciona primero un calendario de iCloud.'); return; }
      if (/mañana|ayer|semana|tomorrow|yesterday|week/i.test(command)) {
        append('assistant',english?'I can currently check today in Puerto Rico.':'Por ahora puedo consultar hoy en Puerto Rico.');return;
      }
      const agenda = await calendarToday(english);
      if (agenda) {
        const tasks = kind === 'brief' ? trustedCommand(command,{tasks:state.tasks,loaded:sourceIsRecent('tasks'),verifiedAt:state.tasksVerifiedAt,calendarQueried:true}).text+' ' : '';
        append('assistant',tasks+agenda);
      }
      return;
    }
    const answer=command?localCommand(command):'Te escucho. Dime qué necesitas.';
    if(answer!==null){append('assistant',answer);return}
    if(!state.model){append('assistant','Todavía no tengo habilitada la conversación libre con OpenAI. Puedo ayudarte con tus tareas y recuerdos sin generar gastos de IA. Di «Qué puedes hacer» para ver las órdenes.');return}
    const data=await request('/v1/chat','POST',{message:command||clean,conversation_id:state.conversation,request_id:crypto.randomUUID()});
    if(data?.conversation_id)state.conversation=data.conversation_id;
    append('assistant',data?.reply||'La respuesta no está disponible; consulta el estado de la solicitud.');
  }catch(e){append('assistant','No pude completar la solicitud: '+e.message)}
  finally{state.busy=false;$('send-button').disabled=false}
}

function speak(content,{force=false,language=null}={}){
  if(!('speechSynthesis' in window)){sayNotice('No se puede reproducir audio en este navegador.');return}
  if(!state.voiceEnabled&&!force)return;
  const words=String(content||'').trim().slice(0,3500);
  if(!words)return;
  cancelSpeech();
  const synth=window.speechSynthesis;
  const sequence=state.speechSequence;
  const voices=synth.getVoices();
  const preferred=(language||state.replyLanguage)==='en'?['en-US','en-GB','en']:['es-PR','es-US','es-MX','es-ES'];
  const selected=preferred.map(lang=>voices.find(v=>v.lang.toLowerCase()===lang.toLowerCase())).find(Boolean)||voices.find(v=>v.lang.toLowerCase().startsWith((language||state.replyLanguage)==='en'?'en':'es'));
  const utterance=new SpeechSynthesisUtterance(words);
  if(selected){utterance.voice=selected;utterance.lang=selected.lang}
  else utterance.lang=(language||state.replyLanguage)==='en'?'en-US':'es-PR';
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
$('task-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const title=$('task-title').value.trim();
  if(!title)return;
  const local=$('task-due').value;
  const due=new Date(local);
  if(local&&!Number.isFinite(due.getTime())){sayNotice('La fecha seleccionada no es válida.');return}
  const payload={title,priority:$('task-priority').value,due_at:local?due.toISOString():null};
  const button=$('task-submit');button.disabled=true;
  const editingId=state.editingTaskId;
  try{
    if(editingId){
      if(!state.tasks.some(t=>t.id===editingId))throw Error('La tarea ya no existe en los datos cargados.');
      await request('/v1/tasks/'+encodeURIComponent(editingId),'PATCH',payload);
    }else{
      await request('/v1/tasks','POST',payload);
    }
    resetTaskEditor();
    await loadWorkspace();
    sayNotice(editingId?'Tarea actualizada.':'Tarea guardada.');
  }catch(err){sayNotice('No se pudo guardar: '+err.message)}
  finally{button.disabled=false}
});
$('memory-form').addEventListener('submit',async e=>{
  e.preventDefault();
  const content=$('memory-content').value.trim();
  if(!content)return;
  const payload={content,category:$('memory-category').value};
  const editingId=state.editingMemoryId;
  $('memory-submit').disabled=true;
  try{
    if(editingId){
      if(!state.memories.some(m=>m.id===editingId))throw Error('El recuerdo ya no aparece en los datos cargados.');
      await request('/v1/memories/'+encodeURIComponent(editingId),'PATCH',payload);
    }else{
      await request('/v1/memories','POST',payload);
    }
    resetMemoryEditor();
    await loadWorkspace();
    sayNotice(editingId?'Recuerdo corregido.':'Recuerdo guardado.');
  }catch(err){sayNotice('No se pudo guardar: '+err.message)}
  finally{$('memory-submit').disabled=false}
});
$('task-search').addEventListener('input',drawTasks);
$('task-filter').addEventListener('change',drawTasks);
$('memory-search').addEventListener('input',drawMemories);
$('memory-filter').addEventListener('change',drawMemories);
$('task-cancel-edit').addEventListener('click',()=>{resetTaskEditor();sayNotice('Edición cancelada.')});
$('memory-cancel-edit').addEventListener('click',()=>{resetMemoryEditor();sayNotice('Edición cancelada.')});
$('history-refresh').addEventListener('click',()=>void loadHistory());
$('history-close').addEventListener('click',closeHistory);
$('sync-button').addEventListener('click',()=>void loadWorkspace());
$('export-button').addEventListener('click',()=>void exportUserData());
window.addEventListener('offline',()=>{
  state.tasksLoaded=false;state.memoriesLoaded=false;
  state.tasksVerifiedAt=null;state.memoriesVerifiedAt=null;
  renderTrust();drawTasks();drawMemories();
  syncStatus('Sin Internet. Los datos conservados en pantalla no están verificados.','error');
});
window.addEventListener('online',()=>{if(ready())void loadWorkspace()});
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
function refreshVisibleTrust(){
  if(document.hidden)return;
  renderTrust();
  drawTasks();
  drawMemories();
  if(ready()&&(!sourceIsRecent('tasks')||!sourceIsRecent('memories'))){
    syncStatus('Datos sin verificación reciente. Pulsa Actualizar.','idle');
  }
}
document.addEventListener('visibilitychange',()=>{
  if(document.hidden){stopVoice();voiceStatus('Modo detenido: la página no está visible.','paused');return;}
  refreshVisibleTrust();
});
window.addEventListener('pagehide',()=>{
  // iOS may navigate away without delivering visibilitychange; never leave the microphone active.
  stopVoice();
});
window.addEventListener('focus',refreshVisibleTrust);
supabase.auth.onAuthStateChange((_event,session)=>{queueMicrotask(()=>updateIdentity(session))});
updateVoiceControl();
updateVoiceCompatibility();
renderTrust();
window.jarvisInitialized=true;
window.dispatchEvent(new Event('jarvis:initialized'));
try {
  const {data:{session}}=await supabase.auth.getSession();
  updateIdentity(session);
} catch (error) {
  // Fail closed: discard any stale identity, private workspace and active voice session.
  clearIdentity();
  visible('login',true);visible('workspace',false);
  setStatus('ERROR DE ACCESO',false);
  $('login-message').textContent='No pude comprobar tu sesión. Recarga la página y vuelve a entrar.';
}
