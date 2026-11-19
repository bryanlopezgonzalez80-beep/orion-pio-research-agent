# ORIÓN JARVIS — Conversación real (ruta sin servicios facturables)

**Estado:** prototipo experimental local para Mac; NO integrado en el servicio Render, ni desplegado, ni probado en el Mac del usuario.

## Problema confirmado

La interfaz publicada implementa comandos deterministas y síntesis de voz del navegador. La variable \`state.model\` permanece en \`false\`, de modo que los mensajes no reconocidos reciben la advertencia de que la conversación libre está deshabilitada. Reconocer voz y leer mensajes en voz alta **no equivale** a sostener un diálogo con un modelo conversacional.

## Ruta de menor riesgo sin nuevas APIs pagas

1. Modelo de lenguaje local en Mac, ejecutado por el usuario mediante Ollama, sin activar OpenAI API ni modificar \`ENABLE_MODEL_REQUESTS\`. La API local oficial es \`http://127.0.0.1:11434/api/chat\`.
2. Puente HTTP de prueba que escuche **solo** en \`127.0.0.1\`, con origen restringido, sin CORS abierto, sin secretos y sin persistencia de conversaciones.
3. Diálogo multivuelta en español e inglés y síntesis de voz del navegador. El reconocimiento de voz del navegador puede depender de servicios externos: **no prometer voz totalmente offline**.
4. El prototipo **no** puede consultar tareas, recuerdos, citas, tráfico, ubicación ni guardar acciones. Toda afirmación de agenda, disponibilidad, ubicación o acciones ejecutadas debe seguir bloqueada hasta tener conectores autorizados.
5. Mantener el sitio Render aislado del puente local: Render no debe intentar llamar a la Mac, ni exponerse Ollama a Internet. Para iPhone remoto se necesita un diseño posterior autenticado y una revisión de amenazas.

## Pruebas de aceptación antes de integración

- Conversación multivuelta real con un modelo ya descargado en la Mac, sin respuestas de plantilla.
- Entrada escrita y dictado por navegador, con declaración visible de sus limitaciones.
- Respuesta por voz e interrupción, deteniendo reconocimiento y TTS al ocultar/cerrar la página.
- Rechazo de roles \`system\`/ \`tool\` suministrados por cliente, mensajes demasiado largos, host/origen externo y solicitudes sin cabeceras esperadas.
- No enviar historial a servicios facturables y no persistir mensajes en disco.
- Error explícito cuando Ollama o el modelo no estén disponibles, sin fingir una respuesta.
- Pruebas reales de Mac y Safari/Chrome; pruebas de iPhone y publicación pendientes.

## Uso del prototipo autónomo

El prototipo autocontenido se prepara como paquete separado junto con \`test_local_conversation.py\`. Solo debe instalarse y ejecutarse por decisión del usuario en su Mac; no contiene claves privadas y no instala ni descarga modelos automáticamente.

Fuentes: https://docs.ollama.com/api y https://github.com/ollama/ollama/blob/main/docs/macos.mdx

**No considerar ORIÓN JARVIS terminado por esta prueba de concepto.**
