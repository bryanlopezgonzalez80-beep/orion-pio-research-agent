from __future__ import annotations

import os
import json
import shutil
from datetime import date, datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from dotenv import load_dotenv

from data_store import (
    DB_PATH, add_client, add_generated_asset, add_project, add_proposal, create_survey, db_stats,
    get_clients, get_generated_assets, get_paper, get_papers, get_projects, get_proposals,
    get_radar_runs, get_survey_questions, get_survey_responses, get_surveys, log_radar_run,
    save_ai_analysis, save_survey_response, set_favorite, set_read_full, upsert_papers,
)
from export_utils import export_docx, export_pdf, export_pptx
from orion_platform_ui import render_legal, render_platform, render_sources
from research_agent import (
    APP_VERSION, DEFAULT_SOURCES, DEFAULT_TOPICS, analyze_paper, answer_from_library,
    compare_papers, deduplicate, extract_trends, generate_case, generate_class_activity,
    generate_consulting_diagnostic, generate_workshop, search_all_sources, source_search_links,
)

load_dotenv()
st.set_page_config(page_title="PIO Intelligence Hub", page_icon="🧠", layout="wide")

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


def fmt_paper(p):
    return f"{p.get('title','Sin título')} — {(p.get('published_date') or '')[:4]}"


def library_df(papers):
    if not papers:
        return pd.DataFrame()
    return pd.DataFrame(papers)


def paper_card(p, *, section, position):
    widget_id = f"{section}_{position}_{p['id']}"
    with st.container(border=True):
        c1, c2, c3 = st.columns([7, 1, 1])
        c1.markdown(f"### {p.get('title','Sin título')}")
        topical = float(p.get("topic_relevance_percent") or (float(p.get("relevance_score") or 0) * 5))
        c2.metric("Coincidencia", f"{topical:.0f}%")
        c3.metric("Práctica", f"{float(p.get('practical_score') or 0):.1f}/10")
        st.caption(
            f"{p.get('authors','')} · {p.get('journal') or p.get('source','')} · {p.get('published_date','')} · "
            f"Vía: {p.get('discovered_via') or p.get('source','')}"
        )
        if p.get("topics"):
            st.write("**Temas:**", p.get("topics"))
        abstract = p.get("summary") or p.get("abstract") or "Resumen no disponible."
        st.write(abstract[:1100] + ("…" if len(abstract) > 1100 else ""))
        b1, b2, b3, b4, b5 = st.columns([1.2, 1.2, 1.2, 1.1, 3])
        if b1.button("✨ Analizar", key=f"an_{widget_id}"):
            with st.spinner("Analizando evidencia y utilidad práctica…"):
                data = analyze_paper(p)
                save_ai_analysis(p["id"], data)
            st.rerun()
        if b2.button("★ Guardado" if p.get("favorite") else "☆ Favorito", key=f"fav_{widget_id}"):
            set_favorite(p["id"], not bool(p.get("favorite")))
            st.rerun()
        if b3.button("✓ Leer" if p.get("read_full") else "Leer completo", key=f"read_{widget_id}"):
            set_read_full(p["id"], not bool(p.get("read_full")))
            st.rerun()
        link = p.get("oa_url") or p.get("url")
        if link:
            b4.link_button("Fuente", link)
        if p.get("pdf_url"):
            b5.link_button("PDF / OA", p["pdf_url"])
        if p.get("why_it_matters"):
            st.markdown("**Por qué importa**")
            st.write(p.get("why_it_matters"))
            st.markdown("**Aplicaciones**")
            st.write(p.get("applications") or "—")
            if p.get("limitations"):
                with st.expander("Limitaciones / qué verificar"):
                    st.write(p.get("limitations"))
            st.caption(
                f"Evidencia: {p.get('evidence_level') or 'no evaluada'} · "
                f"Utilidad práctica: {float(p.get('practical_score') or 0):.1f}/10 · "
                f"Leer completo: {'Sí' if p.get('read_full') else 'No marcado'}"
            )


