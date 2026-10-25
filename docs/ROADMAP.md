# Roadmap

Gates, not dates, are the commitment. Autonomy arrives only after the gate is calibrated.

| Phase | Builds | Gate to pass |
| --- | --- | --- |
| **0 Foundations** (this PR) | Schema v1, DB + migrations, anchor check, evidence and gravity maths, Arbiter write API, CLI, model benchmark harness | Tests green; benchmark results for 2+ local models committed as a summary |
| **1 Manual pipeline** | `akashic ingest <url\|pdf>`: forage → distill (template + quotes) → anchor → embed → store; `show`, hybrid `search` | 50 sources on one charter; ≥ 95% of stored quotes verbatim; ≥ 85% of claims faithful (hand audit) |
| **2 Judge + calibration** | SAME/REFINES/CONTRADICTS/RELATED/NEW judge, lineage merging, reliability updates, Belnap states live | Judge ≥ 85% agreement on 200 hand-labelled pairs; re-ingesting the same 50 sources creates no new genes |
| **3 Loop + MCP** | Leased task queue, Steward + Forager workers, budgets, kill switch, day/night scheduler, GPU yield; Akashic MCP server with `brief()` | 3 unattended nights, no crash loops, spend within cap; an AI coding session answers from `brief()` alone |
| **4 Red team + verification** | Fallacy-checklist red-teamer, network-less Docker verifier, cloud escalation for CONTESTED, Synthesist with DERIVED genes | ≥ 80% of 30 planted false claims end REFUTED/REJECTED; derived genes fall when a premise falls |
| **5 Hardening + human layer** | Librarian (clusters, centrality, AXIOM), Obsidian export, daily digest, Anki export, capture inbox, backups + restore tests, metrics, embedding migration | 30 days running; weekly audit precision ≥ 90%; duplicate rate < 2% |
