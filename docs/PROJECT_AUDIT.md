# Project audit: 333 Multi-Triangular Recursive Research Framework ("Akashic")

**Audit date:** 2026-11-09
**Audited state:** `main` at `938e038`, PR #1 head `32e63da` (`phase0-scaffold`), PR #2 head `97bf11f` (`phase1-pipeline`)
**Purpose:** a complete, deliberately verbose account of what this project is, what exists, what works, what is broken, what is missing, and whether it is worth finishing. It is written so that a reviewer (human or AI) who has never seen the project can judge it from this file alone, and then check every claim against the code.

**Method.** Every statement about the code below comes from reading the source on the PR branches line by line, running the test suites, and running four small probe scripts against the pipeline (Section 12). Statements about the design come from the repo's `docs/`, `Argon-research.md`, and the project's private planning document (a living design doc kept outside the repo; it is summarised here, not linked, because the repo is public). Where something is an opinion or an estimate, it is labelled as one.

---

## Table of contents

0. [TL;DR and verdict](#0-tldr-and-verdict)
1. [The project at a glance](#1-the-project-at-a-glance)
2. [Goal and design intent](#2-goal-and-design-intent)
3. [History and timeline](#3-history-and-timeline)
4. [Repository and pull-request state](#4-repository-and-pull-request-state)
5. [Working sessions and how decisions were made](#5-working-sessions-and-how-decisions-were-made)
6. [Architecture as designed](#6-architecture-as-designed)
7. [Module-by-module audit of the code](#7-module-by-module-audit-of-the-code)
8. [Data model](#8-data-model)
9. [The admission law and the gravity maths, with worked numbers](#9-the-admission-law-and-the-gravity-maths-with-worked-numbers)
10. [The research and critical-thinking plan, and what of it is built](#10-the-research-and-critical-thinking-plan-and-what-of-it-is-built)
11. [Tests: status and real coverage](#11-tests-status-and-real-coverage)
12. [Probes run for this audit](#12-probes-run-for-this-audit)
13. [Defects found, ranked](#13-defects-found-ranked)
14. [Contradictions between the docs and the code](#14-contradictions-between-the-docs-and-the-code)
15. [What is not built yet](#15-what-is-not-built-yet)
16. [Risks](#16-risks)
17. [Requirements traceability: the owner's asks versus reality](#17-requirements-traceability-the-owners-asks-versus-reality)
18. [Effort to finish (estimates)](#18-effort-to-finish-estimates)
19. [Verdict in full](#19-verdict-in-full)
20. [Open questions and unresolved decisions](#20-open-questions-and-unresolved-decisions)
21. [Appendices](#21-appendices)

---

## 0. TL;DR and verdict

**What it is.** A local-first research library that turns web pages and PDFs into small, atomic claims ("genes"), each anchored to a verbatim quote from its source, stored in a single SQLite file with full-text and vector search. Claims only rise to "corroborated" when several *independent* sources support them and the claim connects to the rest of the library. The bar rises as a topic gets denser ("gravity"). The long-term goal is a 24/7 multi-agent loop on one consumer PC (RTX 4070 12 GB, 96 GB RAM) with optional, capped cloud models, plus a reading layer (briefs, digests, an MCP server) that ends the owner's "ever-losing context battle".

**What exists.** About 2,400 lines of Python and SQL plus 700 lines of tests, all on two **unmerged draft PRs**. `main` still contains only the original prompt as a README and the first design draft (`Argon-research.md`). The code covers the storage core, the admission maths, a supervised `akashic ingest` pipeline (fetch → extract claims with an LLM → verify quotes → embed → judge against neighbours → store), search, briefs, a daily digest and a re-check replay. All 65 tests pass, offline, with a fake model and a fake embedder.

**What has never happened.** The pipeline has never run against a real local model or a real embedder. No benchmark has been run. No source has been hand-audited. None of the roadmap's six gates has been passed, including Phase 0's, although the docs call Phase 0 "done". The autonomous 24/7 part (task workers, scheduler, red-team, verifier, synthesis, MCP server, Obsidian export) is not started.

**What is wrong.** The design is careful and mostly sound, and the code is clean, small and well commented. But this audit found real defects, five of them serious enough to break the system's central promises once it meets real data:

1. Contradictions never weaken anything. The judge can say CONTRADICTS, but the pipeline only draws an edge. It never writes "against" evidence, so `REFUTED` and `CONTESTED` are unreachable from ingestion (Section 13, D-1).
2. A lone, well-evidenced claim cannot become corroborated without a manual step the CLI does not offer. Ingesting links genes to a charter as `BEARS_ON`, but the connection rule (D1) only counts `ANSWERS`. A probe with four independent sources and support 0.93 stayed a hypothesis (D-2). This partly re-creates the cold-start deadlock the project was founded to fix.
3. One bad quote blocks a true claim everywhere for 90 days. Rejection tombstones are keyed on the claim's wording, and are checked before the new quote is looked at, so a later, correctly quoted source is silently dropped (D-3, reproduced).
4. Re-ingesting the same source eventually creates duplicates. Each re-ingest leaves a superseded copy in the vector index. After about six, the copies fill the neighbour list and the next one is admitted as a new gene (D-4, reproduced). This breaks the Phase 2 gate ("re-ingesting creates no new genes") and the owner's "no repeated content" requirement.
5. A REFINES verdict gives a gene new words while keeping old evidence. The old quotes now "support" a thesis they were never checked against, and the number check is skipped (D-5).

**Verdict: worth finishing, but not as currently scoped, and not in the current order.** The core idea (the database is the memory, the model is a small checkable worker, and truth needs independent quoted evidence) is the right answer to the owner's problem, and about a third of the hard thinking is already encoded in tested code. The risk is not the design. The risk is that **the whole edifice rests on one unmeasured assumption: that a 12–14B local model can extract faithful, quotable, atomic claims and judge SAME / REFINES / CONTRADICTS well enough.** Nothing in the repo tests that yet, and the project has spent its effort on epistemic machinery (14 design rulings, 6 frames, 4-valued truth, lineage maths) that is only worth anything if that assumption holds.

The recommended path (Section 19) is: merge the two PRs, fix the five defects (a few days of work), then spend the next effort on **measurement, not features**: run the benchmark on two local models, ingest and hand-audit 10–50 sources, and ship the `brief()` MCP server early because it is the part that pays off for the owner even if the 24/7 hive never ships. Set explicit kill criteria: if quote fidelity under 90% or judge agreement under about 75% cannot be reached with local models after honest tuning, stop the autonomous ambition and keep the system as a supervised, human-in-the-loop library, which is still useful.

---

## 1. The project at a glance

| Item | Value |
| --- | --- |
| Repository | `rawdogin69x-dev/333-Multi-Triangular-Recursive-Research-Framework.` (public; the name ends in a dot) |
| Package name | `akashic` (Python ≥ 3.11, hatchling build) |
| Dependencies | `sqlite-vec ≥ 0.1.6`, `pyyaml`, `httpx`; dev: `pytest`; optional: `pypdf` |
| Code size (PR #2) | 2,432 lines across 15 Python modules and 1 SQL migration |
| Test size (PR #2) | 703 lines, 7 test files, 65 tests |
| Test result | PR #1: 29 passed. PR #2: 65 passed (Python 3.13, run for this audit) |
| CI | None. There is no `.github/` folder, so tests have never run on GitHub |
| On `main` | `README.md` (the owner's original brief, 7 lines) and `Argon-research.md` (first design draft, 332 lines). No code |
| Open PRs | #1 Phase 0 (draft, base `main`), #2 Phase 1 (draft, stacked on #1). Neither reviewed or merged |
| Real-model runs | None |
| Gates passed | 0 of 6 |
| Cloud spend allowed | $0 (hard-coded default; cloud providers refuse to run at a $0 cap) |
| Target hardware | One Windows PC under WSL2: RTX 4070 (12 GB VRAM), 96 GB DDR5 |
| Last code commit | 2026-10-25 |
| Last activity before this audit | 2026-10-26 (request to merge the PRs; blocked on review) |

---

## 2. Goal and design intent

### 2.1 The owner's brief, restated

The README on `main` is the owner's original brief, kept verbatim. Paraphrased into requirements:

| # | Requirement in the owner's words (paraphrased) | Interpretation used by the design |
| --- | --- | --- |
| G1 | A framework that works with local **or** cloud LLMs | OpenAI-compatible model gateway; local by default, cloud behind spend caps |
| G2 | A "carefully designed circular research system" that "continuously appends and extends deep research" 24/7 | A loop of roles (find gaps → forage → distil → judge → verify → synthesise → re-check) over a task queue |
| G3 | "As research data increases, so must the severity, interconnectedness and accuracy" | The **gravity rule**: the evidence needed for promotion rises with a topic's settled mass |
| G4 | "Mass can only increase if it is TRUE, ACCURATE, RELEVANT, AND THEREFORE INTERCONNECTED" | Promotion needs independent evidence **and** a typed connection (ruling D1) |
| G5 | Everything "accurately labelled, dated, understood, connected" | Frames, lifecycle states, publication and validity dates, typed edges, an event log |
| G6 | No superfluous or repeated content, without losing nuance | Judge verdicts SAME (merge as corroboration) / REFINES (new version) instead of new rows |
| G7 | Label "rubbish rubbish and treasure treasure" | Named rejection reasons, tombstones with expiry, states that are never deleted |
| G8 | "Genes of research", chronological and implementable, not a book you never finish | Atomic claim template (thesis, reason, example, application, scope) with version history |
| G9 | Solve the "ever-losing context battle": even 1M tokens is not enough | The DB is the memory; folded, token-budgeted **briefs** and an MCP server feed any AI session |
| G10 | Memorise and intuit multi-step ideas easily | Digest, trails, pictures-before-lists cards, Anki export (planned) |
| G11 | Raw SQLite plus a vector format ("RAW akashic records") | One SQLite file with FTS5 and `sqlite-vec`, plus a content-addressed blob store of raw sources |
| G12 | A **safe** 24/7 auto-agent that picks sources and chooses local or cloud agents; a "hive" | Leased task queue, single writer, budgets, kill switch, quarantine of scraped text (planned) |
| G13 | Efficiency on a 4070 + 96 GB RAM, within API limits (Codex / Claude / Antigravity) | Day/night model shifts, MoE with experts in RAM, API keys with caps, no subscriptions in the loop |
| G14 | (Later, from the owner) Vedic, esoteric and Indian-logic ideas woven in, labelled by status | Indian epistemology as design heuristics; esoteric content only in its own frames |
| G15 | (Later) A Steiner-method persona steers design decisions | "Rudolf" persona; rulings S1–S10 and D1–D14 |

### 2.2 The core design thesis

> **The database is the mind; the LLM is a stateless worker.**

This is the single most important idea in the project and it is sound. Context windows degrade and are expensive; a queryable store does not. Models only do small, checkable jobs (extract claims from one chunk, compare two claims), and every model output is validated by deterministic code before it is written. The design then adds three independent admission questions in place of a single magic score:

1. **Anchored?** The claim's quote must appear verbatim in the raw source (deterministic, free).
2. **New?** Compare against nearest neighbours with a judge (SAME / REFINES / CONTRADICTS / RELATED / NEW).
3. **True?** Count *independent lineages* of evidence with a noisy-OR, under a threshold that rises with topic mass, and require a connection into the library.

### 2.3 What the project is not

It is not a chatbot, not a RAG wrapper over documents, and not a summariser. It stores *propositions with provenance*, not documents. It is also explicitly not a claim that esoteric material is true: the "Akashic records" name is labelled a metaphor for the append-only raw archive.

---

## 3. History and timeline

| Date (UTC) | Event |
| --- | --- |
| 2026-10-24 | Repo created; README holds the brief. `Argon-research.md` (first design, from another AI system, called "Argon" here) committed |
| 2026-10-24 | Argon reviewed. The review found its admission gate broken (Section 3.1) and produced a replacement design and a phased build plan in the private planning doc |
| 2026-10-24 | Owner's standing instruction set: "Architect, ask your master builder (me), think autonomously and self critique." Repo declared public: commit only framework code and docs |
| 2026-10-24 23:05 | **PR #1** (Phase 0) opened: schema, anchor check, evidence maths, store, CLI, benchmark harness. 29 tests. Two self-found bugs fixed |
| 2026-10-25 13:00 | Owner redirected: pause building, deepen the critical-thinking design. "Critical thinking engine v2" (R1–R10) written into the plan |
| 2026-10-25 13:37 | Owner asked for a Rudolf Steiner persona to steer design. "Rudolf" written, with rulings S1–S10 |
| 2026-10-25 15:09 | Owner: "yes or no is irrelevant, Steiner must decide, proceed autonomously". Rudolf now decides design questions. Rulings D1–D14 recorded; `docs/DECISIONS.md` pushed to PR #1 |
| 2026-10-25 22:00 | Owner: keep building autonomously while away |
| 2026-10-25 22:12 | **PR #2** (Phase 1) opened: rulings in code, ingest pipeline, search, brief, digest, Rückschau. 65 tests |
| 2026-10-26 03:16 | Owner asked for the live GitHub to show the current state. The merge was blocked because the PRs had no review; the owner was asked to merge #1 then #2. No reply since |
| 2026-11-09 | This audit |

### 3.1 Why Argon's gate was replaced (verified by re-reading `Argon-research.md`)

Argon proposed `S(c) = V · C_tri^α · I_nov^β / (1 + λ·R_max)` against `τ(M) = 0.35 + 0.08·ln(1+M)`. Its own code returns a triangulation score of 0.05 when there are fewer than two neighbours, so with V = I = 0.9 the best score on an empty library is about 0.9 × 0.05^1.2 × 0.9 ≈ 0.022, far below 0.35: **nothing can ever enter**. Its "triangulation" rewards being *near* two topics, which is topical closeness, not corroboration. And a second source repeating a known claim has high similarity, so it is binned as RUBBISH, which throws away exactly the signal accuracy depends on. The review listed twelve defects of this kind (cold start, closeness-as-corroboration, saturation in dense topics, spec/code disagreement, invented thresholds, and more) plus schema errors (a column name with a space in it, one gene per source, no publication dates), hardware errors (tmpfs on Windows, vLLM flags, a 14B model at 32K context not fitting 12 GB), and an overclaim ("3,000-token lossless briefing of 2 million tokens"). The replacement kept Argon's good parts: one SQLite file with `sqlite-vec` and FTS5, typed blackboard, tombstones, local-first routing, a tool-less distiller with a grammar, and nightly consolidation.

This review was careful and its corrections are correct as far as this audit can check them.

---

## 4. Repository and pull-request state

### 4.1 Branch picture

```
main ── bcb0920 Initial commit
     ── b67db9e Update README.md
     ── 938e038 Create Argon-research.md           <- main is here (no code)
           │
           └── phase0-scaffold (PR #1, draft, base main)
                 04a091f Phase 0: core schema, admission maths, anchor check, CLI, benchmark harness
                 32e63da Docs: Rudolf's rulings D1–D14, aligned architecture/assumptions/charter
                   │
                   └── phase1-pipeline (PR #2, draft, base phase0-scaffold)
                         50f4244 Implement rulings D1, D5, D6, D9, D10, D11 in the core
                         97bf11f Phase 1 scaffold: forage, distil, anchor, judge, search, brief, digest
```

### 4.2 PR #1: "Phase 0: core schema, evidence-based admission law, CLI and model benchmark"

* **State:** open, draft, not reviewed, not merged. Base `main`. 27 files, +1,670 lines.
* **Contents:** `akashic/anchor.py`, `lifecycle.py`, `store.py`, `db.py`, `config.py`, `ids.py`, `cli.py`, migration `0001_init.sql`, `bench/bench_models.py`, `docs/` (architecture, roadmap, assumptions, self-critique, setup, decisions), example configs, `.gitignore`, tests.
* **Tests:** 29 pass (this audit, run against PR #1's own code).
* **Note:** the second commit is docs only. It records rulings D1–D14 that the PR #1 code does not implement; `docs/DECISIONS.md` says so ("Phase 0 code predates these rulings").

### 4.3 PR #2: "Phase 1 scaffold: ingest pipeline and Rudolf's rulings in code"

* **State:** open, draft, not reviewed, not merged. Base `phase0-scaffold` (stacked). 25 files, +2,095 / −95 lines relative to PR #1.
* **Contents:** rulings D1, D5, D6, D9, D10, D11 in `store.py` / `lifecycle.py` / schema; new modules `forage.py`, `llm.py`, `distill.py`, `embed.py`, `search.py`, `judge.py`, `ingest.py`, `brief.py`, `maintenance.py`; CLI commands `ingest`, `show`, `search`, `brief`, `digest`, `rueckschau`, `resonate`; tests for each.
* **Tests:** 65 pass.
* **Merge mechanics:** merge #1 into `main` first, then retarget #2 to `main` (GitHub usually does this automatically when the base branch is merged and deleted) and merge it. No conflicts are expected because `main` has not moved.

### 4.4 Why `main` looks empty

Nothing has been merged. The project's agent sessions are not allowed to merge without a review, and the owner has not yet reviewed or merged. Anyone browsing the public repo sees only the brief and the superseded Argon draft, which misrepresents the project's state. **Merging is the first action recommended in this audit** (or, if the owner wants to wait, at least add a line to the `main` README pointing to the PRs).

### 4.5 Public-safety check of the repo

A search of the PR #2 tree for personal names, email addresses, Windows paths and home-directory paths found nothing. Data, real configs, benchmark fixtures, the inbox and database files are git-ignored. The Forager deliberately replaces local file paths with `file://local/<hash>/<name>` so that the owner's folder structure never reaches the DB. The only identifying string is the GitHub repo URL in the Forager's User-Agent, which is public anyway and is the correct politeness practice for a crawler.

---

## 5. Working sessions and how decisions were made

The project ran as a set of AI working sessions coordinated on the owner's behalf:

| Session | Purpose | State |
| --- | --- | --- |
| Connect the GitHub repo | Attach the repo to the project | Done |
| Refine the research framework's critical thinking | All design and build work so far: the Argon review, the plan, Phase 0, the critical-thinking refinements, the Rudolf persona, rulings, Phase 1 | Waiting on the owner (to merge PRs #1 and #2) |
| Write the full project audit | This document | In progress |

### 5.1 Governance as it actually operated

* The owner set the direction in short messages and was away for long stretches ("I'll be back in 7 hrs").
* The owner's standing instruction is to work autonomously, pick labelled defaults, and self-critique. Defaults for facts only the owner can supply are recorded in `docs/ASSUMPTIONS.md` (A1–A12).
* Since 2026-10-25, **design questions are decided by "Rudolf"**, an AI persona built from Rudolf Steiner's published *method* (percept + concept; Goethe's phenomenon-first science; threefolding; Imagination / Inspiration / Intuition used as a three-pass pattern; the nightly Rückschau review). It is labelled an ATTRIBUTED, interpretive lens. Steiner's clairvoyant content claims are excluded as fact, and his racial teachings are rejected outright.
* The owner is asked only for things a persona cannot supply: budgets, credentials, personal facts.

**Audit comment.** This arrangement got a lot done quickly, and the rulings themselves are mostly sensible engineering in philosophical clothing (Section 10.3). But it has a structural weakness: an AI was, in effect, deciding design questions by role-playing a persona, and then the same AI implemented and reviewed the result. Two of the five serious defects (D-2 and the unreachable refutation path, D-1) sit exactly where a ruling met the code and nobody outside the loop checked the seam. This is the strongest argument for the reviewing agent and the owner to read Section 13 closely.

---

## 6. Architecture as designed

### 6.1 Components

```
                    owner: charters (YAML), resonance marks, review queue, capture inbox
                                          │
                ┌─────────────────────────▼─────────────────────────┐
                │  STEWARD (planned)  finds stalled / contested /    │
                │  unanswered genes, emits FORAGE / VERIFY tasks     │
                └─────────────────────────┬─────────────────────────┘
                                          │ tasks table (leased, planned)
   ┌──────────────┐   raw bytes   ┌───────▼───────┐  claims+quotes  ┌──────────────┐
   │   FORAGER    │──────────────▶│   DISTILLER   │────────────────▶│ ANCHOR CHECK │
   │ forage.py ✓  │  blob store   │ distill.py ✓  │  (GBNF grammar)  │ anchor.py ✓  │
   └──────────────┘               └───────────────┘                  └──────┬───────┘
                                                                            │ HYPOTHESIS
   ┌──────────────┐  neighbours   ┌───────────────┐   verdicts       ┌──────▼───────┐
   │  SEARCH      │──────────────▶│    JUDGE      │─────────────────▶│   ARBITER    │
   │ search.py ✓  │ FTS5 + vec    │  judge.py ✓   │ SAME/REFINES/... │  store.py ✓  │
   └──────────────┘               └───────────────┘                  │ lifecycle ✓  │
                                                                     └──────┬───────┘
   planned: RED-TEAMER, VERIFIER (network-less Docker), SYNTHESIST,         │ events, RECHECK
            LIBRARIAN, cloud escalation for CONTESTED                       ▼
                                                     ┌──────────────────────────────────┐
                                                     │ READING LAYER: brief.py ✓,        │
                                                     │ digest + Rückschau ✓, MCP server, │
                                                     │ Obsidian / Anki export (planned)  │
                                                     └──────────────────────────────────┘
```

✓ = exists in code on PR #2. Everything else is design only.

### 6.2 Principles that hold throughout the code

* **Single writer.** Only `Store` (the "Arbiter") writes knowledge tables. Every state change writes an `events` row.
* **Nothing is deleted.** Rejected, refuted and superseded genes stay, labelled.
* **Models are untrusted.** Model output is parsed strictly; malformed claims are dropped and counted, never repaired by guessing.
* **Scraped text is data.** Sources are wrapped in delimiters with an instruction to ignore embedded instructions, and injection-like phrases are flagged.
* **Every model call is logged** (`agent_runs`: role, provider, model, prompt hash, tokens, cost, latency, output).
* **Cloud is off by default.** A non-local provider with a $0 cap raises `BudgetExceeded`.

### 6.3 Runtime target (planned, not built)

WSL2 Ubuntu; DB on the Linux filesystem (never `/mnt/c`); llama.cpp with CUDA behind llama-swap; one resident LLM at a time: a day model (14B dense at 16K context fully on GPU, or a 30B-A3B MoE with experts in RAM) for extraction and judging, and a large MoE at night with experts in system RAM for red-teaming and synthesis; embedder on CPU; the GPU yielded when the owner wants it. The setup guide (`docs/SETUP.md`) covers WSL2, CUDA, llama.cpp build flags and the benchmark. The hardware reasoning in the plan (KV-cache sizes, offload speeds, AVX-512 caveats) is careful and labelled as needing re-checking at build time.

---

## 7. Module-by-module audit of the code

All paths are on the `phase1-pipeline` branch (PR #2). Line counts are approximate.

### 7.1 `akashic/ids.py` (24 lines)

* `uuid7()`: hand-rolled RFC 9562 UUIDv7 (48-bit ms timestamp, version and variant bits, random). Correct bit layout. Monotonic only to the millisecond; two ids in the same millisecond sort randomly. That matters slightly for `rueckschau`, which orders by `created_at DESC, task_id DESC`; ties within a second are broken by UUID, which is time-ordered only to the ms. Harmless.
* `now()`: UTC ISO-8601 to the second. Second precision means events within one second cannot be ordered by time alone. Acceptable for now.

### 7.2 `akashic/config.py` (95 lines)

* Frozen dataclasses: `GravityConfig` (τ0 0.60, γ 0.03, τ_max 0.95, k_base 2, k_cap 4, holds 0.50, topic_depth 2), `EvidenceWeights` (EXECUTED 0.95, OBSERVED 0.85, INFERRED 0.60, ABSENCE 0.50, TESTIMONY 0.50, ABDUCTION 0.35, ANALOGY 0.20), `PipelineConfig` (judge_floor 0.80, min_confidence_same 0.75, neighbours 5, max_claims_per_chunk 8, grammar on, 5 s per-host fetch interval), `Config`.
* `load()` rejects unknown top-level keys, which is good. Nested sections are passed as `**kwargs`, so an unknown nested key raises a `TypeError` with a less friendly message. Minor.
* All constants are explicitly labelled as guesses to calibrate in Phase 2. That labelling is honest and correct.

### 7.3 `akashic/db.py` (91 lines)

* Connects with WAL, `synchronous=NORMAL`, foreign keys, 5 s busy timeout, an 8 GB `mmap_size` and about a 2 GB page cache (uses the big RAM instead of Argon's unsafe RAMDisk). Loads `sqlite-vec`.
* Migrations: numbered `.sql` files, applied in a transaction, tracked by `PRAGMA user_version`. Version 1 also creates the virtual tables: a contentless FTS5 table plus a rowid map, and a `vec0` table with cosine distance whose dimension comes from config.
* `_split()` splits SQL on `;` after stripping `--` comments. Its own docstring states the limitation (no triggers, no `;` or `--` inside strings). Fine for now, a trap later.
* **Issue:** the vector dimension is fixed at migration time. Changing embedder (for example from a 1024-d to a 768-d model) needs a migration that does not exist yet; the `embed_meta` table intended to track this is never written. Planned for Phase 5.

### 7.4 `akashic/migrations/0001_init.sql` (205 lines)

Tables: `charters`, `genes`, `gene_versions`, `sources`, `evidence`, `charter_links`, `predictions`, `edges`, `entities`, `gene_entities`, `tombstones`, `tasks`, `agent_runs`, `events`, `embed_meta`. Detailed in Section 8. CHECK constraints enforce the frame, state, stance, evidence-type and edge-type vocabularies, which is good defensive design. The schema was amended in place to carry rulings D1–D14 "before first release"; that is fine only because nothing has been released and no real DB exists.

### 7.5 `akashic/anchor.py` (92 lines): step 1, deterministic

* `normalise()` applies NFKC (ligatures, full-width forms), maps curly quotes and dashes to straight ones, joins line-break hyphenation (`extrac-\ntion` → `extraction`), collapses whitespace and casefolds. A parallel index map turns a match back into an offset in the raw text.
* `find_quote()` refuses quotes shorter than 20 characters after normalisation (too easy to match by accident) and returns the raw offset or `None`.
* `unsupported_numbers()` extracts numbers (with commas, decimals, percentages) from the thesis and requires each to appear in some quote, after canonicalising (`1,000` = `1000`, `0.50` = `0.5`).
* **Quality:** good. This is the cheapest and most valuable anti-hallucination check in the system, and it is well implemented and tested.
* **Limits:** a number written in words ("three datasets") is not a number to this check, so "improves recall on 3 datasets" against a quote saying "three datasets" is rejected as NUMBER_MISMATCH (a false rejection, safe side). Unicode minus signs are mapped. Hyphen joining only fires when the character before is a letter, so "COVID-\n19" is left alone, which is correct. PDF text extraction artefacts (columns interleaved, headers mid-sentence) will defeat exact matching; that is the main expected source of false VIKALPA rejections and must be measured in the Phase 1 audit.

### 7.6 `akashic/lifecycle.py` (227 lines): step 3, pure functions

* **Lineage grouping (D9):** rows from sources whose quotes share at least half of their 8-word shingles (Jaccard ≥ 0.5) are unioned into one lineage, even across domains. This catches syndicated text and press-release copies. Quotes shorter than 8 words are compared as a single tuple, so they merge only when identical.
* **Assessment:** within each (stance, lineage), only the strongest `w × r` counts. Support and against are noisy-ORs over lineages. Unverified quotes count for nothing.
* **Four-valued truth:** SUPPORTED / REFUTED / CONTESTED / UNKNOWN at a `holds` threshold of 0.5 (Belnap–Dunn, which the docs map to the Buddhist catuṣkoṭi).
* **Gravity:** `tau(M) = min(0.95, 0.60 + 0.03·ln(1+M))`, `k_required(M) = min(4, 2 + floor(log10(1+M)))`.
* **`next_state()`:** terminal and DERIVED genes never move here. An entrenched gene (CORROBORATED or AXIOM, or one that was ever promoted) needs `k + 1` lineages against to fall. SPECULATIVE and METAPHOR frames never rise above HYPOTHESIS. Promotion needs `connected` (D1), at least `k` lineages, support ≥ τ, and against < holds.
* **`source_reliability()` (D10):** a base of 0.3–0.7 from transparency (0.5 if unknown), blended Beta-style towards the observed prediction hit rate with a prior strength of 4.
* **`derived_support()`:** the minimum of premise supports.
* **`axiom_eligible()`:** defined, never called (no Librarian yet).
* **Quality:** clear, small and testable. The "ever promoted" fix for the CONTESTED loophole shows real care.
* **Design caveats:** noisy-OR treats the weights as calibrated probabilities, which they are not; the docs correctly say "support is a ranking, not a probability". `group_lineages` is O(n²) per gene in quoted rows, fine at current scale. ATTRIBUTED and PHENOMENOLOGICAL genes can be corroborated; FORMAL genes are treated like empirical ones (a proof is evidenced by lineages of sources, not by checking the proof), which is a known simplification.

### 7.7 `akashic/store.py` (454 lines): the Arbiter

Methods and what they actually do:

| Method | Behaviour | Audit notes |
| --- | --- | --- |
| `add_charter` | Insert a research question | No update, pause or done operation; `status` is never changed by code |
| `link_charter(gene, charter, rel)` | Insert an ANSWERS or BEARS_ON link, then reassess | Only ANSWERS counts for D1. **There is no CLI command for this** (D-2) |
| `add_source` | Dedup by blob hash; lineage defaults to the root domain; reliability from transparency | `root_domain` takes the last two labels, so `bbc.co.uk` and `gov.uk` sites collapse to `co.uk` / `gov.uk` (documented weakness) |
| `add_candidate` | Insert gene + version 1 + FTS row; event | Frame validated |
| `add_derived` | D11: requires premises, a rule and a prediction; DERIVED_FROM edges; a prediction row; a `TEST_PREDICTION` task | Nothing consumes `TEST_PREDICTION` tasks yet |
| `set_resonance` | D5: −2..2 in its own column; event | The gate code never reads it (verified by grep and test) |
| `attach_evidence` | Verifies the quote against the raw text *here*, never trusting the caller | `UNIQUE(gene, source, stance)`: a second quote from the same source for the same gene is silently ignored, which conflicts with SELF_CRITIQUE item 5 ("allow several quotes per claim") |
| `add_edge` | Insert, then reassess both ends | No validation that `rel` fits the frames; the schema CHECK limits the vocabulary |
| `upsert_vector` | Replace the gene's vector, tagging frame and topic | The frame/topic metadata is never used to filter searches |
| `merge_into` (SAME) | Move the duplicate's evidence to the target, mark duplicate SUPERSEDED, reassess target | The duplicate's vector stays in the index (D-4) |
| `refine` (REFINES) | Candidate's text becomes the target's next version; evidence moves; FTS updated | Target keeps its old evidence for the new wording, without re-anchoring or the number check (D-5). No SUPERSEDES edge is created, so the planned "trails" cannot be built from edges |
| `anchor_check` | CANDIDATE → HYPOTHESIS, or REJECTED (VIKALPA, NUMBER_MISMATCH) with a 90-day CLAIM tombstone keyed on the thesis | The tombstone key is the cause of D-3 |
| `is_connected` | D1: any non-PARALLELS edge to a live, non-METAPHOR gene, or an ANSWERS charter link | A link to another unverified HYPOTHESIS counts, and so does a CONTRADICTS edge. So two weak hypotheses that cite each other satisfy D1 for both |
| `topic_mass` | Sum of support over CORROBORATED and AXIOM genes in the topic prefix | Correctly escapes LIKE wildcards |
| `reassess` | Recompute evidence, connection and mass (minus the gene's own support if settled), apply `next_state`, write | The self-mass fix was caught in review; good |
| `_reassess_derived` | Support = premise chain combined with its own evidence; REFUTED if any premise fell or own against wins | Derived genes can never reach CORROBORATED, by design |
| `resolve_prediction` | HIT / MISS / VOID; updates `pred_hits` / `pred_resolved` and reliability of every FOR source; queues RECHECK for every gene those sources support | Correct D10 behaviour. No CLI command, no Brier score (R5 is only half built) |
| `_set_state` | Writes the cached maths; on a state change writes an event and queues RECHECK for dependants (DEPENDS_ON, DERIVED_FROM) | Truth maintenance works for those two edge types |

**Transactions.** Each method opens its own `BEGIN IMMEDIATE`. Multi-step operations in the pipeline (add candidate → attach evidence → anchor → embed → judge → merge) are therefore *not* atomic as a whole. If the embedder or the judge fails half-way, the DB keeps a HYPOTHESIS gene with no vector, which can never be found as a neighbour, which leads to duplicates later (D-7).

### 7.8 `akashic/forage.py` (275 lines): the Forager

* `canonical_url()`: lower-cases scheme and host, drops default ports, fragments and tracking parameters (`utm_*`, `fbclid`, `gclid`, `ref`…), sorts the query, collapses slashes, strips the trailing slash.
* `BlobStore`: raw bytes gzip-compressed under `sha[:2]/sha[2:4]/sha.gz`, addressed by the hash of the *uncompressed* bytes; atomic write via a temp file. (The plan said `.zst`; gzip is a fine substitute.)
* `html_to_text()`: a standard-library `HTMLParser` that skips script, style, nav, header, footer, aside, form, svg, template and iframe; keeps block structure as newlines; reads citation / Dublin Core / OpenGraph metadata for title, authors, date and DOI.
* `pdf_to_text()`: optional `pypdf`, page texts joined by blank lines.
* `transparency_signals()` (D10): the share of six regexes present (data available, code available, methods section, DOI, supplementary / pre-registration, statistics such as `n =` or p-values). Labelled in its docstring as a cheap, gameable prior.
* `injection_flags()`: a regex for phrases that address an AI ("ignore previous instructions", "system prompt", "as an AI language model"…). Flagged and passed to the distiller as a warning, never obeyed.
* `Politeness`: per-host minimum interval and robots.txt caching per origin.
* `Forager.fetch()` / `from_file()`: robots check, pacing, fetch with redirects, blob store, type-specific extraction, signals. Local files get a synthetic `file://local/<hash>/<name>` URI.
* **Issues:**
  * The robots check runs on the requested URL, not on the final URL after redirects.
  * `max_bytes` is applied after the whole response is downloaded (`r.content[:max]`), so a huge response is still pulled into memory.
  * **No SSRF guard.** Any URL is fetched, including `http://127.0.0.1:8080/…` (the model server itself) and LAN addresses. Harmless while the owner types the URLs; a real risk once a Steward picks URLs from scraped pages in Phase 3.
  * The `methods` regex matches the word "method" anywhere, so almost every technical page scores at least 1/6. The docs acknowledge the heuristic is gameable.
  * A `PermissionError` from robots.txt, or any HTTP error, is not caught by the CLI, so one bad URL aborts a whole multi-target `ingest`.

### 7.9 `akashic/llm.py` (116 lines): the Gateway

* `Provider` (name, base URL, model, local flag, API-key environment variable name, monthly cap, prices). Keys are read from the environment at call time and never stored or logged.
* `http_transport()`: OpenAI-compatible `/chat/completions`; temperature 0.1; `max_tokens` 2048; adds `response_format: json_object` in JSON mode and a llama.cpp `grammar` for local providers; a 900 s timeout.
* `Gateway.call()`: refuses cloud providers at a $0 cap or when this month's logged spend reaches the cap; logs every call.
* **Issues:**
  * The distiller sends **both** `response_format` and a `grammar`. Recent llama.cpp server builds treat `response_format` as a JSON-schema constraint and reject requests that specify a schema and a grammar together. **This is likely to fail on the first real run** and must be checked against the installed llama.cpp build (D-6). The fix is one line (send only the grammar to local providers).
  * `max_tokens` 2048 for up to 8 claims with ten fields each is tight. If output is cut off, the JSON is incomplete, `distill.parse` fails, and *every* claim in that chunk is lost and counted as one dropped item. Needs measuring in the benchmark.
  * No retries, no backoff, no rate-limit handling, no timeout per role.
  * The budget check happens before the call and the cost is logged after, so concurrent calls (Phase 3) could overshoot a cap; for a single-process supervised CLI this does not matter.
  * Cost is computed from configured per-token prices, not from provider billing. Fine as an estimate.

### 7.10 `akashic/distill.py` (136 lines): the Distiller

* System prompt: source is untrusted data; for each claim fill **phenomenon first**, then a verbatim quote (20–300 chars), then a single falsifiable thesis whose numbers appear in the quote, reason, example, application, scope, frame, evidence type, taxonomy (2–4 dotted lowercase levels). Skip boilerplate and vague claims.
* `gbnf()`: a llama.cpp grammar that forces exactly that JSON shape with the fields in percept-first order. Nice touch: the grammar enforces the ruling (S1) mechanically.
* `chunk()`: paragraph-aware chunks of up to 12,000 characters with a 600-character overlap.
* `parse()`: strict; drops claims with unknown frames or evidence types, a bad taxonomy, an empty thesis/scope/phenomenon, or a short quote.
* **Issues:**
  * The grammar fixes the *shape* but not the vocabularies (frame and evidence type are free strings in the grammar), so invalid values are only caught by `parse`. Tightening the grammar to enumerations is easy and would save wasted claims.
  * Overlapping chunks can extract the same claim twice from one source. The second copy is merged as SAME, harmless, but it costs judge calls.
  * The ruling S6 says `application` is mandatory for EMPIRICAL genes; the prompt and parser allow `null` (contradiction C-6).
  * The distiller's `phenomenon` text is stored in the gene's `nuance` column, so "nuance" in the DB actually holds the percept description, not nuance. Naming drift that will confuse later code.

### 7.11 `akashic/embed.py` (60 lines)

* `HttpEmbedder`: OpenAI-compatible `/embeddings`, checks dimensions, unit-normalises.
* `HashEmbedder`: feature-hashed words and bigrams; explicitly **not semantic**, for tests only. All pipeline tests use it, which means no test exercises real semantic neighbours (Section 11).

### 7.12 `akashic/search.py` (66 lines)

* `fts_query()`: free text → a safe OR-query of quoted terms (no FTS operators pass through). Good.
* `vector_neighbours()`: k-NN over `vec0` with cosine distance; returns similarity.
* `hybrid()`: FTS5 (BM25) and vector ranks fused by reciprocal rank (k = 60); hides REJECTED and SUPERSEDED by default.
* **Issue:** `vector_neighbours` asks for k results and the caller then skips superseded and rejected ones, so dead genes consume neighbour slots (root cause of D-4). Superseded genes should be removed from `gene_vec` on merge, or the query should over-fetch.

### 7.13 `akashic/judge.py` (69 lines)

* Prompt: both claims are data; steelman each first (pūrvapakṣa, R1); one verdict; scopes that do not overlap mean RELATED, not CONTRADICTS; a confidence score.
* `parse()`: unparseable output → RELATED/EXTENDS ("kept apart and linked"); SAME or REFINES below `min_confidence_same` → RELATED (D14); RELATED with an unknown `rel` → EXTENDS.
* `trivially_same()`: identical after normalisation → merge without a model call.
* **Issues:** the judge sees thesis, scope, nuance and frame, but not the quotes or the sources. It cannot tell "the same claim from the same underlying study" from "an independent replication"; that is left to the lineage maths, which is the right split. LLM self-reported confidence is poorly calibrated in general, so `min_confidence_same` is a weak safeguard until calibrated. Unparseable output silently creates an EXTENDS edge, which counts as a D1 connection: **a judge failure can make a gene "connected"**.

### 7.14 `akashic/ingest.py` (159 lines): the pipeline

Flow for each claim: skip if its thesis is tombstoned → add candidate → attach FOR evidence (quote verified) → anchor check → embed thesis + scope → store vector → link to the charter as BEARS_ON → judge against up to 5 neighbours above `judge_floor`:

* different frame → PARALLELS edge, continue;
* identical text → merge, stop;
* SAME → merge, stop; REFINES → refine, stop;
* CONTRADICTS → CONTRADICTS edge, continue; RELATED → typed edge, continue;
* otherwise → NEW.

It returns an `IngestReport` with counts per outcome, rejection reasons and injection flags. Local files get their own lineage (`file:<hash>`).

**Issues:** see D-1 (CONTRADICTS writes no evidence), D-2 (BEARS_ON is not a connection), D-3 (tombstone checked before the quote), D-4 (dead neighbours), D-7 (no atomicity). Also, `ingest_url` checks URL tombstones that **nothing ever writes**, so that check is dead code. And charter-less ingestion gives genes no charter at all, so the OFF_CHARTER rejection reason can never fire.

### 7.15 `akashic/brief.py` (82 lines): the folded brief

Hybrid search for the topic; rank by `RRF score × (0.5 + support) × state weight`; expand two hops over DEPENDS_ON, CONTRADICTS, EXTENDS, DERIVED_FROM, CAUSES and PART_OF edges; print core genes, live contradictions and connected context, each line tagged with state, frame, support, lineages and a gene-id prefix, inside a character budget of about 4 characters per token. Labelled "lossy" in its own output, which fixes Argon's "lossless" overclaim.

**Audit comment:** this is the piece that most directly serves the owner's stated pain (the context battle). It already works. It is not yet exposed as an MCP tool, which is a small job (Section 19).

### 7.16 `akashic/maintenance.py` (75 lines)

* `rueckschau()`: replays queued RECHECK tasks newest-first, reassessing each gene once per round, for up to 20 rounds (S7). Bounded, so cycles cannot loop forever.
* `digest()`: the last N hours: newly corroborated, newly contested, refuted, rejections by reason, the top five open hypotheses (ordered by resonance, then support), and the number of predictions waiting.
* Both work and are tested at a basic level.

### 7.17 `akashic/cli.py` (203 lines)

Commands: `init`, `charters [--load]`, `stats`, `gravity <taxonomy>`, `ingest <targets…> [--charter]`, `show <gene>`, `search <query> [--no-vectors]`, `brief <topic> [--tokens] [--no-vectors]`, `digest [--hours]`, `rueckschau`, `resonate <gene> <value>`.

**Missing commands that the design or the code's own logic needs:** linking a gene to a charter as ANSWERS, adding an edge by hand, merging lineages by hand (promised in SELF_CRITIQUE item 1), recording transparency by hand (promised in item 10), resolving a prediction, adding the owner's own hypothesis (D3), pausing a charter. Several of the docs' mitigations therefore exist only as library calls.

### 7.18 `bench/bench_models.py` (123 lines)

Runs a prompt per fixture page against an OpenAI-compatible server and reports JSON validity, quote-anchor rate, number fidelity, median tokens/s and peak VRAM (via `nvidia-smi`). It appends a summary line to `bench/results.jsonl` (git-ignored).

**Issue (C-7):** the benchmark's prompt is **not** the production distiller prompt. It has no `phenomenon` field, no PHENOMENOLOGICAL frame, no evidence type, no taxonomy, no grammar and no chunking. Benchmark results would therefore not predict the pipeline's behaviour. It should call `distill.build_messages`, `distill.gbnf` and `distill.parse` directly.

---

## 8. Data model

| Table | Purpose | Written by code today? |
| --- | --- | --- |
| `charters` | Research questions: question, scope, priority 1–5, done-when, status ACTIVE/PAUSED/DONE | Insert only; status never changed |
| `genes` | Stable identity: taxonomy, frame, state, reject reason, cached support/against/lineage counts, τ at promotion, forage cycles, stalled, unintegrated, resonance, charter | Yes. `forage_cycles` and `stalled` are never updated |
| `gene_versions` | Five-member template (thesis, reason, example, application) + scope, nuance, rule, prediction, validity dates, author | Yes. `valid_from` / `valid_until` are never filled by the pipeline, and nothing expires a gene when `valid_until` passes |
| `sources` | URI, canonical URI, root domain, title, authors, published date, capture time, blob hash, lineage, reliability, transparency, prediction hits, licence | Yes. `license` is never filled; `canonical_uri` duplicates `uri` |
| `evidence` | Gene × source × stance with evidence type, quote, offset, quote hash, verified flag | Yes, but only `stance = FOR` from the pipeline |
| `charter_links` | Gene ANSWERS / BEARS_ON charter | Yes (BEARS_ON from the pipeline; ANSWERS only via the API) |
| `predictions` | Checkable predictions with outcome | Yes, for DERIVED genes; resolved only via the API |
| `edges` | Typed relations (CORROBORATES, CONTRADICTS, EXTENDS, DEPENDS_ON, DERIVED_FROM, CAUSES, PART_OF, SUPERSEDES, PARALLELS, ANSWERS) | Yes. CORROBORATES, SUPERSEDES and ANSWERS edges are never created |
| `entities`, `gene_entities` | Canonical entities and aliases ("Qwen3" = "Qwen 3") | **Never used** |
| `tombstones` | Negative knowledge with expiry (URL or CLAIM) | CLAIM only; URL tombstones are never written |
| `tasks` | Blackboard: kind, payload, priority, state, attempts, lease, not-before | RECHECK and TEST_PREDICTION are queued; only RECHECK is ever consumed; leases are never used |
| `agent_runs` | Every model call | Yes |
| `events` | Every state change | Yes (state changes, merges, refines, rejections, resonance, charter added) |
| `embed_meta` | Embedding model registry for migrations | **Never used** |
| `gene_fts`, `gene_fts_map` | Contentless FTS5 index | Yes, maintained correctly on refine |
| `gene_vec` | `vec0` cosine vectors with frame and topic | Yes; superseded genes are never removed |

The plan also promised a JSONL events log written alongside the DB, from which "the database can be rebuilt from blobs plus that log". The code keeps events only inside the same SQLite file, so the DB cannot be rebuilt if the file is lost; backups (planned for Phase 5) are the only protection (C-9).

---

## 9. The admission law and the gravity maths, with worked numbers

### 9.1 Thresholds by topic mass

`M_d` is the summed support of CORROBORATED and AXIOM genes in the topic (first two taxonomy levels). Because settled genes usually have support of about 0.7–0.9, "mass 9" means roughly ten to thirteen settled genes.

| Topic mass M | k_required (lineages) | τ (support needed) | To overturn a settled gene |
| --- | --- | --- | --- |
| 0 | 2 | 0.600 | 3 lineages against |
| 9 | 3 | 0.669 | 4 |
| 99 | 4 | 0.738 | 5 |
| 999 | 4 (cap) | 0.807 | 5 |
| 10⁹ | 4 | 0.950 (cap reached near M ≈ 1.2 × 10⁵) | 5 |

### 9.2 Support per lineage

Per-lineage strength is `w × r`. `r` comes from transparency `t` (share of six markers): `r = 0.3 + 0.4·t` before any predictions resolve.

| Source kind | t | r | OBSERVED (w 0.85) | TESTIMONY (w 0.5) |
| --- | --- | --- | --- | --- |
| Fully transparent (data, code, methods, DOI, supplements, stats) | 1.0 | 0.70 | 0.595 | 0.350 |
| Half the markers | 0.5 | 0.50 | 0.425 | 0.250 |
| Opaque prose (book, blog with no data) | 0.0 | 0.30 | 0.255 | 0.150 |

### 9.3 What that means in practice (noisy-OR)

| Evidence | Support | Promotes in an empty topic (k 2, τ 0.60)? | In a dense topic (k 4, τ 0.738)? |
| --- | --- | --- | --- |
| 2 transparent OBSERVED lineages | 0.836 | Yes (if connected) | No, too few lineages |
| 4 transparent OBSERVED lineages | 0.973 | Yes | Yes |
| 2 half-transparent OBSERVED lineages | 0.669 | Yes | No |
| 4 half-transparent OBSERVED lineages | 0.891 | Yes | Yes |
| 2 opaque OBSERVED lineages | 0.445 | No | No |
| 3 opaque OBSERVED lineages | 0.587 | No | No |
| 4 opaque OBSERVED lineages | 0.692 | Yes | No (0.692 < 0.738) |
| 6 opaque OBSERVED lineages | 0.830 | Yes | Yes |
| 4 half-transparent TESTIMONY lineages | 0.684 | Yes | No |

**Reading.** The rule does what the owner asked: severity rises with mass, and transparency is rewarded. Two consequences the owner should accept knowingly:

1. In a dense topic, claims backed only by books, essays or interviews need about six independent sources. That will make the humanities, history and the esoteric frames very slow to corroborate (they are mostly TESTIMONY and opaque prose). This is intended by D10 but it is a big practical effect.
2. Because "independent" means *different percept origin* (D9), most news coverage of a single study counts as one lineage. That is epistemically right and will make corroboration rare in fast-moving topics.

### 9.4 Frames

EMPIRICAL, FORMAL, ATTRIBUTED, SPECULATIVE, METAPHOR, PHENOMENOLOGICAL. SPECULATIVE and METAPHOR never rise above HYPOTHESIS. Cross-frame neighbours only get PARALLELS edges, which do not count as connection. PHENOMENOLOGICAL evidence is grouped by practitioner (the source's author string) rather than by source lineage. That last rule is fragile: author strings are inconsistent ("J. Smith", "John Smith; A. Lee"), so one practitioner can count as several lineages, and two different people with missing author metadata fall back to domain lineages.

---

## 10. The research and critical-thinking plan, and what of it is built

Legend: **Built** = in code and tested. **Partial** = some code, not complete. **Not built** = design only.

### 10.1 Indian-logic and esoteric lenses (status-labelled in the design)

| Lens | Design status label | Used for | Code status |
| --- | --- | --- | --- |
| Pramāṇas | Established philosophy, used as heuristic | Evidence types | Built (the enum and weights) |
| Five-member syllogism | Established, heuristic | Gene template | Built (fields), but "conclusion" is mapped to scope, and example/application are optional |
| Vyāpti | Established, heuristic | DERIVED genes state their rule | Built (required in `add_derived`) |
| Hetvābhāsa | Established, heuristic | Red-team checklist; rejection reasons | Partial: the enum exists; only VIKALPA and NUMBER_MISMATCH are ever produced |
| Vṛttis (vikalpa, smṛti) | Established, heuristic | Unanchored = vikalpa; model recall is never evidence | Built (VIKALPA); smṛti is enforced implicitly because evidence needs a source |
| Syādvāda | Established, heuristic | Mandatory scope | Built (scope NOT NULL) |
| Catuṣkoṭi ≈ Belnap–Dunn | Established | Four-valued truth | Built in maths; CONTESTED/REFUTED unreachable from the pipeline (D-1) |
| Pāṇini meta-rules | Established | Policy precedence; compact taxonomy | Not built |
| "Vertically and crosswise" | Arithmetic valid, Vedic origin not supported | Metaphor for trace-down + cross-confirm | Metaphor only |
| Casting out nines | Established arithmetic | Number cross-check | Built (number check) |
| Meru-prastāra (Pascal's triangle) | Established | Metaphor for "333 triangular" cross-checks | Metaphor only |
| Indra's net, "as above so below", three guṇas | Metaphor | Typed neighbourhoods, multi-scale briefs, display colours | Briefs built; the rest not |
| Akashic records | Not supported as physics | Name of the raw archive | Name only |
| "Vedic physics" | Not supported | ATTRIBUTED frame only | Frame built |

**Audit comment.** The labelling discipline here is genuinely good: every borrowed idea says whether it is established, a heuristic, a metaphor or unsupported, and the system's machinery only relies on the established and heuristic ones. A reviewer worried that the esoteric framing undermines rigour should note that, in the code, it does not: it reduces to standard evidence-type weights, a scope field, four-valued logic and a frame column that quarantines non-empirical material.

### 10.2 Critical thinking engine v2 (R1–R10)

| # | Refinement | Code status |
| --- | --- | --- |
| R1 | Steelman (pūrvapakṣa) before refuting | Partial: the judge prompt asks for steelmen; no red-teamer exists |
| R2 | Every objection must name a settling test | Not built |
| R3 | Bold beats safe; reject vague claims as SAVYABHICARA | Partial: the distiller prompt says skip vague claims; no informativeness score; SAVYABHICARA never produced |
| R4 | Progressive vs degenerating clusters (Lakatos) | Not built |
| R5 | Calibration ledger with Brier scores | Partial: `predictions` table and resolution exist; no Brier scores; only DERIVED genes get predictions |
| R6 | Base rates by field and study type | Not built |
| R7 | Half-life review by taxonomy branch | Not built |
| R8 | Absence as evidence | Not built (ABSENCE evidence type exists; nothing produces it) |
| R9 | Confidence is not importance | Not built (no centrality) |
| R10 | Weekly self-critique meta-review under owner veto | Not built |

### 10.3 Rudolf's rulings

| # | Ruling | Code status | Audit view |
| --- | --- | --- | --- |
| S1 | Percept before concept | Built (field order in prompt and grammar) | Sound; cheap; good for extraction quality |
| S2 / D1 | Truth needs connection | Built in the gate | Sound in principle; in practice reintroduces a partial cold-start block (D-2) and is satisfied too easily by weak links (Section 7.7) |
| S3 | AXIOM by generativity, not raw centrality | Not built | Reasonable |
| S4 | Three night passes (Imagination, Inspiration, Intuition) | Not built | A naming of standard steps (cluster, judge/red-team, synthesise) |
| S5 | Threefold hive: free charters, equal gate, budget by need; cost never affects admission | Partial: the gate does not read cost or author; budgets are only a $0 refusal | Sound; "equal before the gate" is the right fairness rule |
| S6 / D5 | Resonance mark, priority only | Built and tested; the gate cannot read it | Sound and well isolated |
| S6 (part) | `application` mandatory for EMPIRICAL | **Not enforced** (C-6) | Either enforce or drop the claim from the docs |
| S7 | Rückschau, newest-first replay | Built | Fine |
| S8 | Briefs show reasons and dissent | Partial: briefs show contradictions; reasons are not shown | Fine |
| S9 / D6 | PHENOMENOLOGICAL frame | Built | Lineage-by-author is fragile (Section 9.4) |
| S10 | Living review even for AXIOMs | Not built | Fine |
| D2 | Method over rank | Built implicitly (no prestige input exists) | Sound |
| D3 | Owner's ideas enter freely, equal before the gate | Not built (no capture inbox, no command) | Important for G10; small to build |
| D4 | Esoteric mapped on its own terms | Built via frames | Sound |
| D7 | k 2 → 3 → 4, capped at 4 | Built | Sound |
| D8 | First charter: the system's own epistemology | In the example config | Good choice: its quality can be judged by the owner, and its output improves the tool |
| D9 | Independence shown, not presumed | Partial: shared-passage merge only; no shared-dataset, shared-author or citation detection | Right principle; the implemented half is the easy half |
| D10 | Reliability from transparency and predictions, never agreement | Built | Sound; the transparency regexes are crude |
| D11 | DERIVED genes must predict something checkable | Built at the API level; nothing generates DERIVED genes or tests predictions | Sound |
| D12 | Pictures before lists for memorisation | Not built | This is the owner's original pain; see Section 17 |
| D13 | Daily / weekly / quarterly rhythm; stalled charters pause | Not built (Rückschau and digest exist as commands, no scheduler) | Fine |
| D14 | Unsure judge → RELATED, never SAME | Built and tested | Sound; but RELATED also counts as connection, so judge uncertainty can satisfy D1 |

---

## 11. Tests: status and real coverage

### 11.1 Results (run for this audit, Python 3.13, `pytest -q`)

* PR #1 code: **29 passed**.
* PR #2 code: **65 passed** in about 0.3 s.
* No network, GPU or model is needed. No test is skipped or marked flaky. There is no CI.

(One note for anyone re-running: installing the package in editable mode from one branch and running another branch's tests silently tests the wrong code. Use a fresh virtual environment per branch or set `PYTHONPATH`.)

### 11.2 What the 65 tests cover

| File | Tests | What is genuinely verified |
| --- | --- | --- |
| `test_anchor.py` | 7 | Exact match with offset; smart quotes, case and whitespace; hyphenation; paraphrase refused; short quotes refused; ligatures; numbers must appear |
| `test_config.py` | 3 | Defaults, example config loads, unknown keys refused |
| `test_lifecycle.py` | 17 | Lineage counting, noisy-OR, unverified quotes, gravity curve, cold start with two sources, one source stays hypothesis, dense topics, capped frames, contested, entrenched genes need an extra lineage, terminal states, derived capping, D1 orphans, shared passages merge, different passages stay apart, reliability ignores agreement, opaque sources need more lineages |
| `test_store.py` | 14 | VIKALPA and NUMBER_MISMATCH rejection; D1 with edges and charters; PARALLELS and METAPHOR do not integrate; same domain = one lineage; syndicated quotes across domains = one lineage; phenomenological lineages by practitioner; resonance never moves state; derived genes need rule and prediction and fall with a premise; contested not refuted; prediction resolution updates reliability; vector and FTS round trip |
| `test_distill_judge_llm.py` | 14 (one parametrised) | Strict parsing, malformed claims dropped, garbage handled, chunking, grammar field order, data wrapping and injection warning, D14 downgrade, trivial sameness, gateway logging, $0 cloud refusal, spend cap |
| `test_forage.py` | 7 | URL canonicalisation, HTML extraction with metadata, blob store, signals, fetch via a mock transport, robots disallow, local paths hidden |
| `test_pipeline.py` | 3 | End to end with a scripted fake model and the hash embedder: two sources merge then corroborate after a manual ANSWERS link; re-ingesting once adds no live gene; Rückschau drains RECHECK tasks |

### 11.3 What the tests do **not** cover

* **Any real model behaviour.** The fake model returns exactly the JSON each test needs, so the tests prove the plumbing, not the epistemics. Extraction faithfulness, quote accuracy on real pages, judge accuracy and grammar compatibility are entirely untested.
* **Semantic neighbours.** The hash embedder is not semantic, and `judge_floor=-1.0` in the pipeline fixture sends every neighbour to the judge. The real threshold logic (0.80 cosine for BGE-M3) is untested.
* **The refutation path through the pipeline** (it does not exist; see D-1).
* **Repeated re-ingestion** (only one repeat is tested; the duplicate appears on about the seventh, D-4).
* **Tombstone side effects across sources** (D-3).
* **REFINES** through the pipeline (no test feeds a REFINES verdict).
* **Partial failure** (embedder or model errors mid-ingest).
* **PDFs** (no PDF fixture), large pages, non-UTF-8 pages, redirects.
* **The CLI** (no CLI test at all; `cmd_ingest`, `cmd_show` and the rest are only exercised manually).
* **The benchmark script** (no test).
* **Concurrency** (none exists yet).

The suite is good *unit* coverage of the deterministic core. It is not evidence that the system works.

---

## 12. Probes run for this audit

Four short scripts drove the real `Pipeline` with the same fake model and hash embedder the tests use, changing only the inputs. Each reproduces a defect.

| Probe | Setup | Expected by the design | Observed |
| --- | --- | --- | --- |
| P1: tombstone leak | Source A yields a claim with a made-up quote (rejected VIKALPA). Source B yields the **same thesis** with a valid, verbatim quote | B's claim is admitted as a HYPOTHESIS with one lineage | B's claim is skipped as `tombstoned=1`, `new=0`. The true claim is blocked for 90 days |
| P2: connection block | Four separate files on one charter, each with a *different*, verbatim, transparent quote for the same thesis | Corroborated (4 lineages, support 0.93, and the gene "bears on" a charter) | `HYPOTHESIS`, 4 lineages, support 0.928, `unintegrated=1`. It becomes CORROBORATED only after a manual `link_charter(..., "ANSWERS")` call, which no CLI command offers |
| P2b: identical wording | Same as P2 but all four files use the same sentence | One lineage (D9: a shared passage is one origin) | One lineage. This is correct behaviour, recorded to show D9 works |
| P3: re-ingest duplicates | The same file ingested 8 times | 1 live gene; every repeat merges | Outcomes: new, merged ×5, **new**, merged. 2 live genes and 8 gene rows. The 7th ingest created a duplicate because the five neighbour slots were full of superseded copies |
| P4: refutation | Count AGAINST evidence after all probes | Some, whenever the judge says CONTRADICTS | Zero. No pipeline code path writes AGAINST evidence |

---

## 13. Defects found, ranked

Severity: **Critical** breaks a core promise on real data. **High** produces wrong state or silent loss. **Medium** degrades quality or safety. **Low** is cosmetic or future-facing.

| ID | Severity | Defect | Where | Fix (sketch) |
| --- | --- | --- | --- | --- |
| D-1 | Critical | CONTRADICTS verdicts only add an edge; no AGAINST evidence is ever written, so REFUTED and CONTESTED are unreachable from ingestion and contradictions never lower anyone's support | `ingest._judge_against_neighbours` | When the judge says CONTRADICTS, attach the new source's quote as AGAINST evidence on the old gene (and the old gene's evidence as AGAINST on the new one), then reassess both. Add a pipeline test that drives a gene to CONTESTED and to REFUTED |
| D-2 | Critical | Ingesting with `--charter` writes BEARS_ON, but D1 only counts ANSWERS; no CLI command creates ANSWERS or edges, so a well-evidenced lone claim cannot be corroborated without writing Python | `ingest._admit`, `store.is_connected`, `cli.py` | Either let the judge or a human promote BEARS_ON to ANSWERS (add `akashic link <gene> <charter>` and `akashic edge <a> <rel> <b>`), or count BEARS_ON as connection for genes with ≥ k lineages. Decide via the design process and test it |
| D-3 | High | A rejected claim's thesis is tombstoned for 90 days and checked **before** the new quote, so the same true claim from a different, correctly quoted source is dropped silently | `store.reject`, `ingest._claim_tombstoned` | Key CLAIM tombstones on thesis **and** source (or quote hash), or check the tombstone only after the anchor check fails again |
| D-4 | High | Superseded genes stay in the vector index and consume neighbour slots; repeated ingestion eventually admits a duplicate | `store.merge_into`, `store.refine`, `search.vector_neighbours` | Delete the vector on supersede, and over-fetch neighbours. Add a test that re-ingests 10 times |
| D-5 | High | REFINES replaces the target's wording but keeps its old evidence without re-anchoring or the number check, so quotes can "support" numbers they do not contain | `store.refine` | Re-run the number check against all FOR quotes after a refine; if it fails, keep the candidate as a separate gene linked EXTENDS. Also write a SUPERSEDES edge for trails |
| D-6 | High (likely) | The distiller sends both `response_format` and a GBNF `grammar`; recent llama.cpp servers reject that combination, so the first real ingest may fail outright | `llm.http_transport` | Send only the grammar to local providers; keep `response_format` for cloud. Verify against the installed llama.cpp |
| D-7 | Medium | The per-claim pipeline is not atomic; a failure after the anchor check leaves a HYPOTHESIS gene with no vector, invisible to dedup | `ingest._admit` | Wrap each claim in one transaction, or mark the gene and retry embedding in Rückschau |
| D-8 | Medium | `max_tokens` 2048 can truncate 8-claim JSON; one truncation loses every claim in a 12K-char chunk | `llm.http_transport`, `distill` | Raise `max_tokens`, lower claims per chunk, or stream-parse claims one at a time. Measure in the benchmark |
| D-9 | Medium | A failed or unparseable judge call creates an EXTENDS edge, which satisfies D1, so model failure can make a gene "connected" | `judge.parse`, `store.is_connected` | Use a separate "UNSURE" relation that does not count for D1, or require ≥ k lineages on the linked gene |
| D-10 | Medium | No SSRF guard: the Forager will fetch localhost and LAN URLs, including the model server | `forage.Forager.fetch` | Refuse private, loopback and link-local addresses unless whitelisted; check robots after redirects |
| D-11 | Medium | One failing URL (robots, HTTP error, model error) aborts a multi-target `ingest` | `cli.cmd_ingest` | Catch per target, report, continue |
| D-12 | Medium | `UNIQUE(gene, source, stance)` keeps only one quote per source per gene, contrary to SELF_CRITIQUE item 5 | schema | Make the quote hash part of the key |
| D-13 | Low | URL tombstones are checked but never written | `ingest.ingest_url` | Write them for robots refusals, 4xx and pages with zero admitted claims |
| D-14 | Low | `root_domain` collapses `*.co.uk`, `*.gov.uk` etc. into one lineage (documented) | `store.root_domain` | Use the Public Suffix List (`tldextract`, or a vendored list) |
| D-15 | Low | The distiller's `phenomenon` is stored in the `nuance` column | `ingest._admit` | Add a `phenomenon` column or rename |
| D-16 | Low | The grammar does not constrain frame and evidence type to their enums | `distill.gbnf` | Emit alternations for those two fields |
| D-17 | Low | `max_bytes` is applied after full download | `forage.Forager.fetch` | Stream with a byte limit |

None of these is a sign of careless work; most are seams between separately well-built pieces. All are cheap to fix. D-1 to D-6 together are perhaps two to four days of focused work including tests.

---

## 14. Contradictions between the docs and the code

| ID | Docs say | Code does |
| --- | --- | --- |
| C-1 | README and ROADMAP: "Phase 0 (foundations) is done" | Phase 0's own gate requires "benchmark results for 2+ local models committed"; none exist. Phase 0 is built, not done |
| C-2 | ARCHITECTURE: a contradiction leads to "new gene + edge", and the plan says both genes are "queued for re-evaluation"; four-valued truth is "live" | An edge is added and both ends are reassessed, but no AGAINST evidence exists, so nothing changes (D-1) |
| C-3 | DECISIONS D1: an ANSWERS edge to a charter counts as connection | True, but the pipeline only writes BEARS_ON and the CLI cannot write ANSWERS (D-2) |
| C-4 | ROADMAP Phase 2 gate: "re-ingesting the same 50 sources creates no new genes"; SELF_CRITIQUE 13: "re-ingesting is idempotent" | Re-ingesting creates new superseded rows each time and, after about six repeats, a live duplicate (D-4) |
| C-5 | SELF_CRITIQUE 1 and 10: lineages "can be merged by hand"; the owner "can record transparency by hand" | No command exists for either |
| C-6 | Ruling S6: the "application" field stays mandatory for EMPIRICAL genes | `application` is nullable in the schema, the prompt allows `null`, and the parser accepts it |
| C-7 | SETUP and ROADMAP: the benchmark decides the day-shift distiller | The benchmark uses a different prompt from the distiller, so its numbers will not predict pipeline behaviour |
| C-8 | ARCHITECTURE "Lenses": D9 lineage is "origin of the percept (same dataset, experiment, quoted passage or author group)" | Only quoted-passage overlap is implemented; datasets, experiments, authors and citations are not detected |
| C-9 | Plan: an events JSONL log alongside the DB, so the DB can be rebuilt from blobs plus the log | Events live only inside the same SQLite file |
| C-10 | ASSUMPTIONS A10: "Lineage: root domain for now; D9 moves to origin-of-percept matching" | Already partly moved (shared passages); the row is stale |
| C-11 | Plan: blobs are `.zst` | Blobs are `.gz` (harmless) |
| C-12 | Plan: a NEW gene "must link to at least one existing gene or a charter question within N cycles, or it stalls"; max 2 forage cycles | `forage_cycles`, `stalled` and `max_forage_cycles` exist but nothing reads or writes them |
| C-13 | Plan and DECISIONS D13: a charter without progress for a season pauses | Charter status never changes |
| C-14 | Plan: "valid_until passes" makes a CORROBORATED gene leave that state | Nothing reads `valid_until` |
| C-15 | ARCHITECTURE: "Every model call goes through `llm.Gateway`" | True for the pipeline. The embedder (`HttpEmbedder`) and the benchmark call their servers directly and are not logged |

---

## 15. What is not built yet

By roadmap phase, with an honest completion estimate for each (opinion).

| Phase | Scope | Built | Missing | Rough share done |
| --- | --- | --- | --- | --- |
| 0 Foundations | Schema, DB, anchor, maths, Arbiter, CLI, benchmark | All code | Running the benchmark on two models; committing a results summary; aligning the benchmark prompt with the distiller | ~85% |
| 1 Manual pipeline | `ingest`, `show`, `search` | All code | Real-model run; 50 sources on one charter; hand audit (≥ 95% verbatim quotes, ≥ 85% faithful claims); defects D-1 to D-8 | ~60% |
| 2 Judge + calibration | Judge, lineage merging, reliability, live Belnap states | Judge, D9 (passages), D10, D14 | AGAINST evidence (D-1); 200 hand-labelled pairs; calibrating `judge_floor`, τ0, γ and weights; dataset/author/citation lineage; idempotent re-ingest (D-4) | ~35% |
| 3 Loop + MCP | Leased queue, Steward, Forager workers, budgets, kill switch, day/night scheduler, GPU yield, MCP server with `brief()` | `brief()` itself; the `tasks` table; the $0 cloud refusal | Workers, leases, scheduler, kill switch, watchdog, Steward logic, MCP server, llama-swap integration, GPU yield, retries, per-day/week caps | ~10% |
| 4 Red team + verification | Fallacy red-teamer, network-less Docker verifier, cloud escalation, Synthesist | DERIVED genes at the API level; the rejection-reason enum | Everything else | ~5% |
| 5 Hardening + human layer | Librarian, Obsidian, digest, Anki, inbox, backups, metrics, embedding migration | Digest | Everything else | ~5% |

Overall, by effort rather than by line count, the project is roughly **20–25% of the way to the full 24/7 vision**, and roughly **60–70% of the way to a useful supervised library** (a tool the owner runs by hand that answers questions from a vetted, connected store). That second target is the one worth aiming at first (Section 19).

---

## 16. Risks

### 16.1 Technical

| Risk | Likelihood | Impact | Notes and mitigation |
| --- | --- | --- | --- |
| Local 12–14B models extract unfaithful claims or bad quotes on messy web/PDF text | Medium–high | Fatal to autonomy, survivable for a supervised tool | This is the make-or-break unknown. The anchor check catches invented quotes but not a real quote attached to a claim it does not support ("faithfulness"). Only the hand audit measures this. Mitigation: benchmark first; try a 30B-A3B MoE; keep the human in the loop |
| The local judge cannot separate SAME / REFINES / CONTRADICTS reliably | High | Duplicates or wrong merges; contradictions missed | SELF_CRITIQUE item 4 already names this. D14 limits damage (unsure → RELATED). Cross-encoder rerankers or NLI models may beat an LLM judge for SAME/CONTRADICTS and are cheap on CPU; not yet considered in the code |
| llama.cpp API incompatibilities (D-6), model server flag churn | High (D-6) | Blocks the first run | Trivial fix once observed |
| SQLite + `sqlite-vec` brute-force KNN at scale | Low for years | Slower search | Brute force is fine to about a million 1024-d vectors; a single user will not reach that soon |
| Embedding model change | Medium over time | Needs a migration that does not exist | Phase 5 item; dimension is fixed in the schema |
| PDF and HTML extraction quality | High | False VIKALPA rejections; lost claims | Measure; consider a better extractor (e.g. trafilatura for HTML, a layout-aware PDF tool) |

### 16.2 Epistemic

| Risk | Notes |
| --- | --- |
| Faithfulness, not just anchoring | A verbatim quote proves the words exist, not that the thesis follows from them. A distiller can quote "X improved recall in one setting" and claim "X improves recall". The scope field and the hand audit are the only defences now; an entailment check (quote ⇒ thesis) by a second model or an NLI classifier would be a strong addition |
| Weak connections satisfy D1 | Two unverified hypotheses linked to each other, or a judge failure creating EXTENDS, both count as "connected". D1 currently adds less rigour than it appears to |
| Lineage detection undercounts and overcounts | Over-merging famous quotes (documented) and under-merging the same study reported in different words (not detected: D9's "same dataset/experiment" half is missing). The second error is the dangerous one: it inflates support |
| Uncalibrated numbers | All weights, thresholds and τ/γ are guesses. The docs say so honestly. They are only safe as rankings until Phase 2 |
| Self-reinforcement | Agent-written text never becomes a source (good). But the Steward (planned) choosing what to forage based on what is already in the library is a filter bubble risk; R3/R4/R8 are the planned counterweights and none is built |
| Topic taxonomy is model-chosen | The distiller invents taxonomy paths, so mass can fragment across synonyms ("sci.ml.retrieval" vs "cs.ir.search") and the gravity rule silently weakens. A controlled vocabulary (SELF_CRITIQUE item 6) is needed before mass means anything |

### 16.3 Operational and safety (for the 24/7 phase)

* No workers, leases, kill switch, watchdog or scheduler exist yet, so there is nothing unsafe running, but also nothing autonomous.
* SSRF (D-10) and prompt injection are the two real security risks once URLs come from scraped content. Injection is mitigated well in design (tool-less distiller, grammar, quote anchoring, data wrapping), but local models are known to follow injected instructions anyway; SELF_CRITIQUE item 14 rightly concludes the worst case is a quoted, single-lineage hypothesis.
* Spend: cloud is hard-off. When enabled, the cap check is per call and per month, not per day or week as the plan says, and it can be overshot by the size of one call.
* Legal: robots.txt and pacing are respected; licences are not recorded (`license` column always empty), and raw pages are stored permanently in the blob store. For a private, local library this is normal practice; it would matter if the library were ever published.

### 16.4 Project and governance

| Risk | Notes |
| --- | --- |
| Scope is very large for one person | Six phases, nine agent roles, an MCP server, exports, a scheduler, a sandbox. The plan's own time estimates (8–11 weeks to Phase 4) are labelled optimistic in SELF_CRITIQUE item 9; this audit agrees and would roughly double them for part-time work |
| Design runs ahead of evidence | 14 rulings and 10 refinements were made before a single real page was processed. Several rulings may need revisiting once real data shows where the errors actually are |
| Persona-led decisions | Useful as a consistent design voice, but the persona's rulings were never tested against alternatives, and two seams with the code failed (Section 5.1). The owner retains the veto; it should be exercised on D1 at least |
| Nothing merged, no CI | Work can be lost or diverge; a public visitor sees an empty project |
| Dependence on the owner's attention | The last request (merge the PRs) has been open for two weeks. Many gates require the owner's hand labels (50 sources, 200 pairs). If the owner cannot spend several hours on labelling, Phases 1 and 2 cannot pass |

---

## 17. Requirements traceability: the owner's asks versus reality

| # | Ask (Section 2.1) | Status | Comment |
| --- | --- | --- | --- |
| G1 | Local or cloud LLMs | Built (gateway), untested with a real model | Cloud is deliberately off |
| G2 | Circular 24/7 research | Not built | Supervised, one-shot ingest only |
| G3 | Severity rises with mass | Built (gravity rule) | Needs a controlled taxonomy to mean anything |
| G4 | True, accurate, relevant, therefore interconnected | Built in the gate; D-1 and D-2 undermine it in practice | The philosophical heart of the request, and the most carefully designed part |
| G5 | Labelled, dated, understood, connected | Mostly built (frames, states, events, typed edges); validity dates not filled | Good |
| G6 | No repeats, no loss of nuance | Built (SAME/REFINES), but D-4 and D-5 break it | Fixable |
| G7 | Rubbish labelled rubbish | Built (reasons, tombstones), but D-3 over-blocks | Fixable |
| G8 | Genes of research, chronological | Built (versions, events); trails not built | Small job |
| G9 | End the context battle | `brief` built; MCP server not built | **Highest payoff per hour of remaining work** |
| G10 | Easy memorisation of multi-step ideas | Not built (digest only) | The owner's original pain; D12 cards, Anki export and the capture inbox are all unbuilt. Arguably the most neglected requirement relative to its importance |
| G11 | SQLite + vectors ("raw akashic records") | Built | Solid |
| G12 | Safe 24/7 hive with local/cloud choice | Not built (design is thorough) | Phase 3–4 |
| G13 | Efficient on 4070 + 96 GB within API limits | Designed carefully; not measured | Benchmark pending |
| G14 | Vedic / esoteric / Indian logic, labelled | Built as frames and named heuristics | Done well, with honest status labels |
| G15 | Steiner persona steers design | Done (rulings recorded) | See Section 5.1 caveat |

---

## 18. Effort to finish (estimates)

These are opinions for one person working part-time with AI coding help, and they assume the owner can spend the labelling hours the gates need. They are deliberately less optimistic than the plan's.

| Milestone | Work | Estimate |
| --- | --- | --- |
| M0: Merge and fix | Merge #1 and #2; add CI (GitHub Actions running pytest); fix D-1 to D-9 with tests; align the benchmark prompt | 3–5 days |
| M1: First real run | Install the WSL2 / llama.cpp stack; run the benchmark on two models; ingest 10 sources on the D8 charter; owner audits every quote and claim | 1–2 weeks (half of it setup and owner time) |
| M2: Useful supervised library | MCP server exposing `brief`, `search`, `show`, `add_hypothesis`; capture inbox; `link`, `edge`, `merge-lineage` commands; controlled taxonomy; 50-source audit (Phase 1 gate) | 2–3 weeks |
| M3: Calibrated judge | 200 hand-labelled pairs; tune `judge_floor` and weights; try an NLI/cross-encoder for SAME/CONTRADICTS; entailment check for faithfulness (Phase 2 gate) | 2–4 weeks, dominated by labelling |
| M4: Supervised loop | Leased task queue, Steward, Forager worker, kill switch, scheduler, GPU yield, retries; run overnight supervised (Phase 3 gate) | 3–5 weeks |
| M5: Red team, verifier, synthesis | Phase 4 | 4–8 weeks |
| M6: Hardening and human layer | Phase 5 (Librarian, Obsidian, Anki, backups, metrics, migrations, 30 days running) | Open-ended, 2+ months |

**M0–M2 (about 4–7 weeks) gets the owner a working tool.** M3 decides whether autonomy is viable. M4–M6 (another 3–5 months) is the full vision.

---

## 19. Verdict in full

### 19.1 Reasons it is worth finishing

1. **The central design is right.** "The database is the mind, the model is a small checkable worker" is the correct response to context-window limits, and the project already has a working implementation of the hard-to-get-right core: verbatim quote anchoring, independent-lineage counting, four-valued truth, a gravity rule that does what the owner asked, single-writer storage with a full audit trail.
2. **The code is good.** Small modules, clear names, honest docstrings, strict validation of model output, no hidden network calls, cloud off by default, privacy handled. Every defect found is a fixable seam, not a rotten foundation. A reviewer can read the whole thing in an afternoon.
3. **The self-critique culture is real.** `docs/SELF_CRITIQUE.md` names most of the risks this audit found, and two real bugs were caught and fixed before the PRs opened. The labelling of esoteric and borrowed ideas by epistemic status is unusually disciplined.
4. **A useful product exists one short step away.** Even if the 24/7 hive never ships, a supervised `ingest` + `brief` + MCP server gives the owner exactly what the brief asked for first: a vetted, connected, compact store that any AI session can load instead of the owner retyping their reasoning.
5. **The remaining unknowns are measurable cheaply.** Whether local models are good enough can be answered with one benchmark run and a ten-source audit, a week or two of effort, before any further large investment.

### 19.2 Reasons for caution

1. **The make-or-break assumption is untested.** If local models cannot extract faithful claims and judge sameness reliably, the autonomous vision fails and only the supervised tool survives. No evidence either way exists yet.
2. **Design has outrun evidence.** A lot of conceptual machinery (frames, rulings, refinements, lenses) has been built on top of an extraction step nobody has seen work. Some of it will need to change once real errors are visible.
3. **Five serious defects** sit exactly where the core promises live (refutation, connection, dedup, rejection, refinement). They must be fixed before any audit numbers mean anything.
4. **The scope is very large** for one part-time person, and the gates depend on hours of the owner's hand labelling.
5. **Nothing is merged, there is no CI, and the project has been idle for two weeks.** Momentum is the cheapest thing to lose and the hardest to regain.

### 19.3 Recommendation

**Finish it, re-scoped into two stages with a decision point between them.**

**Stage A: "Useful supervised library" (M0–M2, about 4–7 weeks).**

1. Merge PR #1 then PR #2. Add a GitHub Actions workflow running `pytest`.
2. Fix D-1 to D-9, each with a test. Align the benchmark with the production distiller.
3. Run the benchmark on two local models (a 14B dense model and a 30B-A3B MoE). Commit the summary. This closes the Phase 0 gate honestly.
4. Ingest 10 sources on the D8 charter by hand and audit every stored quote and claim. Record quote fidelity and claim faithfulness.
5. Ship a minimal MCP server (`brief`, `search`, `show`, `add_hypothesis`) and a capture inbox. Start using it in real AI sessions.

**Decision point.** Look at three numbers from step 4 and from real use of the MCP server:

* quote fidelity (target ≥ 95%),
* claim faithfulness (target ≥ 85%),
* whether briefs actually replace retyping in day-to-day sessions.

**Stage B: autonomy (M3–M6), only if Stage A's numbers are met or clearly within reach.** Calibrate the judge on labelled pairs, then build the supervised loop, then red-team and synthesis.

**Kill or downgrade criteria.** If, after honest prompt and model tuning, quote fidelity stays under about 90% or claim faithfulness under about 75% with any local model the hardware can run, **stop the 24/7 ambition** (or wait for better local models) and keep the system as a supervised, human-verified library with cloud help on demand. That version is still valuable and is mostly built.

### 19.4 One-paragraph verdict for a reviewer

This is a thoughtfully designed, cleanly implemented, honestly documented early-stage project whose core idea is correct and whose code is about two thirds of the way to a useful supervised research library, but only a fifth of the way to its 24/7 autonomous goal. It has never touched a real model, it carries five fixable defects in exactly the places its central promises live, and nothing has been merged. It is worth finishing if the next effort goes into fixing those defects and measuring extraction quality on real sources, rather than into more design or more features; it should be scaled back to a supervised tool if local models prove unable to extract faithful claims.

---

## 20. Open questions and unresolved decisions

### 20.1 Needs the owner (a persona cannot answer these)

| # | Question | Current default |
| --- | --- | --- |
| O1 | Merge PRs #1 and #2? | Unmerged since 2026-10-26 |
| O2 | Monthly cloud budget, if any, and per provider | $0: cloud disabled (A2) |
| O3 | API keys or subscriptions only? | Loop uses API keys only; subscriptions only in supervised sessions (A3) |
| O4 | CPU model (AVX-512 or not), for the embedder choice | Assume no AVX-512 (A4) |
| O5 | Is the PC shared or gamed on? How should the daemon yield the GPU? | Assume shared; yield on demand (A5) |
| O6 | How many hours can the owner give to hand labelling (10–50 source audit, 200 judge pairs)? | Unknown. This is the binding constraint on Phases 1–2 |
| O7 | Should the owner overturn or amend D1 given D-2 (lone well-evidenced claims stay hypotheses)? | D1 as ruled |
| O8 | Which reading surface first: Obsidian, a web dashboard, or MCP-only? | Obsidian first (A7); this audit recommends MCP first |
| O9 | Is it acceptable that book- and testimony-based topics corroborate very slowly (Section 9.3)? | Yes, by D10 |

### 20.2 Design questions still open (could be decided by the design process)

* How exactly to detect "same dataset / same experiment / same author group" for D9 (citation graphs, DOIs, dataset names, author overlap).
* Whether an NLI model or cross-encoder should replace or back up the LLM judge for SAME / CONTRADICTS.
* Whether to add an entailment check (quote ⇒ thesis) for faithfulness, and with which model.
* The controlled taxonomy: who maintains it, how new branches are admitted, how synonyms map.
* What counts as "connection" under D1: should links to unverified hypotheses count; should CONTRADICTS count; should a judge failure ever count.
* How DERIVED genes get created (the Synthesist), and how their predictions are tested (who resolves them, when).
* Trails: build from versions, SUPERSEDES edges, or events.
* Half-life intervals per taxonomy branch (R7) and the "living review" for AXIOMs (S10).
* How the owner's resonance mark should affect foraging priority in the loop (D5 says priority only, but the Steward does not exist).

---

## 21. Appendices

### 21.1 Reproduce this audit's checks

```bash
git clone https://github.com/rawdogin69x-dev/333-Multi-Triangular-Recursive-Research-Framework..git akashic
cd akashic
git fetch origin phase0-scaffold phase1-pipeline

# PR #1
git checkout origin/phase0-scaffold
python -m venv /tmp/v0 && /tmp/v0/bin/pip install -e ".[dev]" && /tmp/v0/bin/pytest -q     # 29 passed

# PR #2 (use a fresh venv, or the editable install from PR #1 shadows the code)
git checkout origin/phase1-pipeline
python -m venv /tmp/v1 && /tmp/v1/bin/pip install -e ".[dev]" && /tmp/v1/bin/pytest -q     # 65 passed
```

The probes in Section 12 can be rebuilt from `tests/test_pipeline.py`: reuse its fixture (fake model, hash embedder, mock HTTP client), set `judge_floor` to 0.8, and vary only the quotes and the number of ingests as described in the table.

### 21.2 File inventory (PR #2)

| Path | Lines | Role |
| --- | --- | --- |
| `akashic/store.py` | 454 | Arbiter write API, admission steps, truth maintenance |
| `akashic/forage.py` | 275 | Fetching, canonical URLs, blob store, text extraction, signals |
| `akashic/lifecycle.py` | 227 | Evidence maths, gravity, state machine, reliability |
| `akashic/migrations/0001_init.sql` | 205 | Schema v1 |
| `akashic/cli.py` | 203 | Command line |
| `akashic/ingest.py` | 159 | Pipeline orchestration |
| `akashic/distill.py` | 136 | Claim extraction prompt, grammar, parser, chunking |
| `akashic/llm.py` | 116 | Model gateway, budgets, logging |
| `akashic/config.py` | 95 | Tunable constants |
| `akashic/anchor.py` | 92 | Quote and number checks |
| `akashic/db.py` | 91 | Connection, pragmas, migrations, virtual tables |
| `akashic/brief.py` | 82 | Folded, token-budgeted briefs |
| `akashic/maintenance.py` | 75 | Rückschau replay and daily digest |
| `akashic/judge.py` | 69 | Pairwise judge prompt and parser |
| `akashic/search.py` | 66 | Hybrid FTS5 + vector search |
| `akashic/embed.py` | 60 | HTTP embedder and test hash embedder |
| `akashic/ids.py` | 24 | UUIDv7 and timestamps |
| `bench/bench_models.py` | 123 | Local model benchmark |
| `tests/*.py` | 703 | 65 tests |
| `docs/*.md` | ~290 | Architecture, decisions, roadmap, assumptions, self-critique, setup |
| `config/*.example.yaml` | 75 | Example config and charters |
| `Argon-research.md` | 332 | First design draft (superseded) |

### 21.3 Glossary

| Term | Meaning here |
| --- | --- |
| Gene | One atomic, scoped proposition with its reason, example, application and version history |
| Evidence row | A gene × source link with a stance (FOR / AGAINST), an evidence type and a verified verbatim quote |
| Lineage | A group of sources that share an origin (same passage, and in future the same dataset, experiment or authors); counts once |
| Support / against | Noisy-OR of the strongest `weight × reliability` per lineage on each side; a ranking, not a probability |
| Mass (M_d) | Summed support of settled genes in a topic |
| Gravity rule | Required lineages and support rise with topic mass |
| Frame | The kind of claim: EMPIRICAL, FORMAL, ATTRIBUTED, SPECULATIVE, METAPHOR, PHENOMENOLOGICAL |
| VIKALPA | Rejection: no verbatim quote ("words without a referent", from the Yoga Sūtra) |
| Charter | A research question with scope, priority and a definition of done |
| Arbiter | The single writer of knowledge tables (`Store`) |
| Rückschau | Nightly replay of queued re-checks, newest first |
| Brief | A compact, lossy, token-budgeted summary of a topic's best genes and their neighbourhood, with ids |
| Rudolf | The Steiner-method design persona that decides design questions; an interpretive lens, not a factual source |
| D1–D14, S1–S10, R1–R10 | Recorded design rulings and refinements (Section 10) |
| Gate | A measurable condition a phase must pass before the next starts |