st.title("🧠 Orion Research Platform")
st.caption("Research intelligence · PIO · derecho · consultoría · docencia · evidencia")

stats = db_stats()
with st.sidebar:
    st.header("Sistema")
    st.write(f"**Versión:** {APP_VERSION}")
    st.write("**Base de datos:** 🟢 OK")
    st.write("**Agente IA:**", "🟢 Conectado" if os.getenv("OPENAI_API_KEY") else "🟡 Sin API key")
    st.caption(f"Modelo: {os.getenv('OPENAI_MODEL','gpt-5.6-luna')}")
    st.divider()
    st.metric("Estudios", stats["papers"])
    st.metric("Favoritos", stats["favorites"])
    st.metric("Para leer", stats["read_full"])
    st.divider()
    st.caption("La búsqueda académica funciona sin API key. Las funciones generativas requieren IA.")

m1, m2, m3, m4, m5 = st.columns(5)
m1.metric("Biblioteca", stats["papers"])
m2.metric("Favoritos", stats["favorites"])
m3.metric("Leer completos", stats["read_full"])
m4.metric("Clientes", stats["clients"])
m5.metric("Proyectos", stats["projects"])

platform_tab, home_tab, radar_tab, lib_tab, trends_tab, legal_tab, lab_tab, consulting_tab, agent_tab, sources_tab, reports_tab, setup_tab = st.tabs([
    "🚀 Orion", "🏠 Inicio", "🔎 Radar", "📚 Biblioteca", "📈 Tendencias", "⚖️ Legal", "🧪 Laboratorio",
    "💼 Consultoría", "🤖 Agente", "🔌 Fuentes", "📄 Reportes", "⚙️ Sistema"
])

with platform_tab:
    render_platform()

with legal_tab:
    render_legal()

with sources_tab:
    render_sources()

with home_tab:
    st.subheader("Centro de inteligencia PIO")
    c1, c2 = st.columns([1.2, 1])
    with c1:
        st.markdown("""
Este hub está diseñado para convertir **investigación en acción**. El flujo recomendado es:

**Descubrir → filtrar → analizar → guardar → comparar → convertir en taller/clase/caso → aplicar → reportar.**

El radar consulta varias bases académicas en una sola corrida y deduplica resultados por DOI/título. La biblioteca conserva lo encontrado en la base SQLite del entorno activo; el radar semanal en GitHub actualiza y versiona esa base automáticamente.
        """)
        recent = get_papers(5)
        if recent:
            st.markdown("#### Prioridades actuales")
            for p in recent:
                st.write(f"• **{p['title']}** — afinidad {float(p.get('relevance_score') or 0):.1f}")
    with c2:
        st.markdown("#### Cobertura automática")
        st.write("OpenAlex · Crossref · Europe PMC/PubMed · Semantic Scholar · arXiv")
        st.markdown("#### Búsqueda complementaria")
        st.write("Google Scholar · APA PsycNet · SIOP · SSRN · Academy of Management · HBR")
        st.info("Las fuentes complementarias se abren como búsquedas manuales porque varias no ofrecen una API pública estable para búsqueda automatizada.")

