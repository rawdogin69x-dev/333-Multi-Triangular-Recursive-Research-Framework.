"""Hybrid retrieval: FTS5 (exact words) + sqlite-vec (meaning), fused by reciprocal rank."""

from __future__ import annotations

import re
import sqlite3
from dataclasses import dataclass

import sqlite_vec

RRF_K = 60


@dataclass
class Hit:
    gene_id: str
    score: float
    thesis: str
    state: str
    frame: str
    support: float
    cosine: float | None = None


def fts_query(text: str) -> str | None:
    """Turn free text into a safe FTS5 OR-query of quoted terms (no operators pass through)."""
    terms = [t for t in re.findall(r"\w+", text.casefold()) if len(t) > 2]
    return " OR ".join(f'"{t}"' for t in dict.fromkeys(terms)) or None


def vector_neighbours(conn: sqlite3.Connection, embedding: list[float], k: int = 10,
                      exclude: str | None = None) -> list[tuple[str, float]]:
    """(gene_id, cosine similarity) for the k nearest genes. vec0 cosine distance = 1 - cosine."""
    rows = conn.execute(
        "SELECT gene_id, distance FROM gene_vec WHERE embedding MATCH ? AND k = ? ORDER BY distance",
        (sqlite_vec.serialize_float32(embedding), k + (1 if exclude else 0)),
    ).fetchall()
    return [(r[0], 1.0 - r[1]) for r in rows if r[0] != exclude][:k]


def hybrid(conn: sqlite3.Connection, text: str, embedding: list[float] | None = None, k: int = 10,
           include_rejected: bool = False) -> list[Hit]:
    ranks: dict[str, float] = {}
    cos: dict[str, float] = {}
    q = fts_query(text)
    if q:
        for rank, (gid,) in enumerate(conn.execute(
            """SELECT m.gene_id FROM gene_fts f JOIN gene_fts_map m ON m.rowid = f.rowid
               WHERE gene_fts MATCH ? ORDER BY bm25(gene_fts) LIMIT ?""", (q, k * 3))):
            ranks[gid] = ranks.get(gid, 0.0) + 1.0 / (RRF_K + rank + 1)
    if embedding is not None:
        for rank, (gid, c) in enumerate(vector_neighbours(conn, embedding, k * 3)):
            ranks[gid] = ranks.get(gid, 0.0) + 1.0 / (RRF_K + rank + 1)
            cos[gid] = c
    if not ranks:
        return []
    marks = ",".join("?" * len(ranks))
    meta = {r["gene_id"]: r for r in conn.execute(
        f"""SELECT g.gene_id, g.state, g.frame, g.support, v.thesis FROM genes g
            JOIN gene_versions v ON v.gene_id = g.gene_id AND v.version = g.current_version
            WHERE g.gene_id IN ({marks})""", list(ranks))}
    hits = [Hit(gid, s, meta[gid]["thesis"], meta[gid]["state"], meta[gid]["frame"], meta[gid]["support"],
                cos.get(gid))
            for gid, s in ranks.items() if gid in meta
            and (include_rejected or meta[gid]["state"] not in ("REJECTED", "SUPERSEDED"))]
    return sorted(hits, key=lambda h: -h.score)[:k]
