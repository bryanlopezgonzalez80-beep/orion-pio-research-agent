from __future__ import annotations

import pandas as pd
import streamlit as st

from research_agent import source_rate_policy
from data_store import get_papers, upsert_papers
from orion_platform import (
    ACADEMIC_AUTOMATED, PLATFORM_VERSION, SOURCE_BY_NAME, TOPIC_GROUPS, classify_query,
    execute_academic_search, route_query, source_configuration, source_search_url,
)
from platform_store import (
    add_to_collection, create_alert, create_collection, get_alerts, get_collections,
    get_search_history, get_source_health, platform_stats, purge_expired_cache,
)

def _paper_row(p):
    return {
        "Título": p.get("title",""),
        "Año": p.get("year") or (p.get("published_date") or "")[:4],
        "Fuente": p.get("journal") or p.get("source",""),
        "Coincidencia %": p.get("topic_relevance_percent") or float(p.get("relevance_score") or 0)*5,
        "Descubierto vía": p.get("discovered_via",""),
        "URL": p.get("oa_url") or p.get("url",""),
    }

def render_platform():
    st.subheader("🚀 Orion Research Platform")
    st.caption(f"Motor v{PLATFORM_VERSION}: búsqueda enrutada, caché, resiliencia, biblioteca automática, colecciones y alertas.")
    stats=platform_stats()
    a,b,c,d=st.columns(4)
    a.metric("Búsquedas",stats["searches"]); b.metric("Colecciones",stats["collections"])
    c.metric("Alertas activas",stats["alerts"]); d.metric("Caché activa",stats["cache_entries"])

    search_tab,topics_tab,collections_tab,alerts_tab,diag_tab=st.tabs(
        ["🔎 Search Engine","🧭 Topic Explorer","📁 Colecciones","🔔 Alertas","🩺 Diagnóstico"]
    )

    with search_tab:
        prefill=st.session_state.pop("orion_prefill","")
        query=st.text_input("¿Qué quieres investigar?",value=prefill,placeholder="ej. seguridad psicológica y liderazgo")
        domain_options={"Auto":"auto","Académico / PIO":"academic","Derecho PR":"legal_pr","Derecho federal / EE. UU.":"legal_us","Derecho internacional":"legal_intl"}
        domain_label=st.selectbox("Dominio",list(domain_options))
        plan=route_query(query or "industrial organizational psychology",domain_options[domain_label])
        st.caption(f"Router: **{plan['domain']}** · fuentes sugeridas: {', '.join(plan['automated_sources']+plan['manual_sources'])}")
        if plan["domain"]=="academic":
            st.caption("Puedes buscar en español o inglés. Para temas PIO/RR. HH. en español, Orion consulta también una expansión académica en inglés y deduplica los resultados.")

        if plan["domain"]=="academic":
            c1,c2,c3=st.columns(3)
            days=c1.slider("Ventana (días)",7,730,90,1,key="v3_days")
            per_source=c2.slider("Por fuente",3,40,10,1,key="v3_per_source")
            max_keep=c3.slider("Máximo a guardar",20,500,180,10,key="v3_max_keep")
            source_options=ACADEMIC_AUTOMATED
            sources=st.multiselect("Fuentes automáticas",source_options,default=plan["automated_sources"],key="v3_sources")
            if "Semantic Scholar" not in plan["automated_sources"]:
                st.caption("Semantic Scholar está disponible como fuente opcional. Con SEMANTIC_SCHOLAR_API_KEY configurada, Orion la activa automáticamente.")
            force=st.checkbox("Forzar actualización (ignorar caché)",False)
            if st.button("🚀 Buscar y guardar en Biblioteca",type="primary",use_container_width=True,disabled=not query.strip()):
                with st.spinner("Orion consulta las fuentes, reintenta fallos y elimina duplicados…"):
                    out=execute_academic_search(query,days=days,per_source=per_source,sources=sources,max_keep=max_keep,force_refresh=force)
                    upsert_papers(out["results"])
                    st.session_state["orion_v3_outcome"]=out
                st.rerun()
            out=st.session_state.get("orion_v3_outcome")
            if out and out.get("query")==query:
                st.success(f"{out['received']} resultados recibidos · {out['unique']} únicos guardados · {out['duration_ms']/1000:.1f}s")
                if out["errors"]:
                    with st.expander("Avisos de fuentes"):
                        st.code("\n".join(out["errors"]))
                if out.get("source_meta"):
                    st.markdown("##### Uso de fuentes en esta búsqueda")
                    usage=pd.DataFrame([{
                        "Fuente":m.get("source"),
                        "Estado":m.get("status"),
                        "Resultados":m.get("count",0),
                        "Requests":m.get("network_requests",0),
                        "Caché":m.get("cache_hits",0),
                        "Reintentos":m.get("retries",0),
                        "429":m.get("rate_limited",False),
                        "Pausa mínima (s)":m.get("minimum_interval_seconds",0),
                    } for m in out["source_meta"]])
                    st.dataframe(usage,use_container_width=True,hide_index=True)
                    with st.expander("Guía de límites por fuente"):
                        for m in out["source_meta"]:
                            st.write(f"**{m.get('source')}** — {m.get('rate_guidance','')}")
                if out["results"]:
                    df=pd.DataFrame([_paper_row(p) for p in out["results"]])
                    st.dataframe(df,use_container_width=True,hide_index=True,column_config={"URL":st.column_config.LinkColumn("Fuente")})

            if query.strip() and plan["manual_sources"]:
                st.markdown("##### Fuentes complementarias")
                st.caption("Si una API no devuelve resultados o está limitada, abre la misma consulta en estas fuentes.")
                manual_cols=st.columns(2)
                for i,src in enumerate(plan["manual_sources"]):
                    manual_cols[i%2].link_button(
                        f"Buscar en {src}",source_search_url(src,query),use_container_width=True
                    )

            st.divider()
            st.markdown("#### 📡 Radar acumulado")
            st.caption("El Radar conserva los estudios guardados por búsquedas anteriores; una búsqueda nueva se añade y no reemplaza lo que ya estaba visible.")
            radar_papers=get_papers(200)
            if radar_papers:
                radar_df=pd.DataFrame([_paper_row(p) for p in radar_papers])
                st.dataframe(
                    radar_df,
                    use_container_width=True,
                    hide_index=True,
                    column_config={"URL":st.column_config.LinkColumn("Fuente")},
                )
            else:
                st.info("El Radar se llenará con los estudios encontrados por tus búsquedas.")
        else:
            st.info("Para fuentes jurídicas sin API pública estable, Orion abre búsquedas dirigidas en portales oficiales/fiables en vez de simular resultados.")
            if query.strip():
                cols=st.columns(2)
                for i,src in enumerate(plan["manual_sources"]):
                    cols[i%2].link_button(f"Buscar en {src}",source_search_url(src,query),use_container_width=True)
            st.caption("En investigación jurídica, verifica siempre el texto vigente, historial y fuente oficial antes de depender de un resultado.")

    with topics_tab:
        st.write("Explora temas preconfigurados. Un clic los envía al buscador.")
        for group,topics in TOPIC_GROUPS.items():
            with st.expander(group,expanded=group=="Leadership"):
                cols=st.columns(3)
                for i,topic in enumerate(topics):
                    if cols[i%3].button(topic,key=f"topic_{group}_{i}",use_container_width=True):
                        st.session_state["orion_prefill"]=topic; st.rerun()

    with collections_tab:
        c1,c2=st.columns([1,2])
        name=c1.text_input("Nueva colección"); desc=c2.text_input("Descripción")
        if st.button("Crear colección",disabled=not name.strip()):
            create_collection(name,desc); st.rerun()
        collections=get_collections()
        if collections:
            st.dataframe(pd.DataFrame(collections),use_container_width=True,hide_index=True)
            papers=get_papers(500)
            if papers:
                cmap={x["name"]:x["id"] for x in collections}
                pmap={f"{p.get('title','')} — {(p.get('published_date') or '')[:4]}":p["id"] for p in papers}
                cn=st.selectbox("Colección",list(cmap)); pn=st.selectbox("Estudio",list(pmap))
                if st.button("Añadir estudio a colección"):
                    add_to_collection(cmap[cn],pmap[pn]); st.success("Añadido.")
        else:
            st.caption("Todavía no hay colecciones.")

    with alerts_tab:
        q=st.text_input("Consulta de alerta",key="alert_q")
        c1,c2,c3=st.columns(3)
        name=c1.text_input("Nombre",key="alert_name")
        domain=c2.selectbox("Dominio",["auto","academic","legal_pr","legal_us","legal_intl"],key="alert_domain")
        cadence=c3.selectbox("Frecuencia",["daily","weekly"],key="alert_cadence")
        if st.button("Crear alerta",disabled=not q.strip()):
            plan=route_query(q,domain)
            create_alert(name or q,q,domain,plan["automated_sources"],cadence); st.rerun()
        alerts=get_alerts()
        if alerts: st.dataframe(pd.DataFrame(alerts),use_container_width=True,hide_index=True)
        st.caption("Las alertas académicas activas las ejecuta el workflow diario; las jurídicas quedan listas para revisión dirigida.")

    with diag_tab:
        if st.button("Limpiar caché expirada"):
            st.success(f"Entradas eliminadas: {purge_expired_cache()}")
        health=get_source_health()
        if health: st.dataframe(pd.DataFrame(health),use_container_width=True,hide_index=True)
        history=get_search_history(25)
        if history:
            st.markdown("#### Historial reciente")
            st.dataframe(pd.DataFrame(history),use_container_width=True,hide_index=True)

