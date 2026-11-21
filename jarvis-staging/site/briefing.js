// ORIÓN JARVIS — Trust-first local briefing. No external calls, credentials or inferred calendar events.
export const MAX_TASK_AGE_MS=15*60*1000;
export function recentVerification(timestamp,now=Date.now()){
  return Number.isFinite(timestamp)&&timestamp>0&&timestamp<=now&&now-timestamp<MAX_TASK_AGE_MS;
}
export function normalizedPhrase(value){
  return String(value||'').replace(/[\u2018\u2019\u02bc]/g,"'").toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060\u2066-\u2069\ufeff]/g,' ').replace(/[¡!¿?.,;:]+/g,' ').replace(/\s+/g,' ').trim();
}
export function englishIntent(phrase){
  const n=normalizedPhrase(phrase).replace(/^(?:oye )?jarvis\s*/,'');
  if(/^(?:(?:can you (?:tell me|check|see)|could you (?:tell me|check)) (?:if|whether)|i have|i've got|there (?:is|are))\b/.test(n))return true;
  return /^((?:will i make it|can i make it)(?: to (?:my |the )?(?:meeting|appointment|doctor(?:'s| s)? appointment|dentist(?:'s| s)? appointment))? on time|should i leave|do i need to leave|what\b|what's\b|do i have\b|have i got\b|when\b|where\b|what time\b|when should i\b|what time should i\b|what time do i\b|how long\b|how much time\b|how soon (?:should i leave|do i need to leave)\b|can you tell me (?:when|where|what time) (?:my |the )?(?:next |upcoming )?(?:meeting|appointment)\b|are there (?:any )?(?:meetings|appointments)\b|is there (?:a |an |any )?(?:meeting|appointment)\b|is (?:my |the )?(?:(?:next|upcoming) )?(?:meeting|appointment)\b|(?:how many|which) (?:meetings|appointments)\b|any (?:meetings|appointments)\b|show my\b|my schedule\b|my meetings\b|my appointments\b|what\b|show my\b)/.test(n);
}
export function classifyCommand(phrase){
  const n=normalizedPhrase(phrase).replace(/^(?:oye )?jarvis\s*/,'');
  if(/^(?:(?:llego|llegare|alcanzare a llegar) a tiempo (?:a|para) (?:mi |la |el )?(?:cita|reunion|consulta|medico|doctor|dentista)|(?:will i make it|can i make it) (?:to (?:my |the )?(?:meeting|appointment|doctor(?:'s| s)? appointment|dentist(?:'s| s)? appointment) )?on time|a que hora (?:debo|deberia|tengo que) salir|cuando (?:debo|deberia) salir|cuanto (?:tardare|se tarda) en llegar|cuanto tiempo (?:tardare|tardaria|se tarda)(?: en (?:llegar|ir|el viaje))?|cuanto (?:dura|durara) (?:el )?(?:viaje|trayecto)|should i leave(?: for (?:my |the )?(?:appointment|meeting))? now|do i need to leave(?: for (?:my |the )?(?:appointment|meeting))? now|how soon should i leave|how soon do i need to leave|salgo ya|debo salir ya|cuanto falta para salir|cuanto tiempo tengo para salir|a que hora salgo|cuando salgo|what time do i leave|when do i leave|when should i leave|what time should i leave|what time do i (?:need|have) to leave|how long (?:will it take|does it take|to get there)(?: to (?:get there|arrive))?|how much time (?:will|does) it take(?: to (?:get there|arrive))?|how long (?:is|will be) (?:the |my )?(?:drive|trip|journey)|cuanto (?:me toma|me tomara|demorare) (?:llegar|en llegar))\b/.test(n))return 'travel';
  // Questions about a meeting's time or today's appointments still require a connected calendar.
  // Match specific calendar terms, not generic task deadlines or free-form questions.
  if(/^(?:(?:a que hora|cuando|donde) (?:es|sera|tengo) (?:mi |la |el |una |un )?(?:reunion|cita)|(?:tengo|hay) (?:una |alguna |un )?(?:cita|reunion)(?:\b|$)|(?:que|cuales|cuantas|cuantos) (?:citas|reuniones|appointments|meetings) (?:tengo|hay)|(?:what time|when|where) (?:is|are) (?:my |the )?(?:(?:next|upcoming) )?(?:meeting|appointment|meetings|appointments)|(?:what|which|how many) (?:meetings|appointments) (?:do i have|are there)|(?:do i have|have i got) (?:a |an |any )?(?:meeting|appointment|meetings|appointments))\b/.test(n))return 'calendar';
  // Spanish medical appointments are calendar questions, never evidence of a saved event.
  // Keep the match anchored to avoid misclassifying generic task discussions.
  if(/^(?:tengo|hay) (?:(?:una|alguna|un) )?(?:(?:cita|consulta) (?:medica|con (?:el |la )?(?:medico|medica|doctor|doctora|dentista))|(?:cita|consulta) (?:del |de la )?(?:dentista|doctor|medico))\b/.test(n))return 'calendar';
  // Natural yes/no voice questions must not imply that a calendar was consulted.
  if(/^(?:can you (?:tell me|check|see) (?:if|whether) |could you (?:tell me|check) (?:if|whether) )?(?:i have|i've got|there (?:is|are)) (?:a |an |any )?(?:meeting|appointment|meetings|appointments)\b/.test(n))return 'calendar';
  // Polite voice questions still require a verified calendar, not generic conversation.
  if(/^can you tell me (?:when|where|what time) (?:my |the )?(?:next |upcoming )?(?:meeting|appointment)\b/.test(n))return 'calendar';
  // Possessive yes/no questions also require verified calendar access.
  if(/^is (?:my |the )?(?:(?:next|upcoming) )?(?:meeting|appointment)\b/.test(n))return 'calendar';
  // Medical appointment time questions require a calendar even when the provider appears before 'appointment'.
  if(/^(?:what time|when|where) (?:is|was|will be) (?:my |the )?(?:(?:next|upcoming) )?(?:doctor(?:'s| s)?|dentist(?:'s| s)?|medical) (?:appointment|visit)\b/.test(n))return 'calendar';
  // Specific appointment types still require calendar access; do not infer real appointments.
  if(/^(?:do i have|have i got) (?:a |an |any )?(?:(?:doctor(?:'s| s)?|dentist(?:'s| s)?|medical|work) )?(?:appointment|meeting)\b/.test(n))return 'calendar';
  // Singular English meeting questions require a verified calendar, never generic chat.
  if(/^is there (?:a |an |any )?(?:meeting|appointment)\b/.test(n))return 'calendar';
  // Elliptical voice questions still require verified calendar access.
  if(/^(?:any (?:meetings|appointments)|(?:alguna|algunas) (?:cita|citas|reunion|reuniones))(?:\b|$)/.test(n))return 'calendar';
  // Natural possessive questions must not fall through to generic chat without a calendar.
  if(/^(?:what(?: is| s|'s)? (?:my |the )?(?:next|upcoming) (?:meeting|appointment)|when(?:'s| is) (?:my |the )?(?:next|upcoming) (?:meeting|appointment)|(?:cuando|donde) (?:tengo|sera) (?:mi |la )?(?:proxima|siguiente) (?:reunion|cita))\b/.test(n))return 'calendar';
  if(/^(?:(?:cuando|a que hora|donde) (?:es|sera) (?:mi |la )?(?:proxima |siguiente )?(?:reunion|cita)|tengo (?:(?:alguna|una) reunion|(?:algunas|unas) citas|citas|reuniones)|hay (?:citas|reuniones)|(?:cuales|que) (?:son )?(?:mis )?(?:citas|reuniones)|(?:que|cuales) (?:reuniones|citas) tengo|do i have (?:any )?(?:appointments|meetings)(?: (?:or|and) (?:appointments|meetings))?|are there (?:any )?(?:appointments|meetings)(?: (?:or|and) (?:appointments|meetings))?|my appointments|my meetings|what(?: is| s|'s)? on my calendar|what(?: is| s|'s)? on my agenda|show my calendar|show my meetings|show my appointments|que (?:hay|tengo) en (?:mi |el )?calendario|que (?:hay|tengo) en (?:mi |la )?agenda|muestrame (?:mi |el )?calendario|muestrame (?:mi |la )?agenda)\b/.test(n))return 'calendar';
  if(/^(?:planifica (?:mi |el )?(?:dia|jornada)|planea (?:mi |el )?dia|organiza (?:mi |el )?dia|plan de hoy|mis prioridades de hoy|que (?:tengo|hay|debo hacer) hoy|what (?:i (?:got|have) to do|do i have|should i do|have i got) today|what is on my schedule today|what am i doing today|my schedule today)\b/.test(n))return 'brief';
  return null;
}
export const BRIEFING_TIME_ZONE='America/Puerto_Rico';
// Pin the calendar day to Puerto Rico; never silently interpret a naive timestamp.
function calendarDay(date){
  // formatToParts avoids locale-dependent MM/DD/YYYY vs YYYY-MM-DD output across JS engines.
  const parts=new Intl.DateTimeFormat('en-US',{timeZone:BRIEFING_TIME_ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).formatToParts(date);
  const values=Object.fromEntries(parts.map(({type,value})=>[type,value]));
  return values.year+'-'+values.month+'-'+values.day;
}
function dueValue(task){
  if(!task||typeof task.due_at!=='string')return null;
  const raw=task.due_at.trim();
  // Reject impossible dates and offsets instead of letting Date silently normalize them.
  const match=/^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2})(?::(\d{2})(?:\.(\d{1,3}))?)?(Z|([+-])(\d{2}):(\d{2}))$/i.exec(raw);
  if(!match)return null;
  const [,year,month,day,hour,minute,second='00',fraction='',zone,sign,offsetHours,offsetMinutes]=match;
  const y=Number(year),mo=Number(month),d=Number(day),h=Number(hour),mi=Number(minute),sec=Number(second);
  if(y<1||mo<1||mo>12||d<1||d>31||h>23||mi>59||sec>59)return null;
  const canonical=new Date(Date.UTC(y,mo-1,d,h,mi,sec));
  if(canonical.getUTCFullYear()!==y||canonical.getUTCMonth()!==mo-1||canonical.getUTCDate()!==d)return null;
  // Real-world UTC offsets are bounded by UTC−12:00 and UTC+14:00; never accept fictitious zones.
  if(zone.toUpperCase()!=='Z'){
    const oh=Number(offsetHours),om=Number(offsetMinutes);
    const minutes=oh*60+om;
    if(om>59||minutes>(sign==='+'?14*60:12*60))return null;
  }
  const date=new Date(raw);
  return Number.isFinite(date.getTime())?date:null;
}
export function safeTaskTitle(title,english=false){
  const cleaned=typeof title==='string'?title.replace(/[\u0000-\u001f\u007f-\u009f\u200b-\u200f\u2028-\u202e\u2060\u2066-\u2069\ufeff]/g,' ').replace(/\s+/g,' ').trim().slice(0,120):'';
  return cleaned||(english?'Untitled':'Sin título');
}
export function dailyBriefing({tasks=[],loaded=false,verifiedAt=null,now=new Date(),english=false}={}){
  // Date(Symbol) and Date(BigInt) throw TypeError; fail closed rather than breaking the voice flow.
  let current;
  try{current=now instanceof Date?now:new Date(now);}catch{current=new Date(NaN);}
  // Fail closed on invalid clock input; never crash the voice briefing or present stale tasks as current.
  if(!Number.isFinite(current.getTime()))return english
    ? 'I cannot verify your tasks because the current time is unavailable. Please check your device clock and update data. Your calendar is not connected to JARVIS.'
    : 'No puedo verificar tus tareas porque la hora actual no está disponible. Comprueba el reloj del dispositivo y actualiza los datos. Tu calendario aún no está conectado a JARVIS.';
  if(!loaded||!Array.isArray(tasks)||!recentVerification(verifiedAt,current.getTime())){
    return english
      ? 'I cannot verify your tasks with recent data. Tap Update data first. Your calendar is not connected to JARVIS.'
      : 'No puedo verificar tus tareas con datos recientes. Pulsa Actualizar datos primero. Tu calendario aún no está conectado a JARVIS.';
  }
  const today=calendarDay(current);
  const sevenDays=new Date(current.getTime()+7*24*60*60*1000);
  // Completed or explicitly cancelled tasks must never be presented as outstanding commitments.
  const inactiveStatuses=new Set(['done','completed','complete','cancelled','canceled']);
  const pending=tasks.filter(x=>x&&typeof x==='object'&&!Array.isArray(x)&&typeof x.title==='string'&&safeTaskTitle(x.title)!=='Sin título'&&!inactiveStatuses.has(String(x.status??'').trim().toLowerCase())&&String(x.status??'pending').trim().toLowerCase()==='pending');
  const overdue=pending.filter(x=>{const d=dueValue(x);return d&&d<current});
  const upcoming=pending.filter(x=>{const d=dueValue(x);return d&&calendarDay(d)===today&&d>=current});
  const rank={high:0,normal:1,low:2};
  const urgency=d=>d?d<current?-2:d<sevenDays?-1:0:1;
  const ordered=[...pending].sort((a,b)=>{
    const da=dueValue(a),db=dueValue(b);
    return urgency(da)-urgency(db)||(rank[String(a.priority??'').trim().toLowerCase()]??1)-(rank[String(b.priority??'').trim().toLowerCase()]??1)||(da?.getTime()??Infinity)-(db?.getTime()??Infinity);
  });
  const taskText=(task,index)=>{
    const d=dueValue(task);
    const date=d?d.toLocaleString(english?'en-US':'es-PR',{timeZone:BRIEFING_TIME_ZONE,month:'short',day:'numeric',hour:'numeric',minute:'2-digit'}):'';
    const high=String(task.priority??'').trim().toLowerCase()==='high'?(english?', high priority':', prioridad alta'):'';
    return (index+1)+'. '+safeTaskTitle(task.title,english)+high+(date?(english?', due '+date:', vence '+date):'');
  };
  const suggestions=ordered.slice(0,3).map(taskText).join('; ');
  const verified=new Date(verifiedAt).toLocaleTimeString(english?'en-US':'es-PR',{timeZone:BRIEFING_TIME_ZONE,hour:'numeric',minute:'2-digit'});
  if(english){
    return 'Based on your JARVIS tasks verified at '+verified+': '+pending.length+' pending, '+overdue.length+' overdue and '+upcoming.length+' due later today. '+(suggestions?'Suggested priorities: '+suggestions+'. ':'No pending tasks were recorded. ')+'Your calendar and live traffic are not connected, so I cannot confirm meetings or departure times. These are task suggestions, not appointments.';
  }
  return 'Según tus tareas de JARVIS verificadas a las '+verified+': '+pending.length+' pendientes, '+overdue.length+' atrasadas y '+upcoming.length+' con vencimiento más tarde hoy. '+(suggestions?'Prioridades sugeridas: '+suggestions+'. ':'No hay tareas pendientes registradas. ')+'Tu calendario y el tráfico en vivo no están conectados; no puedo confirmar reuniones ni horas de salida. Estas son propuestas de tareas, no citas.';
}
export function trustedCommand(input,context={}){
  const kind=classifyCommand(input);
  if(!kind)return null;
  const english=englishIntent(input);
  if(kind==='calendar')return {language:english?'en':'es',text:english
    ?'I cannot verify meetings or appointments. Your calendar is not connected to JARVIS. A task title does not confirm a meeting; no calendar events have been checked.'
    :'No puedo confirmar citas ni reuniones. Tu calendario aún no está conectado a JARVIS. Una tarea no confirma una reunión; no he consultado eventos de calendario.'};
  if(kind==='travel')return {language:english?'en':'es',text:english
    ?'I cannot calculate a reliable departure time. I do not have a verified appointment, an authorized starting point or live traffic data. I will not invent a route or travel duration.'
    :'No puedo calcular una hora fiable para salir. Me falta la cita verificada, un punto de partida autorizado y datos reales de tráfico. No inventaré rutas ni minutos.'};
  return {language:english?'en':'es',text:dailyBriefing({...context,english})};
}