with radar_tab:
    st.subheader("Radar multifuente")
    c1, c2, c3 = st.columns(3)
    days = c1.slider("Ventana de publicación (días)", 7, 365, 60, 1)
    per_source = c2.slider("Resultados por fuente y tema", 3, 25, 8, 1)
    max_keep = c3.slider("Máximo a guardar por corrida", 20, 500, 150, 10)
    sources = st.multiselect("Fuentes automáticas", DEFAULT_SOURCES, default=DEFAULT_SOURCES)
    topics = st.multiselect("Temas", DEFAULT_TOPICS, default=[])
    custom = st.text_input("Tema o búsqueda adicional", placeholder="ej. leadership development transfer training")
    st.caption("Selecciona uno o varios temas, o escribe una búsqueda libre. Los resultados de esta corrida se muestran separados de la biblioteca histórica.")

    if st.button("🚀 Ejecutar radar multifuente", type="primary", use_container_width=True):
        queries = list(topics)
        if custom.strip(): queries.append(custom.strip())
        if not queries or not sources:
            st.warning("Selecciona al menos un tema y una fuente.")
        else:
            all_results, all_errors = [], []
            progress = st.progress(0)
            status = st.empty()
            total_steps = len(queries)
            for i, q in enumerate(queries, 1):
                status.write(f"Buscando **{q}** en {len(sources)} fuentes…")
                results, errors = search_all_sources(q, days, per_source, sources)
                all_results.extend(results)
                all_errors.extend([f"{q} → {e}" for e in errors])
                progress.progress(i / total_steps)
            unique = deduplicate(all_results)[:max_keep]
            # Preserve only this run for the Radar view; the database remains the historical library.
            st.session_state["current_search_results"] = unique
            st.session_state["current_search_queries"] = queries
            st.session_state["current_search_timestamp"] = datetime.now().isoformat(timespec="seconds")
            upsert_papers(unique)
            log_radar_run(sources, queries, len(all_results), len(unique), all_errors)
            status.success(f"Radar completado: {len(all_results)} resultados recibidos; {len(unique)} únicos priorizados/guardados.")
            if all_errors:
                with st.expander(f"Avisos de fuentes ({len(all_errors)})"):
                    st.code("\n".join(all_errors))
            st.rerun()

    st.markdown("#### Búsqueda complementaria de fuentes sin API pública estable")
    manual_q = st.text_input("Abrir este tema en fuentes complementarias", value=custom or "industrial organizational psychology leadership")
    if manual_q:
        links = source_search_links(manual_q)
        cols = st.columns(3)
        for i, (name, url) in enumerate(links):
            cols[i % 3].link_button(name, url, use_container_width=True)

    st.divider()
    st.markdown("#### Resultados de esta búsqueda")
    current = st.session_state.get("current_search_results", [])
    current_queries = st.session_state.get("current_search_queries", [])
    if current_queries:
        st.caption("Consulta actual: " + " · ".join(current_queries))
    min_topic = st.slider("Coincidencia temática mínima (%)", 0, 100, 60, 5, key="radar_topic_min")
    source_filter = st.multiselect("Filtrar por origen", DEFAULT_SOURCES, default=[])
    filtered = [
        p for p in current
        if float(p.get("topic_relevance_percent") or (float(p.get("relevance_score") or 0) * 5)) >= min_topic
    ]
    if source_filter:
        filtered = [p for p in filtered if any(s in (p.get("discovered_via") or p.get("source") or "") for s in source_filter)]
    filtered = sorted(
        filtered,
        key=lambda p: (
            float(p.get("topic_relevance_percent") or 0),
            float(p.get("evidence_score") or 0),
            p.get("published_date") or "",
        ),
        reverse=True,
    )
    if current and not filtered:
        st.info("La búsqueda sí recuperó registros, pero ninguno supera el umbral temático actual. Baja el umbral si quieres revisar coincidencias débiles.")
    elif not current:
        st.info("Ejecuta una búsqueda para ver aquí únicamente los resultados de esa corrida.")
    else:
        st.caption(f"{len(filtered)} resultados superan el umbral de relevancia temática.")
        for i, p in enumerate(filtered[:30]):
            paper_card(p, section="current_radar", position=i)

    with st.expander("📚 Biblioteca histórica / radar acumulado"):
        historical = get_papers(150)
        st.write(f"{len(historical)} estudios recientes guardados en la biblioteca. Usa la pestaña Biblioteca para explorarlos sin mezclarlos con la búsqueda actual.")

