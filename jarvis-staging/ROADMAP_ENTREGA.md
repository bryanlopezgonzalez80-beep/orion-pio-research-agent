# ORIÓN JARVIS — Roadmap de entrega y criterios de aceptación

Estado: desarrollo activo (rama `orion-jarvis-staging`). Este documento no certifica funcionamiento completo.

## Principios no negociables
- No habilitar `ENABLE_MODEL_REQUESTS` ni gastar en OpenAI/API externas hasta recibir aprobación explícita de presupuesto y límites de uso.
- Ninguna clave `sb_secret_`, service role o API privada en archivos frontend.
- Sesiones por Supabase, RLS por propietario y pruebas de separación entre usuarios.
- No inventar recuerdos, eventos, citas, costos ni fechas; distinguir datos sincronizados de datos pendientes.
- Ninguna acción externa sensible sin consentimiento y confirmación; permitir revisión y revocación.
- Safari/iPhone no garantiza reconocimiento continuo en segundo plano ni activación por palabra clave.

## Versiones
### 0.9.2 — publicada
- [x] Interfaz pública PWA y acceso mediante Supabase.
- [x] Módulos consola/tareas/memoria/historial.
- [x] Listado privado de conversaciones almacenadas, solo lectura.
- [x] Búsqueda de tareas y recuerdos; exportación privada.
- [x] Controles de voz experimental y transcripción de reconocimiento.
- [ ] Validación autenticada de extremo a extremo en Safari/iPhone.

### 0.9.3 — en implementación
- [x] Plan diario a partir de tareas sincronizadas (sin calendario ficticio).
- [x] Edición de título, prioridad y fecha de tareas, con cancelar.
- [x] Clasificación y edición de recuerdos.
- [ ] Pruebas de regresión y despliegue público.
- [ ] Prueba de persistencia tras recarga con sesión real.

### 1.0 — conversación inteligente
- [ ] Motor IA conversacional con consentimiento explícito de presupuesto.
- [ ] Control de gasto diario/mensual con rechazo cerrado ante límite.
- [ ] Contexto recuperado desde datos propios con transparencia y límite de tokens.
- [ ] Memoria explícita: crear/editar/olvidar, origen y consentimiento.
- [ ] Conversación por voz: interrupciones, transcripción, seguridad de micrófono.
- [ ] Pruebas end-to-end reales en iPhone y casos de fallos de red/latencia.

### 1.1 — acciones y calendario
- [ ] Conectar calendario autorizado por usuario.
- [ ] Confirmación antes de crear, modificar o eliminar eventos.
- [ ] Registro de acciones, errores, reintentos idempotentes y revocación.
- [ ] Recordatorios y notificaciones únicamente en plataformas compatibles.

### 1.5 — módulos personales
- [ ] Study (reválida y LSAT): fuentes, banco de preguntas, rendimiento.
- [ ] Performance: importación y lectura segura de datos de ciclismo, si se autoriza.
- [ ] Business: documentación y tareas de proyectos sin fuga de información.
- [ ] Life: objetivos personales, preferencias elegidas y agenda.

### 2.0 — experiencia avanzada
- [ ] Interfaz multimodal y presencia visual reactiva, accesible.
- [ ] Evaluación de aplicación nativa iOS para capacidades no permitidas por Safari.
- [ ] Auditoría de seguridad y privacidad de terceros, pruebas de abuso y recuperación.
- [ ] Pruebas en múltiples dispositivos y red intermitente.


## Prioridad transversal: JARVIS Trust & Time Intelligence
Principio de producto: un asistente fiable no inventa agenda, disponibilidad, tiempos de viaje ni acciones ejecutadas. Separa hechos verificables, estimaciones e ideas. Muestra la fuente y vigencia de cada dato crítico y explicita cuándo no está conectado.

