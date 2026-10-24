# Architecture

**The database is the mind; the LLM is a stateless worker.** Knowledge lives in one SQLite file
(relations + FTS5 + `sqlite-vec` vectors) beside a content-addressed blob store of raw sources.
Models only do small, checkable jobs over small slices of it.

This replaces the admission gate in `Argon-research.md`. Argon's gate has three fatal flaws:
on an empty library it can never admit anything (score ≈ 0.02 vs threshold 0.35), it treats
"close to two topics" as corroboration, and it discards independent confirmations as redundant.

## Admission: three questions, in order

1. **Anchored?** (deterministic) Every claim carries a verbatim quote that must match the raw
   source after normalisation. Numbers in the thesis must appear in a quote. Failures are
   `REJECTED` with a named reason (`VIKALPA`, `NUMBER_MISMATCH`). See `akashic/anchor.py`.
2. **New?** (vector + FTS search, then a local LLM judge, Phase 2) For each near neighbour:
   `SAME` → add evidence to the existing gene (corroboration), `REFINES` → new version,
   `CONTRADICTS` → new gene + edge, `RELATED` → new gene + typed edge, `NEW` → new hypothesis.
3. **True?** (evidence maths) Evidence rows are grouped into independent *lineages* (by default
   the root domain). The strongest row per lineage and stance counts once:

   ```
   support = 1 − Π (1 − w_i · r_i)   over lineages FOR
   against = 1 − Π (1 − w_j · r_j)   over lineages AGAINST
   ```

   `w` is the evidence-type weight (EXECUTED 0.95 … ANALOGY 0.20), `r` is source reliability.
   Truth is four-valued: SUPPORTED, REFUTED, CONTESTED (both), UNKNOWN (neither).

## The gravity rule ("severity rises with mass")

Mass is per topic (the first two taxonomy levels): `M_d = Σ support` of settled genes there.
Promotion from HYPOTHESIS to CORROBORATED needs

```
k_req = min(4, 2 + floor(log10(1 + M_d)))   independent lineages
support ≥ τ_d = min(0.95, 0.60 + 0.03 · ln(1 + M_d))
```

So a new topic needs 2 lineages, a topic with 10 settled genes needs 3, one with 100 needs 4.
Overturning a once-settled gene needs `k_req + 1` lineages against. See `akashic/lifecycle.py`.

## Lifecycle

`CANDIDATE → HYPOTHESIS → CORROBORATED → AXIOM`, with `CONTESTED`, `DERIVED`, `REFUTED`,
`REJECTED`, `SUPERSEDED`. Nothing is deleted. Every change is a row in `events`, and a change
to a gene queues `RECHECK` tasks for genes that `DEPENDS_ON` or are `DERIVED_FROM` it
(truth maintenance).

## Frames

Every gene has a frame: `EMPIRICAL`, `FORMAL`, `ATTRIBUTED` (what a person, text or tradition
holds), `SPECULATIVE`, `METAPHOR`. `SPECULATIVE` and `METAPHOR` genes never rise above
HYPOTHESIS. Links across frames use `PARALLELS`, so traditional and esoteric material can be
studied beside empirical work without lending it confidence.

## Lenses from Indian logic (status-labelled)

| Lens | Status | Used for |
| --- | --- | --- |
| Pramāṇas (Nyāya, Mīmāṃsā) | established philosophy, design heuristic | `evidence_type` values |
| Five-member syllogism | established, heuristic | gene template: thesis, reason, example, application, conclusion |
| Hetvābhāsa (five fallacies) | established, heuristic | red-team checklist, `RejectReason` names |
| Yoga Sūtra vṛttis (*vikalpa*, *smṛti*) | established, heuristic | unanchored text = vikalpa; LLM recall without source = smṛti, never evidence |
| Syādvāda | established, heuristic | mandatory `scope` on every gene |
| Catuṣkoṭi ≈ Belnap–Dunn four-valued logic | established | SUPPORTED / REFUTED / CONTESTED / UNKNOWN |
| "Vertically and crosswise" (*Vedic Mathematics*, 1965) | arithmetic valid; Vedic origin not supported | metaphor: trace down to the primary source, confirm across an independent lineage |
| Akashic records | not supported as physics | metaphor: the append-only raw archive |

## Runtime (target)

Python daemon in WSL2. Role workers (Steward, Forager, Distiller, Judge, Red-teamer, Verifier,
Synthesist, Librarian) pull leased tasks from `tasks`; only the Arbiter (`akashic/store.py`)
writes knowledge tables. One GPU means one resident LLM: a day model for extraction and judging,
a large MoE with experts in system RAM at night. Cloud APIs only for CONTESTED genes and for
writing verification tests, under hard spend caps; tests run in a local, network-less container.

See `docs/ROADMAP.md` for phases and `docs/ASSUMPTIONS.md` for the defaults chosen so far.
