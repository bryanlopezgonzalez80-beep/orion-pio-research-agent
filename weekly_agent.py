"""Radar semanal multifuente para ejecución automática (launchd/cron)."""
from __future__ import annotations

import os
from datetime import date
from pathlib import Path

from data_store import log_radar_run, save_ai_analysis, upsert_papers, verify_database_backend
from research_agent import DEFAULT_SOURCES, DEFAULT_TOPICS, analyze_paper, deduplicate, search_all_sources

ROOT = Path(__file__).resolve().parent
REPORTS = ROOT / "reports"
REPORTS.mkdir(exist_ok=True)


def main():
    verify_database_backend()
    topics = DEFAULT_TOPICS[:10]
    sources = DEFAULT_SOURCES
    all_results, errors = [], []
    for topic in topics:
        print(f"Buscando: {topic}")
        papers, errs = search_all_sources(topic, days=14, per_source=6, sources=sources)
        all_results.extend(papers)
        errors.extend([f"{topic} -> {e}" for e in errs])

    unique = deduplicate(all_results)[:120]
    upsert_papers(unique)
    log_radar_run(sources, topics, len(all_results), len(unique), errors)

    # Analyze only a small top set if the user has configured an API key.
    analyzed = []
    if os.getenv("OPENAI_API_KEY"):
        for p in unique[:8]:
            try:
                data = analyze_paper(p)
                save_ai_analysis(p["id"], data)
                p.update(data)
                analyzed.append(p)
            except Exception as exc:
                errors.append(f"IA {p.get('title','')}: {exc}")

    top = analyzed or unique[:12]
    lines = [
        f"# Radar semanal PIO - {date.today().isoformat()}", "",
        f"Fuentes: {', '.join(sources)}", "",
        f"Resultados recibidos: {len(all_results)} | únicos priorizados: {len(unique)}", "",
    ]
    for i, p in enumerate(top, 1):
        lines += [
            f"## {i}. {p.get('title','Sin título')}",
            f"**Fuente:** {p.get('journal') or p.get('source','')} | **Fecha:** {p.get('published_date','')} | **Afinidad:** {p.get('relevance_score',0)}",
            "",
            p.get("summary") or (p.get("abstract") or "Resumen no disponible")[:900],
            "",
        ]
        if p.get("why_it_matters"):
            lines += [f"**Por qué importa:** {p['why_it_matters']}", ""]
        if p.get("applications"):
            lines += ["**Aplicaciones:**", p["applications"], ""]
        if p.get("url"):
            lines += [f"**Fuente:** {p['url']}", ""]
    if errors:
        lines += ["---", "## Avisos técnicos", ""] + [f"- {e}" for e in errors]

    path = REPORTS / f"weekly_{date.today().isoformat()}.md"
    path.write_text("\n".join(lines), encoding="utf-8")
    print(f"Guardados/actualizados: {len(unique)}")
    print(f"Reporte: {path}")
    if errors:
        print(f"Avisos: {len(errors)}")


if __name__ == "__main__":
    main()
