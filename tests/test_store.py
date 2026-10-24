import pytest

from akashic.config import Config
from akashic.db import connect, migrate
from akashic.lifecycle import State
from akashic.store import Store, root_domain

RAW_A = "Lab A measured that the widget reduces latency by 40% under sustained load in their tests."
RAW_B = "Independent replication: the widget reduces latency by 40% under sustained load, confirmed."


@pytest.fixture
def store():
    cfg = Config(embed_dims=4)
    conn = connect(":memory:")
    assert migrate(conn, cfg) == 1
    assert migrate(conn, cfg) == 1  # idempotent
    return Store(conn, cfg)


def candidate(store, thesis="The widget reduces latency by 40% under sustained load"):
    return store.add_candidate(
        taxonomy="eng.perf.widget", frame="EMPIRICAL", thesis=thesis,
        reason="measured in benchmarks", scope="sustained load", author="agent:test",
    )


def test_root_domain():
    assert root_domain("https://docs.a.example.org/x") == "example.org"


def test_unanchored_claim_is_rejected_as_vikalpa(store):
    gid = candidate(store)
    src = store.add_source("https://a.org/p", "sha-a")
    assert store.attach_evidence(gid, src, stance="FOR", evidence_type="OBSERVED",
                                 quote="the widget makes everything much faster", raw_text=RAW_A) is False
    assert store.anchor_check(gid) == State.REJECTED
    row = store.conn.execute("SELECT reject_reason FROM genes WHERE gene_id = ?", (gid,)).fetchone()
    assert row[0] == "VIKALPA"
    assert store.conn.execute("SELECT COUNT(*) FROM tombstones").fetchone()[0] == 1


def test_invented_number_is_rejected(store):
    gid = candidate(store, thesis="The widget reduces latency by 60% under sustained load")
    src = store.add_source("https://a.org/p", "sha-a")
    store.attach_evidence(gid, src, stance="FOR", evidence_type="OBSERVED",
                          quote="the widget reduces latency by 40% under sustained load", raw_text=RAW_A)
    assert store.anchor_check(gid) == State.REJECTED


def test_two_independent_sources_corroborate_and_events_are_logged(store):
    gid = candidate(store)
    a = store.add_source("https://a.org/p", "sha-a")
    store.attach_evidence(gid, a, stance="FOR", evidence_type="OBSERVED",
                          quote="the widget reduces latency by 40% under sustained load", raw_text=RAW_A)
    assert store.anchor_check(gid) == State.HYPOTHESIS

    b = store.add_source("https://b.net/q", "sha-b")
    store.attach_evidence(gid, b, stance="FOR", evidence_type="OBSERVED",
                          quote="the widget reduces latency by 40% under sustained load", raw_text=RAW_B)
    assert store.reassess(gid) == State.CORROBORATED
    kinds = [r[0] for r in store.conn.execute("SELECT kind FROM events WHERE gene_id = ? ORDER BY at", (gid,))]
    assert kinds.count("STATE") == 2
    assert store.topic_mass("eng.perf.anything") > 0


def test_same_domain_twice_is_one_lineage(store):
    gid = candidate(store)
    for i, raw in enumerate((RAW_A, RAW_B)):
        s = store.add_source(f"https://sub{i}.a.org/p", f"sha-{i}")
        store.attach_evidence(gid, s, stance="FOR", evidence_type="OBSERVED",
                              quote="the widget reduces latency by 40% under sustained load", raw_text=raw)
    assert store.anchor_check(gid) == State.HYPOTHESIS


def test_state_change_queues_recheck_of_dependants(store):
    premise = candidate(store)
    child = candidate(store, thesis="Therefore queue depth stays bounded")
    store.add_edge(child, premise, "DEPENDS_ON")
    a = store.add_source("https://a.org/p", "sha-a")
    store.attach_evidence(premise, a, stance="FOR", evidence_type="OBSERVED",
                          quote="the widget reduces latency by 40% under sustained load", raw_text=RAW_A)
    store.anchor_check(premise)
    tasks = store.conn.execute("SELECT kind, payload_json FROM tasks").fetchall()
    assert tasks and tasks[0]["kind"] == "RECHECK" and child in tasks[0]["payload_json"]


def test_vector_and_fts_round_trip(store):
    gid = candidate(store)
    store.upsert_vector(gid, [1.0, 0.0, 0.0, 0.0])
    hit = store.conn.execute(
        "SELECT gene_id, distance FROM gene_vec WHERE embedding MATCH ? AND k = 1",
        (b"".join(__import__("struct").pack("f", x) for x in (1.0, 0.0, 0.0, 0.0)),),
    ).fetchone()
    assert hit["gene_id"] == gid and hit["distance"] < 1e-6
    fts = store.conn.execute(
        "SELECT m.gene_id FROM gene_fts f JOIN gene_fts_map m ON m.rowid = f.rowid WHERE gene_fts MATCH 'latency'"
    ).fetchall()
    assert [r[0] for r in fts] == [gid]
