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
- [x] Pruebas de regresión y despliegue público de 0.9.3.
- [ ] Prueba de persistencia tras recarga con sesión real.

### 0.9.4 — Trust-first briefing bilingüe (código integrado; despliegue por verificar)
- [x] Interpretación local segura de «Qué tengo hoy», «What I got to do today?», preguntas de reuniones y hora de salida.
- [x] Cómputo de tareas pendientes, vencidas y próximas sin confundir tareas con eventos del calendario.
- [x] Procedencia visual Supabase para tareas y recuerdos, hora de última verificación y caducidad tras 15 minutos.
- [x] Si falla la red o expira la frescura de los datos, no presentar conteos antiguos como confirmados.
- [x] Selector de reconocimiento de voz español de Puerto Rico / inglés de EE. UU. y selección de síntesis acorde a la respuesta.
- [x] Prueba local de 35 verificaciones estáticas y de comportamiento, sin gastos de API.
- [ ] Validar estado autenticado en iPhone real y guardado/recarga de datos; las pruebas locales no sustituyen la verificación real.
- [ ] Conectar de forma autorizada calendario y proveedor de tráfico antes de informar reuniones o horas de salida reales.

### 1.0 — conversación inteligente
- [ ] Motor IA conversacional con consentimiento explícito de presupuesto.
- [ ] Control de gasto diario/mensual con rechazo cerrado ante límite.
- [ ] Contexto recuperado desde datos propios con transparencia y límite de tokens.
- [ ] Memoria explícita: crear/editar/olvidar, origen y consentimiento.
- [ ] Conversación por voz: interrupciones, transcripción, seguridad de micrófono.
- [ ] Pruebas end-to-end reales en iPhone y casos de fallos de red/latencia.

### 1.1 — acciones y calendario
- [ ] Conectar calendarios autorizados por usuario: Apple/iCloud, Google Calendar y Outlook/Microsoft 365, según los criterios de «Calendarios de distintas cuentas y conexión voluntaria».
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

### Calendarios de distintas cuentas y conexión voluntaria
Requisito de Bryan, 18 de noviembre de 2026 (America/Puerto_Rico). **Diseño pendiente de implementación y validación real por proveedor.**

La app Calendario del iPhone puede mostrar cuentas de diferentes proveedores. JARVIS debe conectar la cuenta que aloja los eventos; no asumir que todos los eventos visibles en el iPhone pertenecen a iCloud. Una conexión de calendario disponible en ChatGPT no autoriza ni conecta automáticamente la aplicación JARVIS.

| Fuente elegida | Vía prevista | Límite que debe explicar el producto |
| --- | --- | --- |
| Apple / iCloud Calendar | Conector de servidor para iCloud; evaluar CalDAV y la autorización admitida para JARVIS. Apple ofrece autorización de cuenta para apps compatibles y contraseña específica para otras apps. | Verificar compatibilidad antes de ofrecer el flujo. No pedir la contraseña principal de Apple en JARVIS ni en el chat. |
| Calendarios del dispositivo iPhone | EventKit en una futura app iOS con componente nativo y permiso del sistema. | La PWA de Safari no obtiene acceso a EventKit por instalarse en la pantalla de inicio; los eventos exclusivamente locales no aparecen mediante un conector de iCloud. |
| Google Calendar | Google Calendar API y autorización OAuth individual. | Registrar la aplicación y cumplir la verificación que corresponda antes de ofrecer acceso público; respetar permisos efectivos de cada calendario. |
| Outlook.com / Microsoft 365 | Microsoft Graph y autorización delegada individual. | Respetar políticas de la organización; algunas cuentas pueden requerir consentimiento del administrador. |
| Archivo o suscripción iCalendar (.ics) | Importación puntual o suscripción de lectura, como funciones separadas. | Importar un archivo no equivale a sincronización continua; una suscripción no permite editar la fuente y su actualización puede demorarse. |

