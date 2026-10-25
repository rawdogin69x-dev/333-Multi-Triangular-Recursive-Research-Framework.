import struct

import pytest

from akashic.config import Config
from akashic.db import connect, migrate
from akashic.lifecycle import State
from akashic.store import Store, root_domain

THESIS = "The widget reduces latency by 40% under sustained load"
RAW_A = "Lab A measured that the widget reduces latency by 40% under sustained load in their tests."
Q_A = "the widget reduces latency by 40% under sustained load"
RAW_B = "In our separate replication on different hardware, p99 latency fell 40% when load stayed high."
Q_B = "p99 latency fell 40% when load stayed high"
RAW_C = "A third team, using its own traces, found latency down 40% for long-running sustained traffic."
Q_C = "found latency down 40% for long-running sustained traffic"


@pytest.fixture
def store():
    cfg = Config(embed_dims=4)
    conn = connect(":memory:")
    assert migrate(conn, cfg) == 1
    assert migrate(conn, cfg) == 1  # idempotent
    return Store(conn, cfg)


def candidate(store, thesis=THESIS, frame="EMPIRICAL", taxonomy="eng.perf.widget"):
    return store.add_candidate(taxonomy=taxonomy, frame=frame, thesis=thesis,
                               reason="measured in benchmarks", scope="sustained load", author="agent:test")


def evidence(store, gid, uri, sha, quote, raw, stance="FOR", **src):
    s = store.add_source(uri, sha, **src)
    return store.attach_evidence(gid, s, stance=stance, evidence_type="OBSERVED", quote=quote, raw_text=raw)


def two_source_hypothesis(store):
    gid = candidate(store)
    evidence(store, gid, "https://a.org/p", "sha-a", Q_A, RAW_A)
    assert store.anchor_check(gid) == State.HYPOTHESIS
    evidence(store, gid, "https://b.net/q", "sha-b", Q_B, RAW_B)
    return gid


def test_root_domain():
    assert root_domain("https://docs.a.example.org/x") == "example.org"


def test_unanchored_claim_is_rejected_as_vikalpa(store):
    gid = candidate(store)
    assert evidence(store, gid, "https://a.org/p", "sha-a", "the widget makes everything much faster", RAW_A) is False
    assert store.anchor_check(gid) == State.REJECTED
    assert store.conn.execute("SELECT reject_reason FROM genes WHERE gene_id = ?", (gid,)).fetchone()[0] == "VIKALPA"
    assert store.conn.execute("SELECT COUNT(*) FROM tombstones").fetchone()[0] == 1


def test_invented_number_is_rejected(store):
    gid = candidate(store, thesis="The widget reduces latency by 60% under sustained load")
    evidence(store, gid, "https://a.org/p", "sha-a", Q_A, RAW_A)
    assert store.anchor_check(gid) == State.REJECTED


def test_evidenced_orphan_waits_then_connection_promotes(store):
    """D1: two independent sources are not enough on their own; a typed connection completes it."""
    gid = two_source_hypothesis(store)
    assert store.reassess(gid) == State.HYPOTHESIS
    assert store.conn.execute("SELECT unintegrated FROM genes WHERE gene_id = ?", (gid,)).fetchone()[0] == 1

    other = candidate(store, thesis="Sustained load is the dominant production traffic pattern")
    store.add_edge(gid, other, "EXTENDS")
    assert store._gene(gid)["state"] == State.CORROBORATED.value
    assert store.conn.execute("SELECT unintegrated FROM genes WHERE gene_id = ?", (gid,)).fetchone()[0] == 0
    kinds = [r[0] for r in store.conn.execute("SELECT kind FROM events WHERE gene_id = ?", (gid,))]
    assert kinds.count("STATE") == 2
    assert store.topic_mass("eng.perf.anything") > 0


def test_charter_answer_counts_as_connection(store):
    gid = two_source_hypothesis(store)
    cid = store.add_charter("How fast is the widget?")
    assert store.link_charter(gid, cid, "ANSWERS") == State.CORROBORATED


def test_parallels_and_metaphor_links_do_not_integrate(store):
    gid = two_source_hypothesis(store)
    meta = candidate(store, thesis="Latency is the friction of the machine", frame="METAPHOR")
    store.add_edge(gid, meta, "EXTENDS")
    other = candidate(store, thesis="Tradition X teaches that patience removes friction", frame="ATTRIBUTED")
    store.add_edge(gid, other, "PARALLELS")
    assert store._gene(gid)["state"] == State.HYPOTHESIS.value


def test_same_domain_twice_is_one_lineage(store):
    gid = candidate(store)
    evidence(store, gid, "https://sub0.a.org/p", "sha-0", Q_A, RAW_A)
    evidence(store, gid, "https://sub1.a.org/p", "sha-1", Q_B, RAW_B)
    assert store.anchor_check(gid) == State.HYPOTHESIS
    assert store._gene(gid)["lineages_for"] == 1


def test_syndicated_quote_across_domains_is_one_lineage(store):
    """D9: independence must be shown. The same passage on two domains is one lineage."""
    gid = candidate(store)
    evidence(store, gid, "https://a.org/p", "sha-a", Q_A, RAW_A)
    evidence(store, gid, "https://mirror.net/p", "sha-m", Q_A, "Repost: " + RAW_A)
    store.anchor_check(gid)
    assert store._gene(gid)["lineages_for"] == 1