def render_legal():
    st.subheader("⚖️ Orion Legal Research")
    st.caption("Puerto Rico · Federal/Estados Unidos · Internacional")
    query=st.text_input("Consulta jurídica",placeholder="ej. Ley 80 despido injustificado Puerto Rico",key="legal_query")
    jurisdiction=st.radio("Jurisdicción",["Puerto Rico","Federal / EE. UU.","Internacional"],horizontal=True)
    domain={"Puerto Rico":"legal_pr","Federal / EE. UU.":"legal_us","Internacional":"legal_intl"}[jurisdiction]
    plan=route_query(query or "law",domain)
    st.markdown("#### Fuentes recomendadas")
    for src in plan["manual_sources"]:
        spec=SOURCE_BY_NAME[src]; c1,c2=st.columns([3,1])
        c1.write(f"**{src}** — {spec.authority}")
        c2.link_button("Buscar" if query.strip() else "Abrir",source_search_url(src,query) if query.strip() else spec.official_url,use_container_width=True)
    st.warning("La presencia de un documento en el buscador no sustituye verificar vigencia, enmiendas, historial procesal ni citación oficial.")

def render_sources():
    st.subheader("🔌 Fuentes, acceso y credenciales")
    st.write("Orion nunca almacena contraseñas de terceros. Los botones de cuenta abren el portal oficial; las credenciales técnicas van en Secrets/variables de entorno.")
    rows=source_configuration()
    table=pd.DataFrame([{
        "Fuente":r["name"],"Dominio":r["domain"],"Automática":r["automated"],
        "Acceso gratuito":r["free_access"],"Credencial":r["credential_env"] or "—",
        "Configurada":r["credential_configured"],"Autoridad":r["authority"],
        "Pausa mínima (s)":source_rate_policy(r["name"])["minimum_interval_seconds"],
        "Guía":source_rate_policy(r["name"])["guidance"],
    } for r in rows])
    st.dataframe(table,use_container_width=True,hide_index=True)
    st.markdown("#### Acceso oficial")
    cols=st.columns(3)
    for i,r in enumerate(rows):
        url=r["login_url"] or r["official_url"]
        cols[i%3].link_button(f"{r['name']} — {'Login' if r['login_url'] else 'Abrir'}",url,use_container_width=True)
    st.markdown("#### Secrets recomendados")
    st.code("""OPENAI_API_KEY=...
OPENAI_MODEL=gpt-5.6-luna
SEMANTIC_SCHOLAR_API_KEY=...
CROSSREF_EMAIL=...
COURTLISTENER_API_TOKEN=...""",language="text")
    st.caption("No pegues claves en el código ni las subas al repositorio.")