with lib_tab:
    st.subheader("Biblioteca acumulada")
    papers = get_papers(1000)
    if not papers:
        st.info("Ejecuta el radar para comenzar.")
    else:
        q = st.text_input("Buscar en biblioteca", placeholder="liderazgo, engagement, autor, revista…")
        fav_only = st.checkbox("Solo favoritos")
        read_only = st.checkbox("Solo marcados para leer")
        filtered = papers
        if q.strip():
            needle = q.lower()
            filtered = [p for p in filtered if needle in f"{p.get('title','')} {p.get('authors','')} {p.get('journal','')} {p.get('topics','')} {p.get('abstract','')}".lower()]
        if fav_only: filtered = [p for p in filtered if p.get("favorite")]
        if read_only: filtered = [p for p in filtered if p.get("read_full")]
        df = library_df(filtered)
        if not df.empty:
            cols = [c for c in ["favorite","read_full","title","published_date","journal","source","discovered_via","relevance_score","practical_score","evidence_score","url"] if c in df.columns]
            st.dataframe(df[cols], use_container_width=True, hide_index=True, column_config={
                "favorite": st.column_config.CheckboxColumn("★"), "read_full": st.column_config.CheckboxColumn("Leer"),
                "url": st.column_config.LinkColumn("Fuente"), "relevance_score": st.column_config.NumberColumn("Afinidad", format="%.1f"),
                "practical_score": st.column_config.NumberColumn("Práctica", format="%.1f"), "evidence_score": st.column_config.NumberColumn("Evidencia", format="%.1f"),
            })
            st.download_button("⬇️ Exportar CSV", df.to_csv(index=False).encode("utf-8"), "pio_library.csv", "text/csv")
        st.download_button("Biblioteca para la versión web", json.dumps({"papers": filtered}, ensure_ascii=False, indent=2).encode("utf-8"), "pio_library.json", "application/json")
        st.markdown("#### Fichas")
        for i, p in enumerate(filtered[:15]): paper_card(p, section="library", position=i)

with trends_tab:
    st.subheader("Tendencias y temas emergentes")
    papers = get_papers(1000)
    if not papers:
        st.info("Necesitas una biblioteca para calcular tendencias.")
    else:
        df = pd.DataFrame(papers)
        df["published_date"] = pd.to_datetime(df["published_date"], errors="coerce")
        df["month"] = df["published_date"].dt.to_period("M").astype(str)
        st.markdown("#### Volumen de evidencia por mes")
        monthly = df.dropna(subset=["published_date"]).groupby("month").size().tail(18)
        if not monthly.empty: st.bar_chart(monthly)
        c1, c2 = st.columns(2)
        with c1:
            st.markdown("#### Términos emergentes")
            terms = extract_trends(papers, 20)
            if terms:
                td = pd.DataFrame(terms, columns=["término","apariciones"]).set_index("término")
                st.bar_chart(td)
        with c2:
            st.markdown("#### Fuentes de descubrimiento")
            counts = {}
            for p in papers:
                for s in (p.get("discovered_via") or p.get("source") or "").split(" | "):
                    if s: counts[s] = counts.get(s, 0) + 1
            if counts:
                st.bar_chart(pd.Series(counts).sort_values(ascending=False))
        st.markdown("#### Evolución de temas")
        keyword = st.text_input("Rastrear término", value="leadership")
        if keyword:
            tmp = df[df.apply(lambda r: keyword.lower() in f"{r.get('title','')} {r.get('topics','')} {r.get('abstract','')}".lower(), axis=1)]
            series = tmp.dropna(subset=["published_date"]).groupby("month").size()
            if not series.empty: st.line_chart(series)
            else: st.info("No hay suficientes registros fechados para ese término.")