def test_phenomenological_reports_count_by_practitioner(store):
    """D6: experience reports are corroborated across independent practitioners, not websites."""
    gid = candidate(store, thesis="Practitioners report a felt warmth in the hands during the exercise",
                    frame="PHENOMENOLOGICAL", taxonomy="exp.meditation.warmth")
    raw1 = "After twenty sessions I noticed a felt warmth in the hands during the exercise every time."
    raw2 = "Diary, week 3: a distinct warmth gathered in both hands while doing the breathing exercise."
    evidence(store, gid, "https://forum-a.org/1", "p1", "a felt warmth in the hands during the exercise", raw1,
             authors="Practitioner One")
    evidence(store, gid, "https://forum-b.org/2", "p2", "a distinct warmth gathered in both hands", raw2,
             authors="Practitioner One")
    store.anchor_check(gid)
    assert store._gene(gid)["lineages_for"] == 1  # same person on two sites


def test_resonance_is_stored_and_never_moves_state(store):
    gid = two_source_hypothesis(store)
    store.set_resonance(gid, 2)
    assert store.reassess(gid) == State.HYPOTHESIS
    with pytest.raises(ValueError):
        store.set_resonance(gid, 5)


def test_derived_gene_requires_rule_and_prediction_and_falls_with_premise(store):
    premise = candidate(store)
    evidence(store, premise, "https://a.org/p", "sha-a", Q_A, RAW_A)
    assert store.anchor_check(premise) == State.HYPOTHESIS
    with pytest.raises(ValueError):
        store.add_derived([premise], taxonomy="eng.perf.widget", frame="EMPIRICAL", thesis="t", reason="r",
                          rule="", prediction="", scope="s", author="agent:synth")
    d = store.add_derived([premise], taxonomy="eng.perf.widget", frame="EMPIRICAL",
                          thesis="Queues behind the widget stay shorter under sustained load",
                          reason="lower latency drains queues faster", rule="Little's law: L = lambda W",
                          prediction="Queue length metrics fall by a similar fraction", scope="sustained load",
                          author="agent:synth")
    g = store._gene(d)
    assert g["state"] == "DERIVED" and 0 < g["support"] <= store._gene(premise)["support"] + 1e-9
    assert store.conn.execute("SELECT COUNT(*) FROM tasks WHERE kind = 'TEST_PREDICTION'").fetchone()[0] == 1
    assert store.conn.execute("SELECT COUNT(*) FROM predictions WHERE gene_id = ?", (d,)).fetchone()[0] == 1

    # the premise is overturned by two independent lineages against it
    for i, (q, raw) in enumerate([
        ("the widget made no measurable difference to latency at all",
         "Audit 1: the widget made no measurable difference to latency at all in production."),
        ("we observed zero latency change with the widget enabled",
         "Audit 2 summary: we observed zero latency change with the widget enabled over a month."),
    ]):
        evidence(store, premise, f"https://audit{i}.org/r", f"aud-{i}", q, raw, stance="AGAINST")
    assert store.reassess(premise) == State.REFUTED
    recheck = store.conn.execute("SELECT payload_json FROM tasks WHERE kind = 'RECHECK'").fetchall()
    assert any(d in r[0] for r in recheck)
    assert store.reassess(d) == State.REFUTED


def test_strong_support_plus_strong_attack_is_contested_not_refuted(store):
    gid = two_source_hypothesis(store)
    store.link_charter(gid, store.add_charter("q"))
    for i, (q, raw) in enumerate([
        ("the widget made no measurable difference to latency at all",
         "Audit 1: the widget made no measurable difference to latency at all in production."),
        ("we observed zero latency change with the widget enabled",
         "Audit 2 summary: we observed zero latency change with the widget enabled over a month."),
        ("disabling the widget left tail latency exactly where it was",
         "Audit 3: disabling the widget left tail latency exactly where it was, within noise."),
    ]):
        evidence(store, gid, f"https://audit{i}.org/r", f"aud-{i}", q, raw, stance="AGAINST")
    assert store.reassess(gid) == State.CONTESTED


def test_resolved_prediction_updates_source_reliability(store):
    premise = two_source_hypothesis(store)
    d = store.add_derived([premise], taxonomy="eng.perf.widget", frame="EMPIRICAL", thesis="t2", reason="r",
                          rule="rule", prediction="something checkable", scope="s", author="agent:synth")
    pid = store.conn.execute("SELECT prediction_id FROM predictions WHERE gene_id = ?", (d,)).fetchone()[0]
    before = store.conn.execute("SELECT reliability FROM sources").fetchall()
    store.resolve_prediction(pid, "MISS")
    # the derived gene has no FOR evidence of its own, so no source is debited
    assert store.conn.execute("SELECT reliability FROM sources").fetchall() == before


def test_vector_and_fts_round_trip(store):
    gid = candidate(store)
    store.upsert_vector(gid, [1.0, 0.0, 0.0, 0.0])
    hit = store.conn.execute(
        "SELECT gene_id, distance FROM gene_vec WHERE embedding MATCH ? AND k = 1",
        (struct.pack("4f", 1.0, 0.0, 0.0, 0.0),),
    ).fetchone()
    assert hit["gene_id"] == gid and hit["distance"] < 1e-6
    fts = store.conn.execute(
        "SELECT m.gene_id FROM gene_fts f JOIN gene_fts_map m ON m.rowid = f.rowid WHERE gene_fts MATCH 'latency'"
    ).fetchall()
    assert [r[0] for r in fts] == [gid]
