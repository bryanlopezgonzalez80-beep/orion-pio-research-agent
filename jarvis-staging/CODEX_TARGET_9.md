# ORIÓN JARVIS — Objetivo 9/10: misión de ingeniería para Codex

Fecha de preparación: 2026-11-22. Estado: **plan y criterios de aceptación**, no certificación de calidad ni anuncio de despliegue.

## Contexto verificable
- Repositorio: `bryanlopezgonzalez80-beep/orion-pio-research-agent`.
- Rama base: `orion-jarvis-staging`. Trabajar en ramas auxiliares y PR; nunca fusionar ni publicar sin revisión humana.
- Fuente normativa: `jarvis-staging/ROADMAP_ENTREGA.md`, especialmente `JARVIS Trust & Time Intelligence`.
- La documentación del roadmap marca componentes 0.9.4 integrados pero con despliegue y prueba autenticada iPhone pendientes. Confirmar contra código y entorno real.
- Existe una serie de tests de `briefing.js` y expresiones bilingües. Los informes previos incluyen verificaciones aisladas en V8, **no** evidencia suficiente de suite Node integrada. No asumir estabilidad.
- `jarvis-staging/README.md` describe un shell de staging minimalista; resolver con evidencia cualquier divergencia entre documentos y aplicación desplegada.
- El objetivo del producto es **70% voz / 30% escrito inicialmente**, evolucionando hacia una experiencia predominantemente hablada cuando la plataforma lo soporte. Esto es una preferencia de diseño, no una capacidad ya validada.

## ¿Qué significa realmente 9/10?
El 9/10 será una calificación **basada en evidencia**, evaluada sobre 100 puntos tras una auditoría. No hay puntuación actual verificada. No usar porcentajes de madurez o títulos `production ready` sin pruebas.

| Dimensión | Peso | Evidencia exigida |
| --- | ---: | --- |
| Fiabilidad y pruebas | 20 | Test suite reproducible, integración y regresión, fallos de red, evidencia CI o local con comandos completos |
| Trust & Time Intelligence | 20 | Cero hechos críticos inventados en casos de aceptación, origen y vigencia, datos stale/cancelados, zona horaria y fallbacks seguros |
| Voz y conversación | 20 | Conversaciones es/en, escucha, respuesta, interrupciones, corrección, recuperación sin duplicados, prueba real iPhone |
| Seguridad y privacidad | 15 | Auth, sesiones, RLS multiusuario con fixtures, secretos fuera de frontend, auditoría de permisos y errores |
| Experiencia iPhone/Mac | 10 | Flujo útil, accesible, responsive, tiempos de respuesta medidos, estados inequívocos de audio y conexión |
| Memoria y acciones | 10 | Memoria editable con procedencia, confirmación antes de acciones, idempotencia y prueba de persistencia |
| Operación y documentación | 5 | Runbook, reversibilidad, métricas, límites de costo, despliegue verificado si existe |
| **Total** | **100** | **Objetivo >=90 + todas las barreras obligatorias** |

### Barreras obligatorias (un fallo bloquea el 9/10)
1. Sin filtraciones de datos entre usuarios ni secretos visibles en frontend/logs/PR.
2. Sin ejecución de acciones externas sin consentimiento y sin hacer pasar propuestas por acciones completadas.
3. Sin invenciones en calendario, tareas guardadas, ubicación, tráfico, ETA, citas o recordatorios; fuente, edad y limitación explícitas.
4. Sin cálculo de hora de salida si falta cualquiera de los requisitos: compromiso sincronizado con zona horaria, origen/destino autorizados, proveedor de rutas con tráfico autorizado. No inferir la ubicación del usuario.
5. Suite automatizada de rutas críticas aprobada en entorno reproducible; pendientes y pruebas omitidas reportadas.
6. Validación autenticada de la experiencia de voz en un iPhone físico. Si no hay acceso, etiquetar el estado como **pendiente de aceptación**, no completo.
7. Ningún cambio en producción ni activación de `ENABLE_MODEL_REQUESTS` o APIs facturables sin autorización.

## Plan de ejecución por etapas (con gates)

### P0. Auditoría y baseline reproducible
- Identificar entrypoints, módulos de frontend/backend, rutas de API, esquema/migraciones, autenticación y deployment.
- Leer políticas raíz y roadmap. Comparar documentación vs árbol real y versiones publicadas.
- Ejecutar la suite existente de Node y Python con versiones exactas. Clasificar fallos preexistentes y fallos de entorno.
- Construir matriz de trazabilidad de requisitos a archivos, tests y estado real: `implementado`, `probado`, `desplegado`, `validado en dispositivo`.
- Priorizar defectos P0 por severidad, reproducibilidad y impacto. Corregir al menos uno si el entorno lo permite y entregar PR con rollback.
- **Salida:** pruebas repetibles, informe basado en artefactos, cero suposiciones de funcionalidad.

