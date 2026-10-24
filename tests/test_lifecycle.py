import math

from akashic.config import EvidenceWeights, GravityConfig
from akashic.lifecycle import (
    Assessment,
    EvidenceRow,
    State,
    Truth,
    assess,
    derived_support,
    k_required,
    next_state,
    tau,
    truth,
)

G = GravityConfig()
W = EvidenceWeights()


def row(lineage, stance="FOR", kind="OBSERVED", r=0.8, ok=True):
    return EvidenceRow(lineage, stance, kind, r, ok)


def test_same_lineage_counts_once():
    a = assess([row("a.org"), row("a.org"), row("a.org")], W)
    assert a.lineages_for == 1
    assert math.isclose(a.support, 0.85 * 0.8)


def test_independent_lineages_compound():
    a = assess([row("a.org"), row("b.org")], W)
    assert a.lineages_for == 2
    assert math.isclose(a.support, 1 - (1 - 0.68) ** 2)


def test_unverified_quotes_count_for_nothing():
    a = assess([row("a.org", ok=False)], W)
    assert a.support == 0 and a.lineages_for == 0


def test_gravity_rises_with_mass():
    assert [k_required(m, G) for m in (0, 9, 99, 999, 10**6)] == [2, 3, 4, 4, 4]
    assert tau(0, G) == G.tau0
    assert tau(100, G) > tau(10, G) > tau(0, G)
    assert tau(1e300, G) == G.tau_max


def test_cold_start_admits_with_two_independent_sources():
    """Argon's gate could never admit the first gene. This one can."""
    a = assess([row("a.org"), row("b.org")], W)
    assert next_state(State.HYPOTHESIS, "EMPIRICAL", a, 0.0, G) == State.CORROBORATED


def test_one_source_stays_hypothesis():
    a = assess([row("a.org", r=1.0, kind="EXECUTED")], W)
    assert next_state(State.HYPOTHESIS, "EMPIRICAL", a, 0.0, G) == State.HYPOTHESIS


def test_dense_topic_needs_more_lineages():
    a = assess([row("a.org"), row("b.org")], W)
    assert next_state(State.HYPOTHESIS, "EMPIRICAL", a, 50.0, G) == State.HYPOTHESIS
    a3 = assess([row("a.org"), row("b.org"), row("c.org")], W)
    assert next_state(State.HYPOTHESIS, "EMPIRICAL", a3, 50.0, G) == State.CORROBORATED


def test_metaphor_and_speculative_never_corroborate():
    a = assess([row(x) for x in "abcd"], W)
    for frame in ("METAPHOR", "SPECULATIVE"):
        assert next_state(State.HYPOTHESIS, frame, a, 0.0, G) == State.HYPOTHESIS
    assert next_state(State.HYPOTHESIS, "ATTRIBUTED", a, 0.0, G) == State.CORROBORATED


def test_both_sides_strong_is_contested():
    a = assess([row("a.org"), row("b.org"), row("c.org", "AGAINST"), row("d.org", "AGAINST")], W)
    assert truth(a, G.holds) == Truth.CONTESTED
    assert next_state(State.HYPOTHESIS, "EMPIRICAL", a, 0.0, G) == State.CONTESTED


def test_entrenched_gene_needs_extra_lineage_to_fall():
    against2 = Assessment(support=0.2, against=0.9, lineages_for=1, lineages_against=2)
    against3 = Assessment(support=0.2, against=0.9, lineages_for=1, lineages_against=3)
    assert next_state(State.CORROBORATED, "EMPIRICAL", against2, 0.0, G) == State.CONTESTED
    assert next_state(State.CORROBORATED, "EMPIRICAL", against3, 0.0, G) == State.REFUTED
    # once contested, it still cannot be refuted on the cheaper path
    assert next_state(State.CONTESTED, "EMPIRICAL", against2, 0.0, G, ever_promoted=True) == State.CONTESTED
    assert next_state(State.CONTESTED, "EMPIRICAL", against2, 0.0, G, ever_promoted=False) == State.REFUTED


def test_terminal_and_derived_states_do_not_move():
    a = assess([row(x) for x in "abcd"], W)
    for s in (State.REJECTED, State.SUPERSEDED, State.DERIVED):
        assert next_state(s, "EMPIRICAL", a, 0.0, G) == s


def test_derived_is_capped_by_weakest_premise():
    assert derived_support([0.9, 0.4, 0.8]) == 0.4
    assert derived_support([]) == 0.0
