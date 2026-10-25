"""Step 3 of admission: is it true? Evidence maths, the gravity rule and state transitions.

Pure functions only; akashic.store applies them to the database.

Model
-----
* Evidence rows are grouped into independent lineages. Within a lineage only the
  strongest row per stance counts (w * r), so ten copies of one press release count once.
  Independence must be shown, not presumed (D9): sources whose quotes share the same
  passage are merged into one lineage even when their declared lineages differ.
* support = 1 - prod(1 - w_i r_i) over lineages FOR; against likewise (noisy-OR).
* Four-valued state (catuskoti / Belnap-Dunn): SUPPORTED, REFUTED, CONTESTED, UNKNOWN.
* Gravity: in a topic with settled mass M, promotion needs
      k_req = min(k_cap, k_base + floor(log10(1 + M))) independent lineages and
      support >= tau = min(tau_max, tau0 + gamma * ln(1 + M)).
  Overturning an entrenched (CORROBORATED / AXIOM) gene needs k_req + 1 lineages against.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, replace
from enum import Enum

from .config import EvidenceWeights, GravityConfig


class State(str, Enum):
    CANDIDATE = "CANDIDATE"
    HYPOTHESIS = "HYPOTHESIS"
    CORROBORATED = "CORROBORATED"
    AXIOM = "AXIOM"
    CONTESTED = "CONTESTED"
    DERIVED = "DERIVED"
    REFUTED = "REFUTED"
    REJECTED = "REJECTED"
    SUPERSEDED = "SUPERSEDED"


class RejectReason(str, Enum):
    """Why a candidate never entered. Named after the Nyaya fallacies where one fits."""

    VIKALPA = "VIKALPA"                # no verbatim quote: words without a referent
    NUMBER_MISMATCH = "NUMBER_MISMATCH"  # thesis states numbers its quotes do not
    ASIDDHA = "ASIDDHA"                # rests on an unestablished premise
    VIRUDDHA = "VIRUDDHA"              # reason proves the opposite of the thesis
    SAVYABHICARA = "SAVYABHICARA"      # reason is inconclusive (holds for counter-cases too)
    OFF_CHARTER = "OFF_CHARTER"        # unrelated to any active research question
    SLOP = "SLOP"                      # boilerplate, marketing, or not a proposition


class Truth(str, Enum):
    SUPPORTED = "SUPPORTED"
    REFUTED = "REFUTED"
    CONTESTED = "CONTESTED"   # both
    UNKNOWN = "UNKNOWN"       # neither


ENTRENCHED = {State.CORROBORATED, State.AXIOM}
TERMINAL = {State.REJECTED, State.SUPERSEDED}
# Frames that are not truth claims about the world never rise above HYPOTHESIS.
CAPPED_FRAMES = {"SPECULATIVE", "METAPHOR"}
SHINGLE_WORDS = 8
SHARED_PASSAGE_JACCARD = 0.5


@dataclass(frozen=True)
class EvidenceRow:
    lineage_id: str
    stance: str            # 'FOR' | 'AGAINST'
    evidence_type: str
    reliability: float
    verified_quote: bool
    quote: str = ""


def _shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"\w+", text.casefold())
    if len(words) < SHINGLE_WORDS:
        return {tuple(words)} if words else set()
    return {tuple(words[i:i + SHINGLE_WORDS]) for i in range(len(words) - SHINGLE_WORDS + 1)}


def shared_passage(a: str, b: str) -> bool:
    """True when two quotes are substantially the same passage (copied or syndicated text)."""
    sa, sb = _shingles(a), _shingles(b)
    if not sa or not sb:
        return False
    return len(sa & sb) / len(sa | sb) >= SHARED_PASSAGE_JACCARD


def group_lineages(rows: list[EvidenceRow]) -> list[EvidenceRow]:
    """Union declared lineages that share a quoted passage; return rows relabelled by group (D9)."""
    parent: dict[str, str] = {r.lineage_id: r.lineage_id for r in rows}

    def find(x: str) -> str:
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x

    quoted = [r for r in rows if r.quote]
    for i, a in enumerate(quoted):
        for b in quoted[i + 1:]:
            if find(a.lineage_id) != find(b.lineage_id) and shared_passage(a.quote, b.quote):
                parent[find(b.lineage_id)] = find(a.lineage_id)
    return [replace(r, lineage_id=find(r.lineage_id)) for r in rows]


@dataclass(frozen=True)
class Assessment:
    support: float
    against: float
    lineages_for: int
    lineages_against: int


def assess(rows: list[EvidenceRow], weights: EvidenceWeights) -> Assessment:
    """Noisy-OR over independent lineages. Unverified quotes contribute nothing."""
    best: dict[tuple[str, str], float] = {}
    for r in group_lineages(rows):
        if not r.verified_quote:
            continue
        s = weights.of(r.evidence_type) * max(0.0, min(1.0, r.reliability))
        key = (r.stance, r.lineage_id)
        best[key] = max(best.get(key, 0.0), s)

    def noisy_or(stance: str) -> tuple[float, int]:
        vals = [v for (st, _), v in best.items() if st == stance and v > 0]
        return 1.0 - math.prod(1.0 - v for v in vals), len(vals)

    sup, n_for = noisy_or("FOR")
    ag, n_ag = noisy_or("AGAINST")
    return Assessment(sup, ag, n_for, n_ag)


def truth(a: Assessment, holds: float) -> Truth:
    s, g = a.support >= holds, a.against >= holds
    if s and g:
        return Truth.CONTESTED
    if s:
        return Truth.SUPPORTED
    if g:
        return Truth.REFUTED
    return Truth.UNKNOWN


def topic_of(taxonomy: str, depth: int) -> str:
    return ".".join(taxonomy.split(".")[:depth])


def tau(mass: float, g: GravityConfig) -> float:
    return min(g.tau_max, g.tau0 + g.gamma * math.log1p(max(0.0, mass)))


def k_required(mass: float, g: GravityConfig) -> int:
    return min(g.k_cap, g.k_base + int(math.floor(math.log10(1.0 + max(0.0, mass)))))


def next_state(
    current: State,
    frame: str,
    a: Assessment,
    topic_mass: float,
    g: GravityConfig,
    ever_promoted: bool = False,
    connected: bool = False,
) -> State:
    """Where the evidence puts a gene now. Never moves terminal or DERIVED genes (see derived_support).

    `ever_promoted` keeps the extra burden for overturning a once-settled gene even after
    it has slipped to CONTESTED, so it cannot be refuted on the cheaper path.
    `connected` is D1: promotion needs evidence AND a qualifying typed connection. An
    evidenced orphan waits in HYPOTHESIS (a percept not yet understood).
    """
    if current in TERMINAL or current == State.DERIVED:
        return current

    t, k = tau(topic_mass, g), k_required(topic_mass, g)
    k_against = k + 1 if (ever_promoted or current in ENTRENCHED) else k
    refuted = a.lineages_against >= k_against and a.against >= t and a.support < g.holds

    if current in ENTRENCHED:
        if refuted:
            return State.REFUTED
        if a.against >= g.holds:
            return State.CONTESTED
        return current

    if refuted:
        return State.REFUTED
    if truth(a, g.holds) == Truth.CONTESTED:
        return State.CONTESTED
    if ever_promoted and a.against >= g.holds:
        # A once-settled gene under strong but not yet sufficient attack stays visibly contested.
        return State.CONTESTED
    if (
        frame not in CAPPED_FRAMES
        and connected
        and a.lineages_for >= k
        and a.support >= t
        and a.against < g.holds
    ):
        return State.CORROBORATED
    return State.HYPOTHESIS


def source_reliability(transparency: float | None, hits: int = 0, resolved: int = 0,
                       prior_strength: float = 4.0) -> float:
    """D10: trust is earned by showing percepts (data, methods, code) and by predictions that came true.

    Agreement with the library is deliberately not an input. Base 0.3-0.7 from transparency,
    then a Beta-style blend toward the observed hit rate as resolved predictions accumulate.
    """
    base = 0.5 if transparency is None else 0.3 + 0.4 * max(0.0, min(1.0, transparency))
    return (hits + prior_strength * base) / (resolved + prior_strength)


def derived_support(premise_supports: list[float]) -> float:
    """A synthesis is only as strong as its weakest premise."""
    return min(premise_supports) if premise_supports else 0.0


def axiom_eligible(state: State, days_uncontested: int, centrality_pct: float) -> bool:
    """Librarian's promotion test: settled, load-bearing, and quiet for 90+ days."""
    return state == State.CORROBORATED and days_uncontested >= 90 and centrality_pct >= 0.95