### P1. Conversación real voice-first
- Verificar el flujo completo de permiso -> captura -> texto -> clasificación/orquestación -> respuesta -> síntesis.
- Investigar explícitamente el caso `Escuchando` sin transcripción en Chrome y las restricciones de Safari.
- Implementar estados robustos, abort/cancel, interrupción de TTS, reintentos idempotentes y prevención de dobles envíos.
- Añadir simulaciones deterministas de reconocimiento/TTS y una lista breve de pruebas manuales en iPhone.
- **Salida:** evidencia de turnos bilingües completos en entorno controlado; prueba iPhone pendiente hasta validación física.

### P2. Trust & Time Intelligence
- Separar `hecho verificado`, `dato local guardado`, `estimación`, `propuesta` y `no disponible`.
- Asegurar caducidad, sincronización, cancelaciones, conflictos, zona horaria `America/Puerto_Rico` cuando corresponda, y no confundir tareas con reuniones.
- Rechazar cualquier cálculo de salida sin conjunto completo de fuentes autorizadas.
- Añadir fixtures de compromisos, fallos de proveedor, registros obsoletos y cambios de idioma.
- **Salida:** baterías negativas de antiinvención y precisión con trazabilidad, sin integraciones de pago.

### P3. Memoria, tareas y seguridad
- Verificar persistencia tras recarga y separación por usuario con datos de prueba.
- Habilitar revisión, edición, eliminación y consentimiento de memoria explícita según roadmap.
- Confirmar acciones antes de ejecutar; estado exacto `propuesto/confirmado/enviado/guardado/error`.
- Auditar tokens frontend, RLS y comportamiento de sesión expirada.
- **Salida:** pruebas de aislamiento y fallos de estado reproducibles.

### P4. Experiencia e interfaz
- Refinar consola futurista propia, accesible, rápida, coherente con una interacción 70% voz.
- Mejorar claridad sobre si JARVIS está escuchando, procesando, hablando o desconectado.
- No añadir animaciones que oculten errores o ralenticen iPhone.
- Preparar checklist de Safari/iPhone autenticado, red intermitente y recuperación.
- **Salida:** mediciones de interacción y verificación manual, sin declarar 100%.

## Requisitos de la primera sesión de Codex
1. Imprime commit de la rama y árbol de paquetes relevantes, sin secretos.
2. Lee `AGENTS.md`, `jarvis-staging/AGENTS.md` y `jarvis-staging/ROADMAP_ENTREGA.md`.
3. Ejecuta pruebas existentes antes de modificar código; muestra comandos, entorno y resultados.
4. Examina especialmente `jarvis-staging/site/briefing.js`, los tests `jarvis-staging/tests/`, módulos de voz y rutas de auth/Supabase.
5. Determina por qué los informes previos no han acreditado `node --test` completo; corrige problemas concretos y reproducibles en vez de seguir acumulando regex.
6. Produce matriz de cobertura e identifica los cinco defectos/gaps principales con severidad.
7. Aplica la mejora de mayor impacto que sea segura y reversible; añade/regenera pruebas reales y ejecútalas.
8. Propón un PR enfocado con diff, resultados, riesgos y rollback. No merges ni despliegues automáticamente.

## Política operativa
- Revisión y pruebas locales sin gastos nuevos. No instalar servicios o dependencias nuevas automáticamente si podrían causar costos, riesgos o permisos.
- CI en runners existentes solo después de comprobar sus límites y efectos; si no se puede ejecutar, informar la limitación.
- No tocar `main`, producción, secretos, datos reales, RLS o infraestructura sensible sin aprobación explícita.
- No alterar ni duplicar la automatización horaria vigente.
- La publicación en Render es un hito separado, sujeto a pruebas y confirmación explícita del usuario.

## Formato de informe por iteración
- Base SHA y rama; commits nuevos y archivos exactos.
- Problema/evidencia -> cambio -> criterio de aceptación.
- Comandos de pruebas **realmente ejecutados**, resultado y entorno.
- Hallazgos de seguridad y privacidad; secretos excluidos.
- Estado: solo local / rama / PR / staging desplegado / producción desplegada / iPhone probado.
- Bloqueos y limitaciones; próximos 1-3 pasos.
- Si no hubo commit o avance demostrable: **"sin cambios nuevos"**, sin inventar progreso.

**Principio final:** JARVIS no debe parecer más capaz de lo que realmente es; alcanzar 9/10 exige evidencia de utilidad, precisión, seguridad y voz práctica, no solamente más código.