with lab_tab:
    st.subheader("Laboratorio: convertir evidencia en productos")
    papers = get_papers(400)
    if not papers:
        st.info("Primero llena la biblioteca.")
    else:
        options = {f"{fmt_paper(p)} [{i + 1}]": p for i, p in enumerate(papers)}
        selected_label = st.selectbox("Estudio base", list(options.keys()))
        p = options[selected_label]
        st.caption(p.get("apa_citation") or "Referencia APA pendiente")
        action = st.radio("Qué quieres crear", ["Taller", "Actividad de clase", "Caso empresarial", "Comparar estudios"], horizontal=True)
        content = ""
        asset_type = ""
        if action == "Taller":
            c1, c2 = st.columns(2)
            duration = c1.selectbox("Duración", ["60 minutos","90 minutos","2 horas","3 horas"])
            audience = c2.text_input("Audiencia", value="líderes y supervisores")
            if st.button("Crear taller", type="primary"):
                with st.spinner("Diseñando taller…"): content = generate_workshop(p, duration, audience)
                asset_type = "taller"
        elif action == "Actividad de clase":
            level = st.text_input("Nivel", value="universidad/posgrado")
            if st.button("Crear actividad", type="primary"):
                with st.spinner("Diseñando actividad…"): content = generate_class_activity(p, level)
                asset_type = "actividad_docente"
        elif action == "Caso empresarial":
            sector = st.text_input("Sector del caso", value="empresa de servicios")
            if st.button("Crear caso", type="primary"):
                with st.spinner("Creando caso…"): content = generate_case(p, sector)
                asset_type = "caso"
        else:
            other_labels = st.multiselect("Añade hasta 5 estudios", [x for x in options.keys() if x != selected_label], max_selections=5)
            if st.button("Comparar", type="primary"):
                chosen = [p] + [options[x] for x in other_labels]
                with st.spinner("Comparando evidencia…"): content = compare_papers(chosen)
                asset_type = "comparacion"
        if content:
            st.markdown(content)
            add_generated_asset(p["id"], asset_type, f"{action}: {p['title']}", content)
            st.download_button("Descargar Markdown", content.encode("utf-8"), f"{asset_type}.md", "text/markdown")

        st.divider()
        st.markdown("#### Plantillas de diagnóstico organizacional")
        diag_topic = st.text_input("Tema del diagnóstico", placeholder="seguridad psicológica, liderazgo, clima, engagement…")
        diag_context = st.text_area("Contexto del cliente (opcional)")
        if st.button("Generar diagnóstico"):
            if diag_topic.strip():
                with st.spinner("Construyendo instrumento y plan…"):
                    diag = generate_consulting_diagnostic(diag_topic, diag_context)
                st.markdown(diag)
                add_generated_asset("", "diagnostico", diag_topic, diag)
            else:
                st.warning("Indica un tema.")

