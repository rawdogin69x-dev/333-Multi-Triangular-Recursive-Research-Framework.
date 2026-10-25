# Self-critique of the redesign

Weak points in our own plan, ranked by how much damage they could do, with the mitigation chosen.

1. **Lineage independence is approximated by root domain.** Syndicated news, mirrors, and papers
   sharing one dataset look independent but are not. This inflates support.
   *Mitigation:* lineages can be merged by hand; Phase 2 adds citation and near-duplicate-text
   detection across sources (shared paragraphs → same lineage). Err towards merging.
2. **Source reliability can become a popularity contest.** If `r` is learned from whether a source
   agrees with what is already settled, contrarian-but-right sources are punished.
   *Mitigation:* update `r` only from EXECUTED results, human audits, or a refutation that
   itself reached CORROBORATED with lineages independent of the source being scored.
3. **Noisy-OR assumes independence and calibrated weights.** The weights in `config` are guesses.
   *Mitigation:* Phase 2 calibrates on a hand-labelled set; until then, treat `support` as a
   ranking, not a probability. The docs say "support", never "probability".
4. **The LLM judge becomes the new single point of failure.** A 14B-class model separating SAME
   from REFINES will be noisy. *Mitigation:* Phase 2 gate requires ≥ 85% agreement with your
   labels; when the judge is unsure, keep both genes and link them `RELATED` (cheap to merge
   later, impossible to un-merge).
5. **Quote anchoring favours extractive claims.** A claim that spans three paragraphs has no
   single verbatim quote. *Mitigation:* allow several quotes per claim (one evidence row each);
   cross-paragraph synthesis belongs in DERIVED genes, which carry premises instead.
6. **Mass by taxonomy depends on good taxonomy labels.** Mislabelled genes dodge or inflate the
   gravity rule. *Mitigation:* a controlled vocabulary (Pāṇini-style: compact, rule-based) and a
   Librarian check that flags genes whose embedding sits far from their taxonomy's centroid.
7. **Dense topics may stagnate.** With k = 4 the newest results in a crowded topic wait longest.
   *Mitigation:* `REFINES` updates an existing gene without a fresh k-lineage hunt, and k is
   capped at 4.
8. **One SQLite writer could bottleneck.** *Expected fine:* writes are small and batched, reads
   use WAL readers. Revisit only if the queue backs up.
9. **Time estimates in the roadmap are optimistic.** They assume AI-assisted coding and no
   detours. Treat gates, not dates, as the commitment.

## Bugs caught so far

- A once-settled gene that slipped to `CONTESTED` could then be refuted with one fewer lineage
  than an entrenched gene, sidestepping the "extraordinary claims" rule. Fixed via
  `ever_promoted` (derived from `tau_at_promotion`) and covered by
  `test_entrenched_gene_needs_extra_lineage_to_fall`.
- A gene's own support counted towards the topic mass it was judged against, so a settled
  gene raised its own bar on every re-check (caught in code review). `Store.reassess` now subtracts it.
