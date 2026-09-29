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

Cuando `DATABASE_URL` está configurada, los radares automáticos persisten en PostgreSQL y publican sus reportes como artifacts de GitHub Actions; no hacen commits de `pio_dashboard.db`. Sin esa variable, SQLite permanece disponible para desarrollo local. Los cambios dentro de una instancia efímera no deben considerarse persistentes sin un backend PostgreSQL configurado.

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

Las Fases 1–5 están completadas. La Fase 7 incorpora monitoring y observabilidad cloud; las fases restantes continúan según el roadmap vigente.

1. **Fase 1 — Hardening del repositorio y automatización (completada)**
2. **Fase 2 — Suite de pruebas y CI reforzado (completada)**
3. **Fase 3 — PostgreSQL y migración reversible (completada)**
4. **Fase 4 — Backend API (completada)**
5. **Fase 5 — Autenticación de API para integración (completada)**
6. Fase 6 — Almacenamiento de archivos y exportaciones
7. **Fase 7 — Monitoring & Observability (completada)**
8. **Fase 8A — Production Security Hardening (actual)**
9. Fase 9 — Escalabilidad, rendimiento y costos
10. Fase 10 — Preparación para producción y recuperación

### Calidad en Fase 2

Fase 2 añade unit tests, pruebas de integración con servicios externos simulados, smoke tests de Streamlit, medición de coverage y un CI que bloquea regresiones de compilación, pruebas o cobertura. La suite normal es determinista y no necesita internet ni secretos. Consulta `docs/TESTING.md` para ejecutarla localmente.

## Database engines

SQLite continúa siendo el motor local y el fallback predeterminado. Si el entorno contiene un `DATABASE_URL` válido con esquema `postgresql://` o `postgres://`, Orion usa PostgreSQL mediante la misma capa de persistencia. Esta capacidad no significa que producción ya esté migrada o configurada. Consulta `docs/POSTGRES_SETUP.md` antes de habilitarla.

## Orion API

La Fase 4 expone una API FastAPI versionada sobre la misma persistencia y lógica de investigación. Se inicia con `uvicorn orion_api.main:app --host 0.0.0.0 --port 8000`. Consulta `docs/API.md` para endpoints, CORS, autenticación opcional, OpenAPI y contenedor.

## Orion Monitoring

La Fase 7 comprueba cada hora la API, PostgreSQL, persistencia, actividad de radares y salud de fuentes mediante GitHub Actions, sin depender de una computadora local. Consulta `docs/MONITORING.md` para métricas, severidades, límites y operación segura.

## Seguridad de producción

Antes de habilitar el modo de producción, configura `ORION_ENV`, una clave interna robusta y orígenes CORS HTTPS explícitos. Orion falla cerrado si esta configuración es incompleta. Consulta `docs/SECURITY.md` para autenticación, headers, rotación y respuesta a incidentes.


## Deep Harvest PIO

La arquitectura Next Generation —registro de fuentes, checkpoints granulares,
provenance, integridad, citation graph limitado y resolución legítima de acceso—
está documentada en
[`docs/DEEP_HARVEST_NEXT_GENERATION.md`](docs/DEEP_HARVEST_NEXT_GENERATION.md).

Orion's daily refresh now uses a high-recall discovery engine instead of a small fixed topic sample.

- Preserves the 188-query global PIO taxonomy, journal watch, and historical backfill.
- Runs a separate bounded Geographic Evidence Intelligence layer for Puerto Rico, the United States, and Latin America/Caribbean.
- Queries Crossref, PubMed/NCBI, and Europe PMC across the taxonomy.
- Adds arXiv for AI/technology/future-of-work topics.
- Uses Semantic Scholar automatically when its key is configured.
- Rotates OpenAlex safely when no OpenAlex key is configured; OpenAlex is not required.
- Persists every successful query immediately.
- Advances a resumable historical Crossref backfill month by month.
- Exposes `GET /api/v1/radar/status` and asynchronous `POST /api/v1/radar/refresh` for the Site's "Actualizar Radar ahora" flow.
- Keeps Google Scholar, APA PsycNet, SIOP, SSRN, Academy of Management, and DOAJ as directed complementary sources when automated ingestion is unavailable or not authorized.
- Stores study location separately from author affiliation, publication location, and lower-confidence geographic mentions.
- Rotates geographic queries, U.S. state groups, and Latin America/Caribbean groups with independent persistent cursors and budgets.

The design targets maximum practical, lawful coverage; it does not claim literal coverage of every page or licensed database on the internet.
CONUCO and other sources without an authorized automated API remain directed/manual sources. Their records are never assumed to be peer reviewed. See `docs/GEOGRAPHIC_INTELLIGENCE.md`.
