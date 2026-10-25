"""The Arbiter's write API. Only this module writes knowledge tables; every change is an event."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone
from urllib.parse import urlsplit

import sqlite_vec

from . import anchor
from .config import Config
from .ids import now, uuid7
from .lifecycle import (
    Assessment,
    EvidenceRow,
    RejectReason,
    State,
    assess,
    k_required,
    next_state,
    tau,
    topic_of,
)

FRAMES = {"EMPIRICAL", "FORMAL", "ATTRIBUTED", "SPECULATIVE", "METAPHOR"}
# Edges along which a change in dst must trigger a re-check of src (truth maintenance).
DEPENDENCY_RELS = ("DEPENDS_ON", "DERIVED_FROM")


@contextmanager
def tx(conn: sqlite3.Connection):
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
        conn.execute("COMMIT")
    except Exception:
        conn.execute("ROLLBACK")
        raise


def root_domain(uri: str) -> str:
    """Crude registrable domain: last two labels ('a.b.example.org' -> 'example.org').

    Known weakness: wrong for 'co.uk'-style suffixes. Lineages can be merged by hand.
    """
    host = (urlsplit(uri).hostname or uri).lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


class Store:
    def __init__(self, conn: sqlite3.Connection, cfg: Config, actor: str = "arbiter"):
        self.conn, self.cfg, self.actor = conn, cfg, actor

    # -- events -------------------------------------------------------------
    def _event(self, kind: str, gene_id: str | None, before=None, after=None) -> None:
        self.conn.execute(
            "INSERT INTO events(event_id, gene_id, kind, before, after, actor, at) VALUES (?,?,?,?,?,?,?)",
            (uuid7(), gene_id, kind, json.dumps(before), json.dumps(after), self.actor, now()),
        )

    # -- charters -----------------------------------------------------------
    def add_charter(self, question: str, scope: str | None = None, priority: int = 3,
                    done_when: str | None = None) -> str:
        cid = uuid7()
        with tx(self.conn):
            self.conn.execute(
                "INSERT INTO charters(charter_id, question, scope, priority, done_when, created_at) VALUES (?,?,?,?,?,?)",
                (cid, question, scope, priority, done_when, now()),
            )
            self._event("CHARTER_ADDED", None, after={"charter_id": cid, "question": question})
        return cid

    # -- sources ------------------------------------------------------------
    def add_source(self, uri: str, blob_sha256: str, *, lineage_id: str | None = None,
                   reliability: float | None = None, title: str | None = None,
                   authors: str | None = None, published_at: str | None = None,
                   license: str | None = None) -> str:
        row = self.conn.execute("SELECT source_id FROM sources WHERE blob_sha256 = ?", (blob_sha256,)).fetchone()
        if row:
            return row["source_id"]
        sid = uuid7()
        dom = root_domain(uri)
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO sources(source_id, uri, canonical_uri, root_domain, title, authors, published_at,
                       captured_at, blob_sha256, lineage_id, reliability, license)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, uri, uri, dom, title, authors, published_at, now(), blob_sha256,
                 lineage_id or dom,
                 self.cfg.default_source_reliability if reliability is None else reliability, license),
            )
        return sid

    # -- genes --------------------------------------------------------------
    def add_candidate(self, *, taxonomy: str, frame: str, thesis: str, reason: str, scope: str,
                      author: str, example: str | None = None, application: str | None = None,
                      nuance: str | None = None, rule: str | None = None,
                      valid_from: str | None = None, valid_until: str | None = None,
                      charter_id: str | None = None) -> str:
        if frame not in FRAMES:
            raise ValueError(f"frame must be one of {sorted(FRAMES)}")
        gid, ts = uuid7(), now()
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO genes(gene_id, taxonomy, frame, charter_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?)""",
                (gid, taxonomy, frame, charter_id, ts, ts),
            )
            self.conn.execute(
                """INSERT INTO gene_versions(gene_id, version, thesis, reason, example, application, scope,
                       nuance, rule, valid_from, valid_until, author, created_at)
                   VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?)""",
                (gid, thesis, reason, example, application, scope, nuance, rule, valid_from, valid_until,
                 author, ts),
            )
            cur = self.conn.execute(
                "INSERT INTO gene_fts_map(gene_id) VALUES (?)", (gid,)
            )
            self.conn.execute(
                "INSERT INTO gene_fts(rowid, thesis, reason, nuance, scope) VALUES (?,?,?,?,?)",
                (cur.lastrowid, thesis, reason, nuance or "", scope),
            )
            self._event("CANDIDATE", gid, after={"thesis": thesis, "frame": frame, "author": author})
        return gid

    def attach_evidence(self, gene_id: str, source_id: str, *, stance: str, evidence_type: str,
                        quote: str, raw_text: str) -> bool:
        """Record evidence; the quote is verified against the raw source text here, not trusted."""
        offset = anchor.find_quote(quote, raw_text)
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO evidence(evidence_id, gene_id, source_id, stance, evidence_type, quote,
                       quote_offset, verified_quote, added_at)
                   VALUES (?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(gene_id, source_id, stance) DO NOTHING""",
                (uuid7(), gene_id, source_id, stance, evidence_type, quote, offset,
                 int(offset is not None), now()),
            )
        return offset is not None

    def add_edge(self, src: str, dst: str, rel: str, note: str | None = None) -> None:
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO edges(edge_id, src, dst, rel, note, created_by, created_at)
                   VALUES (?,?,?,?,?,?,?) ON CONFLICT(src, dst, rel) DO NOTHING""",
                (uuid7(), src, dst, rel, note, self.actor, now()),
            )

    def upsert_vector(self, gene_id: str, embedding: list[float]) -> None:
        g = self.conn.execute("SELECT frame, taxonomy FROM genes WHERE gene_id = ?", (gene_id,)).fetchone()
        with tx(self.conn):
            self.conn.execute("DELETE FROM gene_vec WHERE gene_id = ?", (gene_id,))
            self.conn.execute(
                "INSERT INTO gene_vec(gene_id, embedding, frame, topic) VALUES (?,?,?,?)",
                (gene_id, sqlite_vec.serialize_float32(embedding), g["frame"],
                 topic_of(g["taxonomy"], self.cfg.gravity.topic_depth)),
            )

    # -- admission ----------------------------------------------------------
    def anchor_check(self, gene_id: str) -> State:
        """Step 1: CANDIDATE -> HYPOTHESIS, or REJECTED with a named reason."""
        gene = self._gene(gene_id)
        if gene["state"] != State.CANDIDATE.value:
            return State(gene["state"])
        quotes = [r["quote"] for r in self.conn.execute(
            "SELECT quote FROM evidence WHERE gene_id = ? AND stance = 'FOR' AND verified_quote = 1",
            (gene_id,))]
        reason: RejectReason | None = None
        if not quotes:
            reason = RejectReason.VIKALPA
        elif anchor.unsupported_numbers(gene["thesis"], quotes):
            reason = RejectReason.NUMBER_MISMATCH
        if reason:
            self.reject(gene_id, reason)
            return State.REJECTED
        self._set_state(gene_id, State.CANDIDATE, State.HYPOTHESIS, Assessment(0, 0, 0, 0))
        return self.reassess(gene_id)

    def reject(self, gene_id: str, reason: RejectReason) -> None:
        g = self._gene(gene_id)
        expires = (datetime.now(timezone.utc) + timedelta(days=self.cfg.tombstone_days)).isoformat(timespec="seconds")
        key = "claim:" + anchor.normalise(g["thesis"])
        with tx(self.conn):
            self.conn.execute(
                "UPDATE genes SET state = 'REJECTED', reject_reason = ?, updated_at = ? WHERE gene_id = ?",
                (reason.value, now(), gene_id),
            )
            self.conn.execute(
                """INSERT INTO tombstones(key, kind, reason, nearest_gene, rejected_at, expires_at)
                   VALUES (?,?,?,?,?,?) ON CONFLICT(key) DO UPDATE SET rejected_at = excluded.rejected_at,
                   expires_at = excluded.expires_at, reason = excluded.reason""",
                (key, "CLAIM", reason.value, gene_id, now(), expires),
            )
            self._event("REJECTED", gene_id, before=g["state"], after=reason.value)

    def topic_mass(self, taxonomy: str) -> float:
        topic = topic_of(taxonomy, self.cfg.gravity.topic_depth)
        row = self.conn.execute(
            """SELECT COALESCE(SUM(support), 0) FROM genes
               WHERE state IN ('CORROBORATED', 'AXIOM') AND (taxonomy = ? OR taxonomy LIKE ? ESCAPE '\\')""",
            (topic, topic.replace("%", r"\%").replace("_", r"\_") + ".%"),
        ).fetchone()
        return float(row[0])

    def reassess(self, gene_id: str) -> State:
        """Step 3: recompute evidence and move the gene to where the gravity rule puts it."""
        g = self._gene(gene_id)
        current = State(g["state"])
        if current == State.CANDIDATE:
            return current
        rows = [
            EvidenceRow(r["lineage_id"], r["stance"], r["evidence_type"], r["reliability"], bool(r["verified_quote"]))
            for r in self.conn.execute(
                """SELECT s.lineage_id, e.stance, e.evidence_type, s.reliability, e.verified_quote
                   FROM evidence e JOIN sources s USING(source_id) WHERE e.gene_id = ?""",
                (gene_id,),
            )
        ]
        a = assess(rows, self.cfg.weights)
        mass = self.topic_mass(g["taxonomy"])
        # A gene's own support must not raise the bar it is being judged against.
        if current.value in ("CORROBORATED", "AXIOM"):
            mass = max(0.0, mass - g["support"])
        new = next_state(current, g["frame"], a, mass, self.cfg.gravity,
                         ever_promoted=g["tau_at_promotion"] is not None)
        self._set_state(gene_id, current, new, a,
                        tau_promo=tau(mass, self.cfg.gravity) if new == State.CORROBORATED and current != new else None)
        return new

    def gravity_view(self, taxonomy: str) -> dict:
        m = self.topic_mass(taxonomy)
        return {"topic": topic_of(taxonomy, self.cfg.gravity.topic_depth), "mass": m,
                "tau": tau(m, self.cfg.gravity), "k_required": k_required(m, self.cfg.gravity)}

    # -- truth maintenance --------------------------------------------------
    def dependants(self, gene_id: str) -> list[str]:
        q = f"SELECT src FROM edges WHERE dst = ? AND rel IN ({','.join('?' * len(DEPENDENCY_RELS))})"
        return [r[0] for r in self.conn.execute(q, (gene_id, *DEPENDENCY_RELS))]

    def _set_state(self, gene_id: str, before: State, after: State, a: Assessment,
                   tau_promo: float | None = None) -> None:
        with tx(self.conn):
            self.conn.execute(
                """UPDATE genes SET state = ?, support = ?, against = ?, lineages_for = ?, lineages_against = ?,
                       tau_at_promotion = COALESCE(?, tau_at_promotion), updated_at = ? WHERE gene_id = ?""",
                (after.value, a.support, a.against, a.lineages_for, a.lineages_against, tau_promo, now(), gene_id),
            )
            if before != after:
                self._event("STATE", gene_id, before=before.value, after=after.value)
                for dep in self.dependants(gene_id):
                    self.conn.execute(
                        """INSERT INTO tasks(task_id, kind, payload_json, priority, created_at)
                           VALUES (?,?,?,?,?)""",
                        (uuid7(), "RECHECK", json.dumps({"gene_id": dep, "because": gene_id}), 2, now()),
                    )

    def _gene(self, gene_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            """SELECT g.*, v.thesis FROM genes g JOIN gene_versions v
               ON v.gene_id = g.gene_id AND v.version = g.current_version WHERE g.gene_id = ?""",
            (gene_id,),
        ).fetchone()
        if row is None:
            raise KeyError(gene_id)
        return row
