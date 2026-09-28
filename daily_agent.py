"""Orion daily research refresh for 07:00 Puerto Rico (AST)."""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

from data_store import upsert_papers, verify_database_backend
from orion_platform import execute_academic_search, route_query
from platform_store import alerts_due, mark_alert_run

ROOT=Path(__file__).resolve().parent
REPORTS=ROOT/"reports"
REPORTS.mkdir(exist_ok=True)

CORE_TOPICS=[
    "leadership effectiveness","employee engagement","organizational development",
    "psychological safety workplace","training transfer","workplace wellbeing",
    "team effectiveness","AI human resources workplace",
]

def _run(query,sources=None):
    return execute_academic_search(query,days=14,per_source=6,sources=sources,max_keep=120,retries=2,cache_ttl_hours=6,force_refresh=True)

def main():
    verify_database_backend()
    results=[]; summaries=[]; errors=[]
    for topic in CORE_TOPICS:
        print(f"[core] {topic}")
        out=_run(topic)
        results.extend(out["results"])
        errors.extend([f"{topic}: {e}" for e in out["errors"]])
        summaries.append({"query":topic,"received":out["received"],"unique":out["unique"],"errors":len(out["errors"])})
    for alert in alerts_due():
        plan=route_query(alert["query"],alert.get("domain") or "auto")
        if plan["domain"]!="academic":
            summaries.append({"query":alert["query"],"status":"legal-review","sources":plan["manual_sources"]})
            mark_alert_run(alert["id"]); continue
        try:
            sources=json.loads(alert.get("sources_json") or "[]") or plan["automated_sources"]
        except Exception:
            sources=plan["automated_sources"]
        print(f"[alert] {alert['query']}")
        out=_run(alert["query"],sources)
        results.extend(out["results"])
        errors.extend([f"alert {alert['query']}: {e}" for e in out["errors"]])
        summaries.append({"query":alert["query"],"received":out["received"],"unique":out["unique"],"errors":len(out["errors"])})
        mark_alert_run(alert["id"])
    upsert_papers(results)
    payload={"date":date.today().isoformat(),"queries":summaries,"results_seen":len(results),"errors":errors}
    (REPORTS/f"daily_{date.today().isoformat()}.json").write_text(json.dumps(payload,ensure_ascii=False,indent=2),encoding="utf-8")
    md=[f"# Orion Daily Radar — {date.today().isoformat()}","",f"Resultados procesados: {len(results)}",""]
    for item in summaries:
        md.append(f"- **{item['query']}** — {item.get('unique','—')} únicos; {item.get('errors',0)} avisos")
    if errors: md += ["","## Avisos"]+[f"- {e}" for e in errors]
    (REPORTS/f"daily_{date.today().isoformat()}.md").write_text("\n".join(md),encoding="utf-8")
    print(json.dumps(payload,ensure_ascii=False))

if __name__=="__main__":
    main()
