# Orion PIO Research Agent

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
```

No subas `.env` ni `secrets.toml` al repositorio.

## Radar automático

El workflow `.github/workflows/weekly-radar.yml` corre los viernes a las 08:00 AST y también puede ejecutarse manualmente desde **Actions → Orion PIO Weekly Radar → Run workflow**.

Si configuraste claves opcionales, añádelas en **GitHub → Settings → Secrets and variables → Actions**.

## Persistencia

El radar automático guarda `pio_dashboard.db` y los reportes en GitHub, por lo que sus actualizaciones sobreviven a reinicios del dashboard. Los cambios manuales hechos dentro de una instancia gratuita de Streamlit (por ejemplo favoritos, CRM o encuestas) pueden no persistir después de que la instancia se reinicie. Para persistencia total de esas funciones conviene migrar la base de datos a un servicio externo en una siguiente fase.