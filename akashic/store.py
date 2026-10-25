"""The Arbiter's write API. Only this module writes knowledge tables; every change is an event."""

from __future__ import annotations

import hashlib
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
    derived_support,
    k_required,
    next_state,
    source_reliability,
    tau,
    topic_of,
)

FRAMES = {"EMPIRICAL", "FORMAL", "ATTRIBUTED", "SPECULATIVE", "METAPHOR", "PHENOMENOLOGICAL"}
# Edges along which a change in dst must trigger a re-check of src (truth maintenance).
DEPENDENCY_RELS = ("DEPENDS_ON", "DERIVED_FROM")
FALLEN = (State.REFUTED.value, State.REJECTED.value)


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

    Only the fallback lineage (D9). Known weakness: wrong for 'co.uk'-style suffixes.
    """
    host = (urlsplit(uri).hostname or uri).lower()
    parts = host.split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else host


def quote_hash(quote: str) -> str:
    return hashlib.sha256(anchor.normalise(quote).encode("utf-8")).hexdigest()


class Store:
    def __init__(self, conn: sqlite3.Connection, cfg: Config, actor: str = "arbiter"):
        self.conn, self.cfg, self.actor = conn, cfg, actor

    # -- events -------------------------------------------------------------
    def _event(self, kind: str, gene_id: str | None, before=None, after=None) -> None:
        self.conn.execute(
            "INSERT INTO events(event_id, gene_id, kind, before, after, actor, at) VALUES (?,?,?,?,?,?,?)",
            (uuid7(), gene_id, kind, json.dumps(before), json.dumps(after), self.actor, now()),
        )

    def _task(self, kind: str, payload: dict, priority: int = 3, charter_id: str | None = None) -> str:
        tid = uuid7()
        self.conn.execute(
            "INSERT INTO tasks(task_id, kind, payload_json, priority, charter_id, created_at) VALUES (?,?,?,?,?,?)",
            (tid, kind, json.dumps(payload), priority, charter_id, now()),
        )
        return tid

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

    def link_charter(self, gene_id: str, charter_id: str, rel: str = "ANSWERS") -> State:
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO charter_links(gene_id, charter_id, rel, created_at) VALUES (?,?,?,?)
                   ON CONFLICT DO NOTHING""",
                (gene_id, charter_id, rel, now()),
            )
        return self.reassess(gene_id)

    # -- sources ------------------------------------------------------------
    def add_source(self, uri: str, blob_sha256: str, *, lineage_id: str | None = None,
                   transparency: float | None = None, title: str | None = None,
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
                       captured_at, blob_sha256, lineage_id, reliability, transparency, license)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (sid, uri, uri, dom, title, authors, published_at, now(), blob_sha256,
                 lineage_id or dom, source_reliability(transparency), transparency, license),
            )
        return sid

    # -- genes --------------------------------------------------------------
    def add_candidate(self, *, taxonomy: str, frame: str, thesis: str, reason: str, scope: str,
                      author: str, example: str | None = None, application: str | None = None,
                      nuance: str | None = None, rule: str | None = None, prediction: str | None = None,
                      valid_from: str | None = None, valid_until: str | None = None,
                      charter_id: str | None = None, state: State = State.CANDIDATE) -> str:
        if frame not in FRAMES:
            raise ValueError(f"frame must be one of {sorted(FRAMES)}")
        gid, ts = uuid7(), now()
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO genes(gene_id, taxonomy, frame, state, charter_id, created_at, updated_at)
                   VALUES (?,?,?,?,?,?,?)""",
                (gid, taxonomy, frame, state.value, charter_id, ts, ts),
            )
            self.conn.execute(
                """INSERT INTO gene_versions(gene_id, version, thesis, reason, example, application, scope,
                       nuance, rule, prediction, valid_from, valid_until, author, created_at)
                   VALUES (?,1,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (gid, thesis, reason, example, application, scope, nuance, rule, prediction,
                 valid_from, valid_until, author, ts),
            )
            cur = self.conn.execute("INSERT INTO gene_fts_map(gene_id) VALUES (?)", (gid,))
            self.conn.execute(
                "INSERT INTO gene_fts(rowid, thesis, reason, nuance, scope) VALUES (?,?,?,?,?)",
                (cur.lastrowid, thesis, reason, nuance or "", scope),
            )
            self._event(state.value, gid, after={"thesis": thesis, "frame": frame, "author": author})
        return gid

    def add_derived(self, premise_ids: list[str], *, taxonomy: str, frame: str, thesis: str, reason: str,
                    rule: str, prediction: str, scope: str, author: str) -> str:
        """D11: a synthesis must name the rule it relies on and one novel, checkable consequence."""
        if not premise_ids:
            raise ValueError("a DERIVED gene needs premises")
        if not (rule or "").strip() or not (prediction or "").strip():
            raise ValueError("a DERIVED gene must state its rule (vyapti) and a checkable prediction")
        gid = self.add_candidate(taxonomy=taxonomy, frame=frame, thesis=thesis, reason=reason, scope=scope,
                                 author=author, rule=rule, prediction=prediction, state=State.DERIVED)
        with tx(self.conn):
            for p in premise_ids:
                self.conn.execute(
                    """INSERT INTO edges(edge_id, src, dst, rel, created_by, created_at)
                       VALUES (?,?,?,?,?,?) ON CONFLICT(src, dst, rel) DO NOTHING""",
                    (uuid7(), gid, p, "DERIVED_FROM", self.actor, now()),
                )
            sup = self._derived_premise_support(gid)
            self.conn.execute(
                """INSERT INTO predictions(prediction_id, gene_id, statement, support_at_making, made_at)
                   VALUES (?,?,?,?,?)""",
                (uuid7(), gid, prediction, sup, now()),
            )
            self._task("TEST_PREDICTION", {"gene_id": gid, "prediction": prediction}, priority=2)
        self.reassess(gid)
        return gid

    def set_resonance(self, gene_id: str, value: int) -> None:
        """D5: the owner's felt sense. Stored apart; the gate never reads it."""
        if not -2 <= value <= 2:
            raise ValueError("resonance is -2..2")
        with tx(self.conn):
            self.conn.execute("UPDATE genes SET resonance = ? WHERE gene_id = ?", (value, gene_id))
            self._event("RESONANCE", gene_id, after=value)

    def attach_evidence(self, gene_id: str, source_id: str, *, stance: str, evidence_type: str,
                        quote: str, raw_text: str) -> bool:
        """Record evidence; the quote is verified against the raw source text here, not trusted."""
        offset = anchor.find_quote(quote, raw_text)
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO evidence(evidence_id, gene_id, source_id, stance, evidence_type, quote,
                       quote_offset, quote_sha256, verified_quote, added_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?)
                   ON CONFLICT(gene_id, source_id, stance) DO NOTHING""",
                (uuid7(), gene_id, source_id, stance, evidence_type, quote, offset, quote_hash(quote),
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
        # A new connection can integrate either end (D1).
        for gid in (src, dst):
            self.reassess(gid)

    def upsert_vector(self, gene_id: str, embedding: list[float]) -> None:
        g = self.conn.execute("SELECT frame, taxonomy FROM genes WHERE gene_id = ?", (gene_id,)).fetchone()
        with tx(self.conn):
            self.conn.execute("DELETE FROM gene_vec WHERE gene_id = ?", (gene_id,))
            self.conn.execute(
                "INSERT INTO gene_vec(gene_id, embedding, frame, topic) VALUES (?,?,?,?)",
                (gene_id, sqlite_vec.serialize_float32(embedding), g["frame"],
                 topic_of(g["taxonomy"], self.cfg.gravity.topic_depth)),
            )

    def merge_into(self, duplicate_id: str, target_id: str, why: str = "SAME") -> State:
        """Judge said SAME: the duplicate's evidence becomes corroboration of the target."""
        with tx(self.conn):
            self.conn.execute("UPDATE OR IGNORE evidence SET gene_id = ? WHERE gene_id = ?", (target_id, duplicate_id))
            self.conn.execute("UPDATE genes SET state = 'SUPERSEDED', updated_at = ? WHERE gene_id = ?",
                              (now(), duplicate_id))
            self._event("MERGED", duplicate_id, after={"into": target_id, "why": why})
        return self.reassess(target_id)

    def refine(self, candidate_id: str, target_id: str, why: str = "REFINES") -> State:
        """Judge said REFINES: the candidate's content becomes the target's next version (old versions stay)."""
        v = self.conn.execute(
            """SELECT v.* FROM gene_versions v JOIN genes g ON g.gene_id = v.gene_id
               AND v.version = g.current_version WHERE g.gene_id = ?""", (candidate_id,)).fetchone()
        cur_v = self.conn.execute(
            """SELECT v.* FROM gene_versions v JOIN genes g ON g.gene_id = v.gene_id
               AND v.version = g.current_version WHERE g.gene_id = ?""", (target_id,)).fetchone()
        nxt = cur_v["version"] + 1
        with tx(self.conn):
            self.conn.execute(
                """INSERT INTO gene_versions(gene_id, version, thesis, reason, example, application, scope, nuance,
                       rule, prediction, valid_from, valid_until, author, created_at)
                   VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (target_id, nxt, v["thesis"], v["reason"], v["example"], v["application"], v["scope"], v["nuance"],
                 v["rule"], v["prediction"], v["valid_from"], v["valid_until"], v["author"], now()),
            )
            self.conn.execute("UPDATE genes SET current_version = ?, updated_at = ? WHERE gene_id = ?",
                              (nxt, now(), target_id))
            # Contentless FTS5: delete needs the indexed values, which the old version still holds.
            rowid = self.conn.execute("SELECT rowid FROM gene_fts_map WHERE gene_id = ?", (target_id,)).fetchone()[0]
            self.conn.execute(
                "INSERT INTO gene_fts(gene_fts, rowid, thesis, reason, nuance, scope) VALUES ('delete', ?, ?, ?, ?, ?)",
                (rowid, cur_v["thesis"], cur_v["reason"], cur_v["nuance"] or "", cur_v["scope"]))
            self.conn.execute(
                "INSERT INTO gene_fts(rowid, thesis, reason, nuance, scope) VALUES (?, ?, ?, ?, ?)",
                (rowid, v["thesis"], v["reason"], v["nuance"] or "", v["scope"]))
            self.conn.execute("UPDATE OR IGNORE evidence SET gene_id = ? WHERE gene_id = ?", (target_id, candidate_id))
            self.conn.execute("UPDATE genes SET state = 'SUPERSEDED', updated_at = ? WHERE gene_id = ?",
                              (now(), candidate_id))
            self._event("REFINED", target_id, before=nxt - 1, after={"version": nxt, "from": candidate_id, "why": why})
        return self.reassess(target_id)

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
        key = "claim:" + quote_hash(g["thesis"])
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

    def is_connected(self, gene_id: str) -> bool:
        """D1: a typed edge to a live, non-METAPHOR gene, or an ANSWERS link to a charter.

        PARALLELS edges do not count: cross-frame parallels are for comparison, not integration.
        """
        q = """
            SELECT 1 FROM edges e
            JOIN genes o ON o.gene_id = CASE WHEN e.src = :g THEN e.dst ELSE e.src END
            WHERE (e.src = :g OR e.dst = :g)
              AND e.rel != 'PARALLELS'
              AND o.frame != 'METAPHOR' AND o.state NOT IN ('REJECTED', 'SUPERSEDED')
            LIMIT 1"""
        if self.conn.execute(q, {"g": gene_id}).fetchone():
            return True
        return self.conn.execute(
            "SELECT 1 FROM charter_links WHERE gene_id = ? AND rel = 'ANSWERS' LIMIT 1", (gene_id,)
        ).fetchone() is not None

    def topic_mass(self, taxonomy: str) -> float:
        topic = topic_of(taxonomy, self.cfg.gravity.topic_depth)
        row = self.conn.execute(
            """SELECT COALESCE(SUM(support), 0) FROM genes
               WHERE state IN ('CORROBORATED', 'AXIOM') AND (taxonomy = ? OR taxonomy LIKE ? ESCAPE '\\')""",
            (topic, topic.replace("%", r"\%").replace("_", r"\_") + ".%"),
        ).fetchone()
        return float(row[0])

    def _evidence_rows(self, gene_id: str, frame: str) -> list[EvidenceRow]:
        rows = []
        for r in self.conn.execute(
            """SELECT s.lineage_id, s.authors, e.stance, e.evidence_type, s.reliability, e.verified_quote, e.quote
               FROM evidence e JOIN sources s USING(source_id) WHERE e.gene_id = ?""",
            (gene_id,),
        ):
            lineage = r["lineage_id"]
            # D6: experience reports are corroborated across independent practitioners.
            if frame == "PHENOMENOLOGICAL" and r["authors"]:
                lineage = "practitioner:" + r["authors"].strip().casefold()
            rows.append(EvidenceRow(lineage, r["stance"], r["evidence_type"], r["reliability"],
                                    bool(r["verified_quote"]), r["quote"]))
        return rows

    def _derived_premise_support(self, gene_id: str) -> float:
        sups = [r[0] for r in self.conn.execute(
            """SELECT CASE WHEN g.state IN ('REFUTED','REJECTED') THEN 0 ELSE g.support END
               FROM edges e JOIN genes g ON g.gene_id = e.dst WHERE e.src = ? AND e.rel = 'DERIVED_FROM'""",
            (gene_id,))]
        return derived_support(sups)

    def reassess(self, gene_id: str) -> State:
        """Step 3: recompute evidence and move the gene to where the gravity rule puts it."""
        g = self._gene(gene_id)
        current = State(g["state"])
        if current == State.CANDIDATE:
            return current
        a = assess(self._evidence_rows(gene_id, g["frame"]), self.cfg.weights)
        connected = self.is_connected(gene_id)

        if current == State.DERIVED:
            return self._reassess_derived(gene_id, g, a, connected)

        mass = self.topic_mass(g["taxonomy"])
        # A gene's own support must not raise the bar it is being judged against.
        if current.value in ("CORROBORATED", "AXIOM"):
            mass = max(0.0, mass - g["support"])
        new = next_state(current, g["frame"], a, mass, self.cfg.gravity,
                         ever_promoted=g["tau_at_promotion"] is not None, connected=connected)
        self._set_state(gene_id, current, new, a, connected=connected,
                        tau_promo=tau(mass, self.cfg.gravity) if new == State.CORROBORATED and current != new else None)
        return new

    def _reassess_derived(self, gene_id: str, g: sqlite3.Row, own: Assessment, connected: bool) -> State:
        """A synthesis stands on its premises; a confirmed prediction adds independent support (D11)."""
        premise_dead = self.conn.execute(
            f"""SELECT 1 FROM edges e JOIN genes p ON p.gene_id = e.dst
                WHERE e.src = ? AND e.rel = 'DERIVED_FROM' AND p.state IN ({','.join('?' * len(FALLEN))}) LIMIT 1""",
            (gene_id, *FALLEN),
        ).fetchone()
        chain = self._derived_premise_support(gene_id)
        support = 1.0 - (1.0 - chain) * (1.0 - own.support)
        a = Assessment(support, own.against, own.lineages_for, own.lineages_against)
        new = State.DERIVED
        if premise_dead or (own.against >= self.cfg.gravity.holds and own.against > support):
            new = State.REFUTED
        self._set_state(gene_id, State.DERIVED, new, a, connected=connected)
        return new

    def gravity_view(self, taxonomy: str) -> dict:
        m = self.topic_mass(taxonomy)
        return {"topic": topic_of(taxonomy, self.cfg.gravity.topic_depth), "mass": m,
                "tau": tau(m, self.cfg.gravity), "k_required": k_required(m, self.cfg.gravity)}

    # -- calibration ledger (R5, D10) -----------------------------------------
    def resolve_prediction(self, prediction_id: str, outcome: str) -> None:
        """Record HIT / MISS / VOID and credit or debit every source that supported the gene."""
        if outcome not in ("HIT", "MISS", "VOID"):
            raise ValueError(outcome)
        p = self.conn.execute("SELECT gene_id FROM predictions WHERE prediction_id = ?", (prediction_id,)).fetchone()
        if p is None:
            raise KeyError(prediction_id)
        with tx(self.conn):
            self.conn.execute(
                "UPDATE predictions SET outcome = ?, resolved_at = ? WHERE prediction_id = ?",
                (outcome, now(), prediction_id),
            )
            self._event("PREDICTION_RESOLVED", p["gene_id"], after=outcome)
            if outcome == "VOID":
                return
            src_ids = [r[0] for r in self.conn.execute(
                "SELECT DISTINCT source_id FROM evidence WHERE gene_id = ? AND stance = 'FOR'", (p["gene_id"],))]
            for sid in src_ids:
                self.conn.execute(
                    "UPDATE sources SET pred_resolved = pred_resolved + 1, pred_hits = pred_hits + ? WHERE source_id = ?",
                    (int(outcome == "HIT"), sid),
                )
                s = self.conn.execute(
                    "SELECT transparency, pred_hits, pred_resolved FROM sources WHERE source_id = ?", (sid,)
                ).fetchone()
                self.conn.execute(
                    "UPDATE sources SET reliability = ? WHERE source_id = ?",
                    (source_reliability(s["transparency"], s["pred_hits"], s["pred_resolved"]), sid),
                )
                for (gid,) in self.conn.execute("SELECT DISTINCT gene_id FROM evidence WHERE source_id = ?", (sid,)):
                    self._task("RECHECK", {"gene_id": gid, "because": f"reliability:{sid}"}, priority=3)

    # -- truth maintenance --------------------------------------------------
    def dependants(self, gene_id: str) -> list[str]:
        q = f"SELECT src FROM edges WHERE dst = ? AND rel IN ({','.join('?' * len(DEPENDENCY_RELS))})"
        return [r[0] for r in self.conn.execute(q, (gene_id, *DEPENDENCY_RELS))]

    def _set_state(self, gene_id: str, before: State, after: State, a: Assessment,
                   tau_promo: float | None = None, connected: bool | None = None) -> None:
        with tx(self.conn):
            self.conn.execute(
                """UPDATE genes SET state = ?, support = ?, against = ?, lineages_for = ?, lineages_against = ?,
                       tau_at_promotion = COALESCE(?, tau_at_promotion),
                       unintegrated = COALESCE(?, unintegrated), updated_at = ? WHERE gene_id = ?""",
                (after.value, a.support, a.against, a.lineages_for, a.lineages_against, tau_promo,
                 None if connected is None else int(not connected), now(), gene_id),
            )
            if before != after:
                self._event("STATE", gene_id, before=before.value, after=after.value)
                for dep in self.dependants(gene_id):
                    self._task("RECHECK", {"gene_id": dep, "because": gene_id}, priority=2)

    def _gene(self, gene_id: str) -> sqlite3.Row:
        row = self.conn.execute(
            """SELECT g.*, v.thesis FROM genes g JOIN gene_versions v
               ON v.gene_id = g.gene_id AND v.version = g.current_version WHERE g.gene_id = ?""",
            (gene_id,),
        ).fetchone()
        if row is None:
            raise KeyError(gene_id)
        return row
