// ORIÓN JARVIS — Trust-first local briefing. No external calls, credentials or inferred calendar events.
export const MAX_TASK_AGE_MS=15*60*1000;
export function recentVerification(timestamp,now=Date.now()){
  return Number.isFinite(timestamp)&&timestamp>0&&timestamp<=now&&now-timestamp<MAX_TASK_AGE_MS;
}
export function normalizedPhrase(value){
  return String(value||'').toLocaleLowerCase('es').normalize('NFD').replace(/[\u0300-\u036f]/g,'').replace(/[¡!¿?.,;:]+/g,' ').replace(/\s+/g,' ').trim();
}
export function englishIntent(phrase){
  const n=normalizedPhrase(phrase).replace(/^(?:oye )?jarvis\s*/,'');
  return /^(what\b|what's\b|do i have\b|when should i\b|what time should i\b|how long\b|are there any\b|show my\b|my schedule\b|my meetings\b|my appointments\b|what\b|show my\b)/.test(n);
}
export function classifyCommand(phrase){
  const n=normalizedPhrase(phrase).replace(/^(?:oye )?jarvis\s*/,'');
  if(/^(?:a que hora (?:debo|deberia|tengo que) salir|cuando (?:debo|deberia) salir|cuanto (?:tardare|se tarda) en llegar|when should i leave|what time should i leave|how long (?:will it take|to get there))\b/.test(n))return 'travel';
  // Questions about a meeting's time or today's appointments still require a connected calendar.
  // Match specific calendar terms, not generic task deadlines or free-form questions.
  if(/^(?:(?:a que hora|cuando|donde) (?:es|sera|tengo) (?:mi |la |el |una |un )?(?:reunion|cita)|(?:tengo|hay) (?:una |alguna |un )?(?:cita|reunion)(?:\b|$)|(?:que|cuales|cuantas|cuantos) (?:citas|reuniones|appointments|meetings) (?:tengo|hay)|(?:what time|when|where) (?:is|are) (?:my |the )?(?:meeting|appointment|meetings|appointments)|(?:what|which|how many) (?:meetings|appointments) (?:do i have|are there)|(?:do i have|have i got) (?:a |an |any )?(?:meeting|appointment|meetings|appointments))\b/.test(n))return 'calendar';
  if(/^(?:tengo (?:(?:alguna|una) reunion|(?:algunas|unas) citas|citas|reuniones)|hay (?:citas|reuniones)|(?:cuales|que) (?:son )?(?:mis )?(?:citas|reuniones)|(?:que|cuales) (?:reuniones|citas) tengo|do i have (?:any )?(?:appointments|meetings)(?: (?:or|and) (?:appointments|meetings))?|are there any (?:appointments|meetings)(?: (?:or|and) (?:appointments|meetings))?|my appointments|my meetings|what(?: is| s|'s)? on my calendar|what(?: is| s|'s)? on my agenda|show my calendar|show my meetings|show my appointments|que (?:hay|tengo) en (?:mi |el )?calendario|que (?:hay|tengo) en (?:mi |la )?agenda|muestrame (?:mi |el )?calendario|muestrame (?:mi |la )?agenda)\b/.test(n))return 'calendar';
  if(/^(?:planifica (?:mi |el )?(?:dia|jornada)|planea (?:mi |el )?dia|organiza (?:mi |el )?dia|plan de hoy|mis prioridades de hoy|que (?:tengo|hay|debo hacer) hoy|what (?:i (?:got|have) to do|do i have|should i do|have i got) today|what is on my schedule today|what am i doing today|my schedule today)\b/.test(n))return 'brief';
  return null;
}
export const BRIEFING_TIME_ZONE='America/Puerto_Rico';
// Pin the calendar day to Puerto Rico; never silently interpret a naive timestamp.
function calendarDay(date){
  return new Intl.DateTimeFormat('en-CA',{timeZone:BRIEFING_TIME_ZONE,year:'numeric',month:'2-digit',day:'2-digit'}).format(date);
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
  const current=now instanceof Date?now:new Date(now);
  if(!Number.isFinite(current.getTime()))throw Error('Invalid briefing timestamp');
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