with consulting_tab:
    st.subheader("Consultoría: clientes, proyectos y propuestas")
    ctab1, ctab2, ctab3, ctab4 = st.tabs(["Clientes", "Proyectos", "Propuestas", "Encuestas"])
    with ctab1:
        with st.form("new_client", clear_on_submit=True):
            c1,c2 = st.columns(2)
            name = c1.text_input("Nombre / contacto")
            org = c2.text_input("Organización")
            email = c1.text_input("Email")
            phone = c2.text_input("Teléfono")
            status = c1.selectbox("Estado", ["Prospecto","Activo","Pausado","Cerrado"])
            notes = st.text_area("Notas")
            if st.form_submit_button("Añadir cliente") and name.strip():
                add_client(name, org, email, phone, status, notes); st.rerun()
        clients = get_clients()
        if clients: st.dataframe(pd.DataFrame(clients), use_container_width=True, hide_index=True)
    with ctab2:
        clients = get_clients(); client_map = {f"{c['name']} — {c.get('organization','')}": c["id"] for c in clients}
        with st.form("new_project", clear_on_submit=True):
            pname = st.text_input("Proyecto")
            clabel = st.selectbox("Cliente", ["Sin asignar"] + list(client_map.keys()))
            category = st.selectbox("Categoría", ["Diagnóstico","Capacitación","DO","Coaching","Investigación","Docencia","Otro"])
            status = st.selectbox("Estado", ["Idea","Propuesta","Aprobado","En curso","En espera","Completado"])
            due = st.date_input("Fecha objetivo", value=date.today()).isoformat()
            value = st.number_input("Valor estimado ($)", min_value=0.0, step=100.0)
            notes = st.text_area("Notas")
            if st.form_submit_button("Añadir proyecto") and pname.strip():
                add_project(client_map.get(clabel), pname, category, status, due, value, notes); st.rerun()
        projects = get_projects()
        if projects: st.dataframe(pd.DataFrame(projects), use_container_width=True, hide_index=True)
    with ctab3:
        clients = get_clients(); client_map = {f"{c['name']} — {c.get('organization','')}": c["id"] for c in clients}
        with st.form("new_prop", clear_on_submit=True):
            title = st.text_input("Título de propuesta")
            clabel = st.selectbox("Cliente", ["Sin asignar"] + list(client_map.keys()), key="prop_client")
            status = st.selectbox("Estado", ["Borrador","Enviada","Seguimiento","Aceptada","Rechazada"])
            amount = st.number_input("Monto ($)", min_value=0.0, step=100.0)
            sent = st.date_input("Fecha de envío", value=date.today()).isoformat()
            follow = st.date_input("Seguimiento", value=date.today()).isoformat()
            notes = st.text_area("Notas de propuesta")
            if st.form_submit_button("Añadir propuesta") and title.strip():
                add_proposal(client_map.get(clabel), title, status, amount, sent, follow, notes); st.rerun()
        props = get_proposals()
        if props: st.dataframe(pd.DataFrame(props), use_container_width=True, hide_index=True)
    with ctab4:
        st.caption("Encuestas locales tipo Likert. Para distribución pública/externa, exporta las preguntas a tu plataforma de encuestas preferida.")
        with st.form("new_survey", clear_on_submit=True):
            s_title = st.text_input("Título de encuesta")
            s_desc = st.text_area("Descripción")
            s_questions = st.text_area("Ítems (uno por línea)", placeholder="Mi supervisor comunica expectativas claras.\nMe siento seguro/a expresando desacuerdos.")
            sc1,sc2 = st.columns(2)
            s_min = sc1.number_input("Escala mínima", min_value=0, max_value=5, value=1)
            s_max = sc2.number_input("Escala máxima", min_value=2, max_value=10, value=5)
            if st.form_submit_button("Crear encuesta") and s_title.strip() and s_questions.strip():
                qs = [q.strip() for q in s_questions.splitlines() if q.strip()]
                if s_min >= s_max:
                    st.error("La escala máxima debe ser mayor que la mínima.")
                else:
                    create_survey(s_title, s_desc, qs, int(s_min), int(s_max)); st.rerun()
        surveys = get_surveys()
        if surveys:
            smap = {f"{x['title']} — #{x['id']}": x for x in surveys}
            slabel = st.selectbox("Encuesta", list(smap.keys()))
            survey = smap[slabel]
            questions = get_survey_questions(survey["id"])
            st.write(survey.get("description") or "")
            if questions:
                with st.form(f"answer_survey_{survey['id']}"):
                    respondent = st.text_input("Etiqueta del respondente (opcional)")
                    answers = {}
                    for q in questions:
                        answers[str(q["id"])] = st.slider(q["question_text"], int(q["scale_min"]), int(q["scale_max"]), int((q["scale_min"]+q["scale_max"])//2), key=f"q_{q['id']}")
                    if st.form_submit_button("Guardar respuesta"):
                        save_survey_response(survey["id"], respondent, answers); st.rerun()
                responses = get_survey_responses(survey["id"])
                if responses:
                    import json as _json
                    rows=[]
                    for r in responses:
                        vals=_json.loads(r["answers_json"])
                        rows.append({"respondente":r.get("respondent_label"),"fecha":r.get("created_at"),"promedio":sum(vals.values())/len(vals) if vals else 0})
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

with agent_tab:
    st.subheader("Orión PIO: agente sobre tu biblioteca")
    st.caption("Pregunta por tendencias, evidencia, ideas de capacitación, contenidos docentes, diagnósticos o conexiones entre estudios.")
    papers = get_papers(300)
    mode = st.radio("Contexto", ["Toda la biblioteca", "Solo favoritos", "Solo para leer completos"], horizontal=True)
    context = papers
    if mode == "Solo favoritos": context = [p for p in papers if p.get("favorite")]
    elif mode == "Solo para leer completos": context = [p for p in papers if p.get("read_full")]
    question = st.text_area("Pregunta", placeholder="¿Qué evidencia reciente puedo convertir en un taller sobre liderazgo y seguridad psicológica?")
    if st.button("Preguntar a Orión", type="primary"):
        if not question.strip(): st.warning("Escribe una pregunta.")
        elif not context: st.warning("No hay estudios en el contexto seleccionado.")
        else:
            with st.spinner("Sintetizando tu biblioteca…"):
                st.markdown(answer_from_library(question, context))

with reports_tab:
    st.subheader("Reportes y exportaciones")
    papers = get_papers(500)
    if not papers:
        st.info("No hay contenido para exportar.")
    else:
        scope = st.radio("Qué incluir", ["Favoritos", "Para leer completos", "Top 10 por afinidad", "Top 25 por afinidad"], horizontal=True)
        if scope == "Favoritos": selected = [p for p in papers if p.get("favorite")]
        elif scope == "Para leer completos": selected = [p for p in papers if p.get("read_full")]
        elif scope == "Top 10 por afinidad": selected = papers[:10]
        else: selected = papers[:25]
        st.write(f"Estudios incluidos: **{len(selected)}**")
        if selected:
            c1,c2,c3 = st.columns(3)
            c1.download_button("📄 Word", export_docx(selected), "PIO_report.docx", "application/vnd.openxmlformats-officedocument.wordprocessingml.document", use_container_width=True)
            c2.download_button("📕 PDF", export_pdf(selected), "PIO_report.pdf", "application/pdf", use_container_width=True)
            c3.download_button("📊 PowerPoint", export_pptx(selected), "PIO_brief.pptx", "application/vnd.openxmlformats-officedocument.presentationml.presentation", use_container_width=True)
        st.markdown("#### Activos generados")
        assets = get_generated_assets()
        if assets: st.dataframe(pd.DataFrame(assets), use_container_width=True, hide_index=True)
        st.markdown("#### Corridas del radar")
        runs = get_radar_runs(20)
        if runs: st.dataframe(pd.DataFrame(runs), use_container_width=True, hide_index=True)

with setup_tab:
    st.subheader("Sistema, respaldo y automatización")
    st.markdown(f"""
**Versión actual:** `{APP_VERSION}`  
**Base de datos:** `{DB_PATH}`  
**Modo IA:** {'activo' if os.getenv('OPENAI_API_KEY') else 'no configurado'}

Fuentes automáticas: **OpenAlex, Crossref, Europe PMC/PubMed, Semantic Scholar y arXiv**.
    """)
    if DB_PATH.exists():
        st.download_button("💾 Descargar respaldo de la base de datos", DB_PATH.read_bytes(), f"pio_dashboard_backup_{date.today().isoformat()}.db", "application/octet-stream")
    st.markdown("#### Variables opcionales (.env)")
    st.code("""OPENAI_API_KEY=tu_clave
OPENAI_MODEL=gpt-5.6-luna
SEMANTIC_SCHOLAR_API_KEY=
CROSSREF_EMAIL=tu_email@ejemplo.com""", language="text")
    st.caption("Semantic Scholar funciona sin clave en muchos casos, pero una clave puede mejorar límites. Crossref recomienda identificar las solicitudes con email para uso cortés de su API.")
    st.markdown("#### Automatización semanal")
    st.write("`.github/workflows/daily-radar.yml` actualiza Orion todos los días a las 7:00 a. m. de Puerto Rico. Además, el buscador permite actualización manual; la caché, los reintentos y el circuito de protección reducen presión sobre las fuentes.")
    st.warning("El radar de GitHub Actions actualiza la base SQLite y guarda los cambios en el repositorio. Los cambios manuales realizados dentro de una instancia gratuita de Streamlit pueden perderse si la instancia se reinicia; para persistencia total de favoritos, clientes, proyectos y encuestas conviene usar una base externa en una fase posterior.")