-- Akashic core schema v1 (amended before first release to carry decisions D1-D14, docs/DECISIONS.md).
-- Nothing is hard-deleted; states and versions carry history.
-- All timestamps are ISO-8601 UTC strings. Vector + FTS tables are created in db.py
-- because their shape depends on config (embedding dims).

-- Research agenda: the human steering wheel.
CREATE TABLE charters (
    charter_id  TEXT PRIMARY KEY,
    question    TEXT NOT NULL,
    scope       TEXT,
    priority    INTEGER NOT NULL DEFAULT 3 CHECK (priority BETWEEN 1 AND 5),
    done_when   TEXT,
    status      TEXT NOT NULL DEFAULT 'ACTIVE' CHECK (status IN ('ACTIVE', 'PAUSED', 'DONE')),
    created_at  TEXT NOT NULL
);

-- Stable identity. Content lives in gene_versions; evidence maths is cached here.
CREATE TABLE genes (
    gene_id          TEXT PRIMARY KEY,                -- UUIDv7, time-ordered
    current_version  INTEGER NOT NULL DEFAULT 1,
    taxonomy         TEXT NOT NULL,                   -- dotted, e.g. 'sci.ml.rag.dedup'
    frame            TEXT NOT NULL CHECK (frame IN (
                        'EMPIRICAL', 'FORMAL', 'ATTRIBUTED', 'SPECULATIVE', 'METAPHOR', 'PHENOMENOLOGICAL')),
    state            TEXT NOT NULL DEFAULT 'CANDIDATE' CHECK (state IN (
                        'CANDIDATE', 'HYPOTHESIS', 'CORROBORATED', 'AXIOM', 'CONTESTED',
                        'DERIVED', 'REFUTED', 'REJECTED', 'SUPERSEDED')),
    reject_reason    TEXT,                            -- see akashic.lifecycle.RejectReason
    support          REAL NOT NULL DEFAULT 0,
    against          REAL NOT NULL DEFAULT 0,
    lineages_for     INTEGER NOT NULL DEFAULT 0,
    lineages_against INTEGER NOT NULL DEFAULT 0,
    tau_at_promotion REAL,
    forage_cycles    INTEGER NOT NULL DEFAULT 0,
    stalled          INTEGER NOT NULL DEFAULT 0,
    unintegrated     INTEGER NOT NULL DEFAULT 1,      -- D1: no qualifying typed connection yet
    resonance        INTEGER CHECK (resonance BETWEEN -2 AND 2), -- D5: owner's mark; priority only, never read by the gate
    charter_id       TEXT REFERENCES charters(charter_id),
    created_at       TEXT NOT NULL,
    updated_at       TEXT NOT NULL
);
CREATE INDEX genes_state ON genes(state);
CREATE INDEX genes_taxonomy ON genes(taxonomy);

-- The five-member template (Nyaya pancavayava) plus scope (syadvada) and validity dates.
CREATE TABLE gene_versions (
    gene_id      TEXT NOT NULL REFERENCES genes(gene_id),
    version      INTEGER NOT NULL,
    thesis       TEXT NOT NULL,   -- pratijna: one proposition
    reason       TEXT NOT NULL,   -- hetu: why it holds
    example      TEXT,            -- udaharana: a concrete case (NULL = none known, flagged)
    application  TEXT,            -- upanaya: how to use it
    scope        TEXT NOT NULL,   -- conditions, population, version, date range
    nuance       TEXT,
    rule         TEXT,            -- vyapti: the general rule a DERIVED gene relies on
    prediction   TEXT,            -- D11: a novel, checkable consequence (required for DERIVED)
    valid_from   TEXT,
    valid_until  TEXT,
    author       TEXT NOT NULL,   -- 'agent:<model>' or 'human'
    created_at   TEXT NOT NULL,
    PRIMARY KEY (gene_id, version)
);

CREATE TABLE sources (
    source_id     TEXT PRIMARY KEY,
    uri           TEXT,
    canonical_uri TEXT,
    root_domain   TEXT,
    title         TEXT,
    authors       TEXT,
    published_at  TEXT,
    captured_at   TEXT NOT NULL,
    blob_sha256   TEXT NOT NULL,
    lineage_id    TEXT NOT NULL,   -- sources sharing a lineage count once
    reliability   REAL NOT NULL DEFAULT 0.5 CHECK (reliability BETWEEN 0 AND 1),
    transparency  REAL CHECK (transparency BETWEEN 0 AND 1), -- D10: shows data / methods / code
    pred_hits     INTEGER NOT NULL DEFAULT 0,  -- D10: predictions of genes it supported that came true
    pred_resolved INTEGER NOT NULL DEFAULT 0,
    license       TEXT
);
CREATE UNIQUE INDEX sources_blob ON sources(blob_sha256);