- [ ] Flujo móvil y accesible: Ajustes → Calendarios → Conectar cuenta → autorizar en el proveedor → elegir calendarios → mostrar estado y última sincronización. Cada persona elige si conecta una o varias cuentas.
- [ ] Lectura inicial para briefing; solicitar capacidad de edición cuando la persona quiera usarla. Explicar la diferencia entre los controles de JARVIS y el permiso real concedido por el proveedor o iOS (EventKit requiere acceso completo para leer eventos).
- [ ] Vista unificada de los calendarios seleccionados, conservando cuenta, calendario, identificador de origen y zona horaria. No copiar eventos entre proveedores por el mero hecho de conectar cuentas.
- [ ] Elegir calendario de destino predeterminado para nuevas citas, permitiendo cambiarlo antes de confirmar. Crear, editar, borrar o invitar requiere autorización para esa acción, permisos efectivos y resultado verificado del proveedor.
- [ ] Aislamiento por usuario de JARVIS: conectar la cuenta de una persona no permite consultar calendarios de otros usuarios. Acceso compartido únicamente mediante los permisos y autorizaciones correspondientes.
- [ ] Credenciales y tokens persistentes solo en servidor y cifrados; secretos fuera de frontend, localStorage, conversación y logs. OAuth con protección de estado, callback validado y PKCE cuando corresponda.
- [ ] Mostrar conexión pendiente, conectada, sincronizando, con error, caducada o revocada según evidencia real. Desconectar detiene trabajos pendientes y acceso futuro y elimina credenciales; explicar qué datos ya importados se conservan y ofrecer borrarlos.
- [ ] Sincronización incremental o por consulta según el proveedor, con reautorización y límites de frecuencia. Conservar cancelaciones, cambios de series recurrentes y excepciones; identificar duplicados sin fusionar eventos solo por tener el mismo título.
- [ ] Una fuente no conectada, una sincronización parcial o un error no permite afirmar «no tienes reuniones». Informar qué cuentas se consultaron, cuándo y cuáles faltan; no prometer actualización instantánea ni avisos con el teléfono bloqueado sin pruebas.
- [ ] Para personas que usan varios proveedores: combinar disponibilidad solo dentro de los permisos concedidos; mostrar conflictos y proponer opciones, sin mover compromisos automáticamente.

**Aceptación mínima antes de anunciar sincronización disponible:**
1. Conectar y revocar una cuenta real de cada proveedor anunciado, desde iPhone; conservar el aislamiento entre dos usuarios de prueba.
2. Leer únicamente los calendarios seleccionados y distinguir cuenta de origen, invitaciones pendientes, eventos cancelados, recurrencias, todo el día y zonas horarias con cambios de horario estacional.
3. Crear o modificar con confirmación en el calendario elegido, comprobar el resultado en el proveedor y evitar duplicados tras reintento o respuesta de red incierta; usar versiones/ETag cuando el proveedor lo admita para detectar ediciones concurrentes.
4. Tras denegación de permiso, expiración, desconexión o error de una de varias cuentas, dar un briefing que declare su cobertura y vigencia reales.
5. Distinguir importación .ics de suscripción y de conexión bidireccional; no publicar calendarios privados para facilitar la conexión.
6. Probar las órdenes «¿Qué tengo hoy?», «What meetings do I have today?» y «Añade esta cita a mi calendario de trabajo», con aclaración del destino si es ambiguo.
7. Documentar registro de aplicaciones, permisos y posibles costes antes de activar conectores. Estas casillas describen trabajo pendiente, no conexiones ya realizadas.

Referencias oficiales revisadas el 18 de noviembre de 2026:
- [Cuentas de calendario en iPhone](https://support.apple.com/en-euro/guide/iphone/iphc37be2016/ios).
- [Autorización de apps para iCloud Mail, Calendar y Contacts](https://support.apple.com/en-us/121539).
- [Niveles de acceso de EventKit](https://developer.apple.com/documentation/eventkit/accessing-calendar-using-eventkit-and-eventkitui).
- [Permisos de Google Calendar API](https://developers.google.com/workspace/calendar/api/auth).
- [Calendarios y permisos delegados de Microsoft Graph](https://learn.microsoft.com/en-us/graph/api/user-list-calendars?view=graph-rest-1.0).

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
