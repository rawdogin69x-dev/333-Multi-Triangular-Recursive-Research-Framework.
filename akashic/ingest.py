"""Phase 1 pipeline: forage -> distill -> anchor -> embed -> judge -> store.

Supervised use: `akashic ingest <url|file>`. Every step that can be deterministic is; the model
only distills and judges, and both outputs are validated before anything is written.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from . import distill, judge
from .embed import Embedder
from .forage import Fetched, Forager
from .ids import now
from .lifecycle import State
from .llm import Gateway
from .search import vector_neighbours
from .store import Store, quote_hash


@dataclass
class IngestReport:
    source_id: str | None = None
    chunks: int = 0
    claims: int = 0
    dropped_malformed: int = 0
    rejected: dict[str, int] = field(default_factory=dict)
    tombstoned: int = 0
    merged: int = 0
    refined: int = 0
    contradicts: int = 0
    related: int = 0
    new: int = 0
    gene_ids: list[str] = field(default_factory=list)
    injection_flags: list[str] = field(default_factory=list)


@dataclass
class Pipeline:
    store: Store
    forager: Forager
    gateway: Gateway
    embedder: Embedder
    distill_provider: str = "local-day"
    judge_provider: str = "local-day"
    judge_floor: float = 0.80          # cosine; calibrate per embedder in Phase 2
    min_confidence_same: float = 0.75  # D14
    neighbours: int = 5
    max_claims_per_chunk: int = 8
    use_grammar: bool = True

    def ingest_url(self, url: str, charter_id: str | None = None) -> IngestReport:
        if self._url_tombstoned(url):
            return IngestReport(tombstoned=1)
        return self._ingest(self.forager.fetch(url), charter_id, lineage=None)

    def ingest_file(self, path: str, charter_id: str | None = None) -> IngestReport:
        f = self.forager.from_file(path)
        # Local files are separate sources; the owner can merge lineages later if two share an origin.
        return self._ingest(f, charter_id, lineage="file:" + f.sha256[:16])

    # -----------------------------------------------------------------------
    def _url_tombstoned(self, url: str) -> bool:
        from .forage import canonical_url

        row = self.store.conn.execute(
            "SELECT expires_at FROM tombstones WHERE key = ? AND kind = 'URL'", ("url:" + canonical_url(url),)
        ).fetchone()
        return bool(row and row[0] > now())

    def _claim_tombstoned(self, thesis: str) -> bool:
        row = self.store.conn.execute(
            "SELECT expires_at FROM tombstones WHERE key = ? AND kind = 'CLAIM'", ("claim:" + quote_hash(thesis),)
        ).fetchone()
        return bool(row and row[0] > now())

    def _ingest(self, f: Fetched, charter_id: str | None, lineage: str | None) -> IngestReport:
        rep = IngestReport(injection_flags=f.injection)
        ex = f.extracted
        rep.source_id = self.store.add_source(
            f.canonical, f.sha256, lineage_id=lineage, transparency=f.transparency, title=ex.title,
            authors=ex.authors, published_at=ex.published_at)
        model = self.gateway.providers[self.distill_provider].model
        for piece in distill.chunk(ex.text):
            rep.chunks += 1
            reply = self.gateway.call(
                self.distill_provider, "distiller",
                distill.build_messages(piece, self.max_claims_per_chunk, f.injection),
                json_mode=True, grammar=distill.gbnf() if self.use_grammar else None)
            claims, dropped = distill.parse(reply.text, self.max_claims_per_chunk)
            rep.dropped_malformed += dropped
            for c in claims:
                rep.claims += 1
                self._admit(c, ex.text, rep, f"agent:{model}", charter_id)
        return rep

    def _admit(self, c: distill.Claim, raw_text: str, rep: IngestReport, author: str,
               charter_id: str | None) -> None:
        if self._claim_tombstoned(c.thesis):
            rep.tombstoned += 1
            return
        st = self.store
        gid = st.add_candidate(taxonomy=c.taxonomy, frame=c.frame, thesis=c.thesis, reason=c.reason,
                               scope=c.scope, author=author, example=c.example, application=c.application,
                               nuance=c.phenomenon, charter_id=charter_id)
        st.attach_evidence(gid, rep.source_id, stance="FOR", evidence_type=c.evidence_type,
                           quote=c.quote, raw_text=raw_text)
        state = st.anchor_check(gid)
        if state == State.REJECTED:
            reason = st.conn.execute("SELECT reject_reason FROM genes WHERE gene_id = ?", (gid,)).fetchone()[0]
            rep.rejected[reason] = rep.rejected.get(reason, 0) + 1
            return
        vec = self.embedder.embed([f"{c.thesis}\nScope: {c.scope}"])[0]
        st.upsert_vector(gid, vec)
        if charter_id:
            st.link_charter(gid, charter_id, "BEARS_ON")
        outcome = self._judge_against_neighbours(gid, c, vec)
        setattr(rep, outcome, getattr(rep, outcome) + 1)
        if outcome in ("new", "related", "contradicts"):
            rep.gene_ids.append(gid)

    def _judge_against_neighbours(self, gid: str, c: distill.Claim, vec: list[float]) -> str:
        st = self.store
        outcome = "new"
        for other, cos in vector_neighbours(st.conn, vec, self.neighbours, exclude=gid):
            if cos < self.judge_floor:
                break
            o = st.conn.execute(
                """SELECT g.state, g.frame, v.thesis, v.scope, v.nuance FROM genes g JOIN gene_versions v
                   ON v.gene_id = g.gene_id AND v.version = g.current_version WHERE g.gene_id = ?""",
                (other,)).fetchone()
            if o is None or o["state"] in ("REJECTED", "SUPERSEDED"):
                continue
            if o["frame"] != c.frame:
                # Cross-frame resemblance is comparison, never corroboration.
                st.add_edge(gid, other, "PARALLELS", note=f"cosine {cos:.2f}")
                continue
            if judge.trivially_same(c.thesis, o["thesis"]):
                st.merge_into(gid, other, "identical thesis")
                return "merged"
            reply = self.gateway.call(
                self.judge_provider, "judge",
                judge.build_messages({"thesis": c.thesis, "scope": c.scope, "nuance": c.phenomenon,
                                      "frame": c.frame}, dict(o)), json_mode=True)
            j = judge.parse(reply.text, self.min_confidence_same)
            if j.verdict == "SAME":
                st.merge_into(gid, other, j.why)
                return "merged"
            if j.verdict == "REFINES":
                st.refine(gid, other, j.why)
                return "refined"
            if j.verdict == "CONTRADICTS":
                st.add_edge(gid, other, "CONTRADICTS", note=j.why)
                outcome = "contradicts"
            elif j.verdict == "RELATED":
                st.add_edge(gid, other, j.rel or "EXTENDS", note=j.why)
                if outcome == "new":
                    outcome = "related"
        return outcome