-- Many-to-many gene <-> source, with stance and the anchoring quote.
CREATE TABLE evidence (
    evidence_id    TEXT PRIMARY KEY,
    gene_id        TEXT NOT NULL REFERENCES genes(gene_id),
    source_id      TEXT NOT NULL REFERENCES sources(source_id),
    stance         TEXT NOT NULL CHECK (stance IN ('FOR', 'AGAINST')),
    evidence_type  TEXT NOT NULL CHECK (evidence_type IN (
                      'EXECUTED', 'OBSERVED', 'INFERRED', 'ABSENCE', 'TESTIMONY', 'ABDUCTION', 'ANALOGY')),
    quote          TEXT NOT NULL,
    quote_offset   INTEGER,
    quote_sha256   TEXT,          -- of the normalised quote; shared quotes reveal shared lineage (D9)
    verified_quote INTEGER NOT NULL CHECK (verified_quote IN (0, 1)),
    added_at       TEXT NOT NULL,
    UNIQUE (gene_id, source_id, stance)
);
CREATE INDEX evidence_gene ON evidence(gene_id);
CREATE INDEX evidence_quote ON evidence(quote_sha256);

-- Genes that answer or bear on a research question (D1: an ANSWERS link counts as connection).
CREATE TABLE charter_links (
    gene_id    TEXT NOT NULL REFERENCES genes(gene_id),
    charter_id TEXT NOT NULL REFERENCES charters(charter_id),
    rel        TEXT NOT NULL CHECK (rel IN ('ANSWERS', 'BEARS_ON')),
    created_at TEXT NOT NULL,
    PRIMARY KEY (gene_id, charter_id, rel)
);

-- Calibration ledger (R5): checkable predictions and how they resolved.
CREATE TABLE predictions (
    prediction_id     TEXT PRIMARY KEY,
    gene_id           TEXT NOT NULL REFERENCES genes(gene_id),
    statement         TEXT NOT NULL,
    support_at_making REAL NOT NULL,
    resolve_after     TEXT,
    outcome           TEXT CHECK (outcome IN ('HIT', 'MISS', 'VOID')),
    resolved_at       TEXT,
    made_at           TEXT NOT NULL
);

CREATE TABLE edges (
    edge_id    TEXT PRIMARY KEY,
    src        TEXT NOT NULL REFERENCES genes(gene_id),
    dst        TEXT NOT NULL REFERENCES genes(gene_id),
    rel        TEXT NOT NULL CHECK (rel IN (
                  'CORROBORATES', 'CONTRADICTS', 'EXTENDS', 'DEPENDS_ON', 'DERIVED_FROM',
                  'CAUSES', 'PART_OF', 'SUPERSEDES', 'PARALLELS', 'ANSWERS')),
    note       TEXT,
    created_by TEXT,
    created_at TEXT NOT NULL,
    UNIQUE (src, dst, rel)
);
CREATE INDEX edges_dst ON edges(dst, rel);

CREATE TABLE entities (
    entity_id      TEXT PRIMARY KEY,
    canonical_name TEXT NOT NULL UNIQUE,
    kind           TEXT,
    aliases        TEXT              -- JSON array
);
CREATE TABLE gene_entities (
    gene_id   TEXT NOT NULL REFERENCES genes(gene_id),
    entity_id TEXT NOT NULL REFERENCES entities(entity_id),
    PRIMARY KEY (gene_id, entity_id)
);

-- Negative knowledge with expiry. URL tombstones stop re-fetching; CLAIM tombstones stop re-judging.
CREATE TABLE tombstones (
    key          TEXT PRIMARY KEY,   -- canonical URL or normalised-claim sha256
    kind         TEXT NOT NULL CHECK (kind IN ('URL', 'CLAIM')),
    reason       TEXT NOT NULL,
    nearest_gene TEXT REFERENCES genes(gene_id),
    rejected_at  TEXT NOT NULL,
    expires_at   TEXT NOT NULL
);

-- Blackboard: agents never talk to each other, only through leased tasks.
CREATE TABLE tasks (
    task_id      TEXT PRIMARY KEY,
    kind         TEXT NOT NULL,
    payload_json TEXT NOT NULL,
    priority     INTEGER NOT NULL DEFAULT 3,
    charter_id   TEXT REFERENCES charters(charter_id),
    state        TEXT NOT NULL DEFAULT 'QUEUED' CHECK (state IN ('QUEUED', 'LEASED', 'DONE', 'FAILED', 'DEFERRED')),
    attempts     INTEGER NOT NULL DEFAULT 0,
    lease_until  TEXT,
    not_before   TEXT,
    created_at   TEXT NOT NULL,
    done_at      TEXT
);
CREATE INDEX tasks_ready ON tasks(state, priority, created_at);

-- Every LLM call, for audit and cost tracking.
CREATE TABLE agent_runs (
    run_id        TEXT PRIMARY KEY,
    task_id       TEXT REFERENCES tasks(task_id),
    role          TEXT NOT NULL,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    prompt_sha256 TEXT NOT NULL,
    tokens_in     INTEGER,
    tokens_out    INTEGER,
    cost_usd      REAL,
    ms            INTEGER,
    output_json   TEXT,
    started_at    TEXT NOT NULL
);

-- Every state change, for replay and "who said this, when, from what?".
CREATE TABLE events (
    event_id   TEXT PRIMARY KEY,
    gene_id    TEXT,
    kind       TEXT NOT NULL,
    before     TEXT,
    after      TEXT,
    actor      TEXT NOT NULL,
    at         TEXT NOT NULL
);
CREATE INDEX events_gene ON events(gene_id, at);

CREATE TABLE embed_meta (
    model  TEXT PRIMARY KEY,
    dims   INTEGER NOT NULL,
    active INTEGER NOT NULL DEFAULT 0
);
