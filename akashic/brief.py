"""Folded briefs: a topic's best genes plus their typed neighbourhood, inside a token budget.

This is what an AI session (or you) loads instead of re-reading sources. It is compact and lossy
by design; every line carries the gene id so any point can be drilled into.
"""

from __future__ import annotations

import sqlite3

from .embed import Embedder
from .search import hybrid

STATE_WEIGHT = {"AXIOM": 1.0, "CORROBORATED": 0.9, "DERIVED": 0.6, "CONTESTED": 0.6, "HYPOTHESIS": 0.35,
                "CANDIDATE": 0.1, "REFUTED": 0.3}
EXPAND_RELS = ("DEPENDS_ON", "CONTRADICTS", "EXTENDS", "DERIVED_FROM", "CAUSES", "PART_OF")


def _line(r: sqlite3.Row) -> str:
    tag = f"{r['state']}/{r['frame']} s={r['support']:.2f} L={r['lineages_for']}"
    if r["state"] == "HYPOTHESIS" and r["unintegrated"]:
        tag += " unintegrated"
    return f"- [{tag}] {r['thesis']} | scope: {r['scope']} | id {r['gene_id'][:13]}"


def _rows(conn: sqlite3.Connection, ids: list[str]) -> dict[str, sqlite3.Row]:
    if not ids:
        return {}
    marks = ",".join("?" * len(ids))
    return {r["gene_id"]: r for r in conn.execute(
        f"""SELECT g.gene_id, g.state, g.frame, g.support, g.lineages_for, g.unintegrated, v.thesis, v.scope
            FROM genes g JOIN gene_versions v ON v.gene_id = g.gene_id AND v.version = g.current_version
            WHERE g.gene_id IN ({marks})""", ids)}


def brief(conn: sqlite3.Connection, topic: str, embedder: Embedder | None = None, k: int = 12,
          budget_tokens: int = 3000, hops: int = 2) -> str:
    vec = embedder.embed([topic])[0] if embedder else None
    hits = hybrid(conn, topic, vec, k=k * 2)
    ranked = sorted(hits, key=lambda h: -(h.score * (0.5 + h.support) * STATE_WEIGHT.get(h.state, 0.2)))[:k]
    core = [h.gene_id for h in ranked]
    seen, frontier, edges = set(core), list(core), []
    for _ in range(hops):
        nxt = []
        for gid in frontier:
            for r in conn.execute(
                f"""SELECT src, dst, rel FROM edges WHERE (src = ? OR dst = ?)
                    AND rel IN ({','.join('?' * len(EXPAND_RELS))})""", (gid, gid, *EXPAND_RELS)):
                edges.append((r["src"], r["rel"], r["dst"]))
                for n in (r["src"], r["dst"]):
                    if n not in seen:
                        seen.add(n)
                        nxt.append(n)
        frontier = nxt
    rows = _rows(conn, list(seen))
    out = [f"# Brief: {topic}", "", "Lossy summary. States: CORROBORATED = evidence + connection; "
           "s = support (a ranking, not a probability); L = independent lineages.", "", "## Core"]
    budget = budget_tokens * 4  # ~4 characters per token
    used = sum(len(x) for x in out)

    def add(line: str) -> bool:
        nonlocal used
        if used + len(line) > budget:
            return False
        out.append(line)
        used += len(line)
        return True

    for gid in core:
        if gid in rows and not add(_line(rows[gid])):
            break
    contra = [(a, b) for a, rel, b in edges if rel == "CONTRADICTS" and a in rows and b in rows]
    if contra and add("\n## Live contradictions"):
        for a, b in dict.fromkeys(contra):
            if not add(f"- {rows[a]['thesis']}  <-x->  {rows[b]['thesis']}"):
                break
    context = [g for g in seen if g not in core and g in rows]
    if context and add("\n## Connected context"):
        for gid in sorted(context, key=lambda g: -rows[g]["support"]):
            if not add(_line(rows[gid])):
                break
    return "\n".join(out)