### Trust Layer — seguridad, objetividad y fiabilidad
- [ ] Cada compromiso, tarea o reunión mencionado procede de un calendario autorizado o de tareas realmente guardadas; identificar su origen y última sincronización.
- [ ] No presentar una invitación pendiente, un evento cancelado o una hora sin zona horaria como reunión confirmada.
- [ ] Ante conflicto de calendarios, duplicados, dirección ambigua o datos desactualizados, pedir confirmación antes de aconsejar.
- [ ] Separar claramente datos comprobados, recomendaciones basadas en reglas y estimaciones; usar lenguaje calibrado sobre incertidumbre.
- [ ] Comportamiento seguro cuando falla la red, expira la sesión o un proveedor no responde; nunca sustituir el error por una agenda vacía ficticia.
- [ ] Trazabilidad de acciones; registro de qué fue propuesto, confirmado, enviado, guardado o falló, sin registrar secretos en los logs.
- [ ] Indicadores de exactitud, latencia, estabilidad del audio, permisos y tasas de fallo; pruebas de regresión reproducibles.

### Voice-first Executive Briefing (español/English)
- [ ] Entender «JARVIS, ¿qué tengo hoy?», «What I got to do today?», «Do I have any appointments or meetings?» y seguimientos bilingües.
- [ ] Interpretar «hoy», «mañana» y «a las cuatro de la mañana» en la zona horaria local efectiva (America/Puerto_Rico cuando aplique).
- [ ] Responder con eventos confirmados, hora, lugar y fuente; distinguir tareas sin hora de reuniones del calendario.
- [ ] Priorizar mediante urgencia, hora, vencimiento y preferencias proporcionadas explícitamente, sin inventar prioridades.
- [ ] Detectar horarios superpuestos, tiempos insuficientes entre actividades y reuniones sin dirección.
- [ ] Consultar rutas/tráfico en una fuente de mapas autorizada solo cuando sea necesario; distinguir tiempo estimado en vivo de estimación sin tráfico.
- [ ] Calcular hora aconsejable para salir = hora del compromiso − duración estimada de viaje − margen acordado; usar el punto de partida autorizado, no inferir ubicación precisa.
- [ ] Volver a calcular al cambiar el tráfico o la hora del evento; comunicar cambios importantes sin saturar de avisos.
- [ ] Preparar un briefing hablado conciso y permitir interrupciones, aclaraciones y lectura de detalles bajo demanda.
- [ ] Recordatorios y alertas mediante canales y permisos aprobados, con fiabilidad comprobada en iPhone y modo de pantalla bloqueada solo si una implementación compatible lo permite.

### Pruebas de aceptación para el briefing
1. A las 04:00, usuario sin reuniones: JARVIS no inventa citas; declara cuándo se sincronizó el calendario.
2. Reunión a las 09:00 en otro municipio: confirma ubicación/origen, consulta ETA real si hay integración y recomienda salida con margen; nunca inventa minutos ni tráfico.
3. Evento cancelado o modificado: no ofrece información obsoleta y marca la sincronización como pendiente si falla.
4. Consulta en inglés seguida de respuesta en español o viceversa: mantiene datos y contexto correctos.
5. Sin permiso de ubicación/calendario: pide la información mínima o indica claramente lo que no puede verificar.
6. Usuario interrumpe el audio, corrige un dato o pide cambiar una prioridad: se recupera sin duplicar recordatorios ni ejecutar acciones no confirmadas.

## Criterios para declarar «completo»
1. Todas las funciones anteriores implementadas o aceptadas explícitamente como fuera de alcance por el usuario.
2. Pruebas automáticas y manuales con evidencia de backend, frontend, RLS y escenarios de Trust & Time Intelligence.
3. Prueba autenticada y de voz en iPhone validada por usuario (una emulación no sustituye el dispositivo).
4. Costos transparentes y aprobados antes de cualquier función facturable.
5. Manual de uso, privacidad, copias y recuperación disponibles.
6. Despliegue estable y sin errores críticos abiertos.

No afirmar que JARVIS funciona al 100 % antes de satisfacer estos criterios.
