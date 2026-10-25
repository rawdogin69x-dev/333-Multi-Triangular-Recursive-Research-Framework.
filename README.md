Plan research and write a system framework which can function with local or cloud LLM + carefully designed circular research system, to continously append and extend deep research, in a way that adds to general knowledge carefully, 24/7. The math might be intuited by something approximating : as research data increases, so must the severity, interconnectedness and accuracy be. All research must be accurately labelled, dated, understood, connected. Without adding any superfluous or repeated content but still not sacrificing accuracy, critical and nuanced thinking and clarity. 'Mass can only increase if it is TRUE, ACCURATE, RELEVANT, AND THER FOR INTERCONNECTED. Big issue of having extremely multi stepped ideas and research that I can memorise and intuit easily. But laborious to re type and manage an ever losing context battle. Even 1M isnt enough to understand things in details the way we use tokens now and their effiency. Atleast to the same human nuanced level.

So recursive accurate and triangularine through connection . This will promote a good library of quality that grows when it needs to or omits rubbish or labels rubbish rubbish and treasure treasure.

The knowledge in the system should grow multifaceted. Visually, raw sqlite +/ our vectorized database format (RAW akashic records). So we create entire genes of research not just raw book we never finish. But chronological and implementable insights and nuance deep critical juice. 

We must also find a safe way to have an auto agent 24/7 do things or  source pick etc and manage which local or cloud agent and how the hive thinks (multi agents). Efficiency, 4070rtx 96gb ddr 5 ram +  API limitations/codex/claude/antigravity.

---

## Status

Phase 0 (foundations) is done and Phase 1 (manual pipeline) is scaffolded: ingest, distil, anchor,
judge, search, brief and a daily digest all run end to end offline in tests. They have not yet
run against real local models. `Argon-research.md` was the first design draft; its admission
gate is replaced by the evidence-based design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

- [Architecture](docs/ARCHITECTURE.md): admission law, gravity rule, lifecycle, frames
- [Decisions](docs/DECISIONS.md): design rulings D1–D14 and why
- [Roadmap](docs/ROADMAP.md): phases and the gate each must pass
- [Assumptions](docs/ASSUMPTIONS.md): defaults in force until changed
- [Self-critique](docs/SELF_CRITIQUE.md): known weak points and mitigations
- [Setup](docs/SETUP.md): WSL2, llama.cpp, Python, benchmark

```bash
uv venv && uv pip install -e ".[dev]" && .venv/bin/pytest -q
.venv/bin/akashic init
.venv/bin/akashic gravity sci.ml.rag
.venv/bin/akashic charters --load config/charters.example.yaml
.venv/bin/akashic ingest https://example.org/paper notes.pdf --charter <id>   # needs llama.cpp + embedder running
.venv/bin/akashic search "hybrid retrieval" --no-vectors
.venv/bin/akashic brief "hybrid retrieval"     # folded, token-budgeted brief for an AI session
.venv/bin/akashic digest                       # what changed in 24 h
.venv/bin/akashic rueckschau                   # replay queued re-checks
.venv/bin/akashic resonate <gene> 2            # your felt mark; changes priority, never truth
```
