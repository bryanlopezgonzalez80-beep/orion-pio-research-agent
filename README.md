# Orion Research Platform

Dashboard y agente de investigación para Psicología Industrial-Organizacional, Recursos Humanos, liderazgo y desarrollo organizacional.

## Ejecutar localmente

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

## Streamlit Community Cloud

- Repository: este repositorio
- Branch: `main`
- Main file path: `app.py`

En **Advanced settings / Secrets**, añade solo las credenciales que uses:

```toml
OPENAI_API_KEY="..."
OPENAI_MODEL="gpt-5.6-luna"
SEMANTIC_SCHOLAR_API_KEY="..."
CROSSREF_EMAIL="..."
COURTLISTENER_API_TOKEN="..."
```

No subas `.env` ni `secrets.toml` al repositorio.

## Radar automático

- **Daily Radar:** 07:00 AST todos los días mediante `.github/workflows/daily-radar.yml`.
- **Weekly Radar:** 08:00 AST todos los viernes mediante `.github/workflows/weekly-radar.yml`.

Ambos procesos se ejecutan en GitHub Actions, sin depender de una computadora local. También pueden iniciarse manualmente desde la pestaña **Actions** con **Run workflow**.

Si configuraste claves opcionales, añádelas en **GitHub → Settings → Secrets and variables → Actions**.

## Persistencia

El radar automático guarda `pio_dashboard.db` y los reportes en GitHub, por lo que sus actualizaciones sobreviven a reinicios del dashboard. Los cambios manuales hechos dentro de una instancia gratuita de Streamlit (por ejemplo favoritos, CRM o encuestas) pueden no persistir después de que la instancia se reinicie. Para persistencia total de esas funciones conviene migrar la base de datos a un servicio externo en una siguiente fase.

## Orion v3

La capa v3 añade:
- router automático entre investigación académica y Derecho PR / federal / internacional;
- búsqueda académica resiliente con caché, reintentos y circuit breaker;
- guardado automático en Biblioteca;
- historial de búsquedas, colecciones, alertas y salud de fuentes;
- catálogo de fuentes con accesos oficiales y credenciales por Secrets;
- actualización diaria a las 07:00 AST mediante `.github/workflows/daily-radar.yml`;
- paquete de migración a ChatGPT Sites en `site_migration/`.

### Principio de seguridad
Orion no guarda contraseñas de servicios externos. Los logins abren los portales oficiales y las API keys se configuran únicamente mediante variables de entorno/Secrets.

## Roadmap Cloud

La Fase 1 está completada y la Fase 2 está en curso. Las fases siguientes son planificación y no representan funcionalidades ya implementadas.

1. **Fase 1 — Hardening del repositorio y automatización (completada)**
2. **Fase 2 — Suite de pruebas y CI reforzado (actual)**
3. **Fase 3 — Diseño de arquitectura cloud (próxima)**
4. Fase 4 — Base de datos administrada
5. Fase 5 — API de aplicación
6. Fase 6 — Identidad, autenticación y autorización
7. Fase 7 — Almacenamiento de archivos y exportaciones
8. Fase 8 — Ejecución administrada de agentes
9. Fase 9 — Observabilidad, escalabilidad y costos
10. Fase 10 — Preparación para producción y recuperación

### Calidad en Fase 2

Fase 2 añade unit tests, pruebas de integración con servicios externos simulados, smoke tests de Streamlit, medición de coverage y un CI que bloquea regresiones de compilación, pruebas o cobertura. La suite normal es determinista y no necesita internet ni secretos. Consulta `docs/TESTING.md` para ejecutarla localmente.
