"""Bounded citation chaining with provider isolation."""
from __future__ import annotations

import os
from collections import deque
from collections.abc import Callable, Iterable


def citation_limits() -> tuple[int, int, float]:
    return (
        max(0, int(os.getenv("ORION_CITATION_MAX_DEPTH", "1"))),
        max(0, int(os.getenv("ORION_CITATION_MAX_NODES", "100"))),
        max(0.0, float(os.getenv("ORION_CITATION_MIN_RELEVANCE", "0.65"))),
    )


def should_chain(paper: dict, min_relevance: float | None = None) -> bool:
    _, _, configured = citation_limits()
    threshold = configured if min_relevance is None else min_relevance
    text = f"{paper.get('title', '')} {paper.get('work_type', '')}".casefold()
    priority = any(term in text for term in ("systematic review", "meta-analysis", "meta analysis"))
    priority = priority or bool(paper.get("geo_pr") or paper.get("geo_us") or paper.get("favorite"))
    return priority or float(paper.get("relevance_score") or 0) >= threshold


def build_citation_graph(
    seeds: Iterable[dict],
    fetchers: dict[str, Callable[[dict], Iterable[dict]]],
    *,
    max_depth: int | None = None,
    max_nodes: int | None = None,
    min_relevance: float | None = None,
) -> dict:
    configured_depth, configured_nodes, configured_relevance = citation_limits()
    depth_limit = configured_depth if max_depth is None else max(0, max_depth)
    node_limit = configured_nodes if max_nodes is None else max(0, max_nodes)
    relevance = configured_relevance if min_relevance is None else min_relevance
    queue = deque((paper, 0) for paper in seeds if should_chain(paper, relevance))
    seen: set[str] = set()
    nodes: list[dict] = []
    edges: list[dict] = []
    errors: list[dict] = []
    while queue and len(nodes) < node_limit:
        paper, depth = queue.popleft()
        paper_id = str(paper.get("id") or paper.get("doi") or "").casefold()
        if not paper_id or paper_id in seen:
            continue
        seen.add(paper_id)
        nodes.append(paper)
        if depth >= depth_limit:
            continue
        for provider, fetch in fetchers.items():
            try:
                related = list(fetch(paper) or [])
            except Exception as exc:
                errors.append({"provider": provider, "error": type(exc).__name__})
                continue
            for candidate in related:
                if len(nodes) + len(queue) >= node_limit:
                    break
                if not should_chain(candidate, relevance):
                    continue
                target = str(candidate.get("id") or candidate.get("doi") or "").casefold()
                if target and target not in seen:
                    edges.append({"source": paper_id, "target": target, "provider": provider})
                    queue.append((candidate, depth + 1))
    return {"nodes": nodes, "edges": edges, "errors": errors, "max_depth": depth_limit, "max_nodes": node_limit}
