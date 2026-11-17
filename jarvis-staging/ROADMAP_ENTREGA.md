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

## Criterios para declarar «completo»
1. Todas las funciones anteriores implementadas o aceptadas explícitamente como fuera de alcance por el usuario.
2. Pruebas automáticas y manuales con evidencia de backend, frontend y RLS.
3. Prueba autenticada y de voz en iPhone validada por usuario (una emulación no sustituye el dispositivo).
4. Costos transparentes y aprobados antes de cualquier función facturable.
5. Manual de uso, privacidad, copias y recuperación disponibles.
6. Despliegue estable y sin errores críticos abiertos.

No afirmar que JARVIS funciona al 100 % antes de satisfacer estos criterios.
