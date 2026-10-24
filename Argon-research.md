To build a 24/7 autonomous research engine that escapes the "context degradation trap" while preventing database bloat, you cannot treat an LLM's context window as your memory. Even a 1M+ token window suffers from middle-context attention decay and quadratic compute overhead, turning nuanced multi-step intuition into diluted summaries.

Instead, the architecture must invert the relationship: **the database is the mind, and the LLM is a stateless CPU executing atomic cognitive operations over small, hyper-dense subgraphs.**

This system framework—**Epistemic Gravity & Genetic Knowledge Graph (EG-GKG)**—enforces a strict mathematical admission gate, unifies relational and vector storage into a single portable SQLite file ("Raw Akashic Records"), and orchestrates your local **RTX 4070 (12GB VRAM) + 96GB DDR5 RAM** alongside cloud APIs (Claude, Codex, Antigravity) safely around the clock.

---

## 1. The Mathematical Law: Epistemic Gravity & The Admission Gate

To satisfy the axiom that *"as research data increases, so must the severity, interconnectedness, and accuracy,"* the system treats knowledge mass ($M$) not as volume of text, but as verified structural density. Every candidate insight $c$ must pass a dynamic threshold $\tau(M_t)$ that scales logarithmically with the current verified mass of the database $M_t$:

$$\tau(M_t) = \tau_0 + \gamma \ln(1 + M_t)$$

As the library grows, it becomes progressively harder for a new piece of information to enter as "Treasure." A candidate node $c$ is evaluated by an **Admission Score** $S(c)$:

$$S(c) = \frac{V(c) \cdot C_{\text{tri}}(c)^\alpha \cdot I_{\text{nov}}(c)^\beta}{1 + \lambda R_{\text{max}}(c)}$$

* **$V(c) \in [0, 1]$ ( Epistemic Validity):** Deterministic verification score based on primary source execution, cryptographic/API signature proof, or empirical reproducibility. Unverified claims default near $0$.
* **$C_{\text{tri}}(c)$ (Triangulation Coefficient):** A node cannot exist in isolation. It must form a closed epistemic triangle by connecting to at least two independent, non-collinear existing clusters ($u, v$) in the graph where the shortest path $d_{\text{graph}}(u, v) \ge 2$:

$$C_{\text{tri}}(c) = \sum_{(u,v) \in E_{\text{link}}} \text{sim}(c, u) \cdot \text{sim}(c, v) \cdot \mathbb{I}\left(d_{\text{graph}}(u, v) \ge 2\right)$$


* **$I_{\text{nov}}(c)$ (Information Gain / Nuance):** Measures the structural surprise or resolution of an existing contradiction, preventing obvious truisms.
* **$R_{\text{max}}(c)$ (Redundancy Penalty):** The maximum cosine similarity against existing vector embeddings in `sqlite-vec`:

$$R_{\text{max}}(c) = \max_{x \in \mathcal{G}} \left( \frac{\mathbf{e}_c \cdot \mathbf{e}_x}{\Vert{}\mathbf{e}_c\Vert{} \Vert{}\mathbf{e}_x\Vert{}} \right)$$



If $R_{\text{max}}(c) \ge 0.88$ without introducing a novel contradiction edge, the denominator spikes and crushes $S(c)$.

### The Tri-State Routing Verdict

1. **TREASURE ($S(c) \ge \tau(M_t)$):** Committed to the core `epistemic_genes` table, updating graph edges and increasing $M_{t+1}$.
2. **SYNTHESIS MERGE ($0.5 \cdot \tau(M_t) \le S(c) \text{ and } R_{\text{max}}(c) \text{ is high}$):** Does not create a new node. Instead, it triggers a versioned mutation on the existing node $x$, appending only the delta/nuance and adding the new source citation.
3. **RUBBISH ($S(c) \text{ falls below threshold}$):** Not deleted—because deleting bad sources causes the 24/7 agent to re-scrape and re-evaluate them tomorrow. Instead, its hash, URL, and failure reason are written to the **Negative Knowledge Graveyard (`rubbish_tombstones`)**, immunizing the hive against future wasted compute.

---

## 2. The "Akashic" Storage Engine: Unified SQLite + `sqlite-vec` + JSONL

Avoid splitting your brain across external vector servers (Pinecone/Qdrant) and relational databases. Using pure **SQLite** in `WAL` (Write-Ahead Logging) mode paired with the C-native **`sqlite-vec`** extension and **FTS5** (Full-Text Search) keeps your entire relational graph, exact keyword index, and float32/int8 vector embeddings inside **one single, ACID-compliant local file** (`akashic_core.db`), backed by an immutable append-only `.jsonl` audit log.

### The "Gene" Schema (`akashic_core.sql`)

Instead of storing "books" or raw markdown dumps, the database stores **Epistemic Genes**—atomic, self-contained units of insight with strict provenance and typed causal edges:

```sql
PRAGMA journal_mode = WAL;
PRAGMA synchronous = NORMAL;
PRAGMA foreign_keys = ON;

-- 1. Epistemic Genes: Atomic units of verified knowledge
CREATE TABLE epistemic_genes (
    gene_id TEXT PRIMARY KEY,              -- UUIDv7 (time-ordered)
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    domain_taxonomy TEXT NOT NULL,         -- e.g., 'sec.auth.oauth_flows'
    claim_atomic TEXT NOT NULL,            -- Crisp, zero-fluff core proposition
    critical_nuance TEXT NOT NULL,         -- Edge cases, constraints, why standard views fail
    actionable_implementation TEXT,        -- Code pattern, test vector, or concrete protocol
    validity_score REAL NOT NULL,          -- V(c)
    triangulation_score REAL NOT NULL,     -- C_tri(c)
    admission_mass REAL NOT NULL,          -- S(c) at time of ingestion
    status TEXT CHECK(status IN ('TREASURE', 'HYPOTHESIS', 'DEPRECATED')) DEFAULT 'TREASURE',
    version INTEGER DEFAULT 1,
    parent_mutation_id TEXT REFERENCES epistemic_genes(gene_id)
);

-- 2. Synapses: Directed Graph Edges for Triangulation & Subgraph Traversal
CREATE TABLE gene_synapses (
    edge_id TEXT PRIMARY KEY,
    source_gene_id TEXT NOT NULL REFERENCES epistemic_genes(gene_id),
    target_gene_id TEXT NOT NULL REFERENCES epistemic_genes(gene_id),
    relation_type TEXT CHECK(relation_type IN (
        'CORROBORATES', 'CONTRADICTS', 'EXTENDS', 'DEPENDS_ON', 'REFUTES', 'IMPLEMENTS'
    )) NOT NULL,
    weight REAL DEFAULT 1.0,
    evidence_note TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(source_gene_id, target_gene_id, relation_type)
);

-- 3. Provenance Ledger: Strict Dated Attribution
CREATE TABLE provenance_ledger (
    source_id TEXT PRIMARY KEY,
    gene_id TEXT NOT NULL REFERENCES epistemic_genes(gene_id),
    uri_or_ origin TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    captured_at DATETIME NOT NULL,
    raw_artifact_jsonl_offset INTEGER NOT NULL -- Pointer to immutable raw JSONL archive
);

-- 4. Rubbish Tombstones: Negative Knowledge Cache (Prevents Re-Scraping Noise)
CREATE TABLE rubbish_tombstones (
    content_sha256 TEXT PRIMARY KEY,
    source_uri TEXT NOT NULL,
    rejected_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    rejection_reason TEXT CHECK(rejection_reason IN (
        'HIGH_REDUNDANCY', 'LOW_VALIDITY', 'UNTRIANGULATED_ISLAND', 'HALLUCINATION_DETECTED', 'SLOP'
    )),
    nearest_gene_id TEXT REFERENCES epistemic_genes(gene_id),
    cosine_similarity REAL
);

-- 5. Vector Table via sqlite-vec (1024-dim for BGE-M3 / Qwen-Embed)
CREATE VIRTUAL TABLE gene_vectors USING vec0(
    gene_id TEXT PRIMARY KEY,
    embedding FLOAT[1024]
);

```

### Escaping the 1M Token Trap: Subgraph Context Folding

When you or an agent work on a 15-step chain of thought, you never feed the raw conversation history back into the prompt. Instead, the **Context Folder** queries `gene_vectors` for the top $K$ semantic anchors, traverses `gene_synapses` 2 hops out (`CONTRADICTS`, `DEPENDS_ON`, `EXTENDS`), and compiles a **3,000-token lossless YAML/JSON briefing** of pure `claim_atomic` + `critical_nuance` nodes. You get the intellectual weight of 2 million tokens of past research compressed into 3,000 tokens of high-signal axioms.

---

## 3. Hardware Optimization: RTX 4070 (12GB VRAM) + 96GB DDR5 Split

Your hardware has an asymmetric superpower: **12GB VRAM** is tight for large weights, but **96GB of fast DDR5 system RAM** is massive. If you configure your local inference stack correctly, your machine can run 24/7 at near-zero marginal cost without hitting CUDA Out-Of-Memory (OOM) errors:

| System Layer | Allocated Hardware | Exact Model / Engine Configuration | Role in the 24/7 Hive |
| --- | --- | --- | --- |
| **Tier 0: Embeddings & Reranking** | **System RAM (CPU/AVX-512)** (~4 GB DDR5) | `BAAI/bge-m3` + `bge-reranker-v2-m3` via ONNX Runtime / `sentence-transformers` | Keeps 100% of GPU VRAM free for LLM generation. Computes `sqlite-vec` embeddings and cross-encoder relevance scores in <40ms on CPU. |
| **Tier 1: Fast Local Worker & Gatekeeper** | **RTX 4070 (12GB VRAM)** (~9.2 GB VRAM) | **Qwen3-14B** (`Q4_K_M` GGUF) or **Gemma 3 12B** (`Q5_K_M`) via `llama.cpp` / `vLLM` with `--kv-cache-dtype q8_0` | Fits 100% inside the 12GB VRAM with a 16K–32K `q8_0` context window (~35–45 tok/s). Handles 90% of 24/7 scraping triage, claim extraction, JSON formatting, and initial rubric scoring. |
| **Tier 2: Deep Local Critic (Hybrid Offload)** | **12GB VRAM + 30GB DDR5 RAM** | **Dense 32B or MoE (e.g., Qwen3-30B-A3B)** via `llama.cpp` | Mixture-of-Experts (MoE) models store weights in your 96GB DDR5 RAM and offload active attention layers to the 4070, yielding 20–25 tok/s for complex local dialectical verification. |
| **Memory Disk Cache** | **RAMDisk (`tmpfs`)** (16 GB DDR5) | Mount `akashic_core.db` hot read-replica & browser staging in DDR5 RAM | Zero NVMe wear during 24/7 vector KNN sweeps and headless browser DOM parsing; syncs to physical NVMe every 5 minutes. |
| **Tier 3: Cloud Escalation** | **External APIs** (Strict Token Budget) | **Claude** (Nuance/Dialectics), **Codex** (Code/Verification Scripts), **Antigravity** (Workspace/Sandbox Execution) | Triggered **only** when a candidate insight scores high on novelty ($I_{\text{nov}}$) or creates an unresolved dialectical contradiction that local Tier 1/2 models cannot resolve. |

---

## 4. The 24/7 Circular Multi-Agent Hive Architecture

To prevent multi-agent chatter from burning API credits or spiraling into recursive hallucinations, agents **never talk to each other directly in free-text chat**. They operate as a state machine over a SQLite **Blackboard Queue**, passing strictly typed JSON payloads.

```
                   ┌──────────────────────────────────────────┐
                   │     GAP DETECTOR (Curiosity Engine)      │
                   │  Scans SQLite Graph for open hypotheses, │
                   │   weak edges, & high-entropy frontiers   │
                   └────────────────────┬─────────────────────┘
                                        │ (1. Emits Target Vector)
                                        ▼
┌───────────────────────────────────────┴───────────────────────────────────────┐
│                         THE AKASHIC CORE (SQLite + vec0)                      │
│  [epistemic_genes]  <--->  [gene_synapses]  <--->  [rubbish_tombstones]       │
└──────▲─────────────────────────────────────────────────────────────────┬──────┘
       │ (5. Commits Treasure                                            │
       │     or Tombstone)                                               ▼ (2. Dispatches Job)
┌──────┴───────────────────────┐                               ┌─────────────────────────┐
│   THE ARBITER (Gatekeeper)   │                               │  THE FORAGER (Harvester)│
│ Computes S(c) vs τ(M_t).     │                               │ Headless Browser / Docs │
│ Enforces C_tri triangulation │                               │ Appends raw JSONL + SHA │
└──────▲───────────────────────┘                               └─────────┬───────────────┘
       │ (4. Verified Candidate)                                         │ (3. Raw Artifact)
       │                                                                 ▼
┌──────┴───────────────────────┐                               ┌─────────────────────────┐
│  ADVERSARIAL RED-TEAMER      │◄──────────────────────────────┤   THE DISTILLER (Local) │
│ Hunts disconfirming evidence │     (Candidate Gene JSON)     │ RTX 4070 (Qwen3-14B)    │
│ Cloud Escalation if deadlocked│                              │ Strips fluff -> Claims  │
└──────────────────────────────┘                               └─────────────────────────┘

```

### The 5 Circular Roles

1. **The Gap Detector (Cron / Event-Driven):** Queries `epistemic_genes` and `gene_synapses` using SQL to find structural holes—such as a `HYPOTHESIS` node with only 1 supporting source, or two `TREASURE` nodes connected by a `CONTRADICTS` edge. It generates targeted search/verification tasks.
2. **The Forager (Deterministic Harvester):** Runs headless browser workers (e.g., Playwright) or API fetchers. Checks `rubbish_tombstones` by URL/hash first; if unseen, logs the raw payload into an append-only `.jsonl` archive and passes the offset to the Distiller.
3. **The Distiller (Local RTX 4070 - Qwen3-14B / Gemma 3 12B):** Reads the raw artifact, strips all boilerplate, and extracts candidate `claim_atomic`, `critical_nuance`, and `actionable_implementation` JSON structures.
4. **The Adversarial Red-Teamer (Local MoE -> Cloud Claude/Codex Escalation):** Tasked explicitly with *destroying* the Distiller's candidate gene. It queries the database for contradicting genes and attempts to falsify the claim.
* If the claim requires empirical code verification, it delegates to **Codex / Antigravity** to write and run a quick verification script in an isolated sandbox.
* If the claim involves deep architectural nuance or unresolved paradoxes, it escalates a tightly folded 2,000-token context packet to **Claude**.


5. **The Arbiter (Deterministic Python + `sqlite-vec` Math):** Computes $S(c)$ against $\tau(M_t)$. If it passes, it writes the gene and its synaptic edges to SQLite.

---

## 5. Core Implementation Blueprint (`hive_governor.py`)

This foundational Python skeleton wires together the **Epistemic Gravity math**, **`sqlite-vec` triangulation**, **circuit-breaker safety budgets**, and **Local-to-Cloud routing**:

```python
import sqlite3
import sqlite_vec
import json
import math
import hashlib
import time
from dataclasses import dataclass
from typing import List, Tuple, Literal

@dataclass
class CandidateGene:
    domain_taxonomy: str
    claim_atomic: str
    critical_nuance: str
    actionable_implementation: str
    source_uri: str
    raw_content_hash: str
    validity_score: float          # V(c) in [0.0, 1.0] from Red-Teamer / empirical check
    novelty_score: float           # I_nov(c) in [0.0, 1.0]
    embedding: List[float]         # 1024-d float vector from local BGE-M3

class AkashicGovernor:
    def __init__(self, db_path: str = "akashic_core.db"):
        self.db = sqlite3.connect(db_path)
        self.db.enable_load_extension(True)
        sqlite_vec.load(self.db)
        self.db.enable_load_extension(False)
        
        # Hyperparameters for Epistemic Gravity
        self.tau_0 = 0.35          # Base admission threshold
        self.gamma = 0.08          # Gravity scaling factor as DB grows
        self.alpha = 1.2           # Triangulation exponent
        self.beta = 1.0            # Novelty exponent
        self.lambda_red = 4.5      # Redundancy penalty multiplier
        
        # 24/7 Safety Circuit Breakers
        self.daily_cloud_tokens_used = 0
        self.max_daily_cloud_tokens = 150_000

    def get_current_mass_threshold(self) -> Tuple[int, float]:
        """Calculates current verified mass M_t and required threshold tau(M_t)."""
        cur = self.db.cursor()
        cur.execute("SELECT COUNT(*) FROM epistemic_genes WHERE status = 'TREASURE'")
        m_t = cur.fetchone()[0]
        tau_mt = self.tau_0 + self.gamma * math.log(1 + m_t)
        return m_t, tau_mt

    def compute_redundancy_and_neighbors(self, embedding: List[float], k: int = 8) -> List[Tuple[str, float]]:
        """Queries sqlite-vec for nearest semantic neighbors and converts L2 distance to cosine similarity."""
        cur = self.db.cursor()
        vec_bytes = sqlite_vec.serialize_float32(embedding)
        cur.execute("""
            SELECT gene_id, distance
            FROM gene_vectors
            WHERE embedding MATCH ? AND k = ?
            ORDER BY distance ASC
        """, (vec_bytes, k))
        rows = cur.fetchall()
        # Assuming normalized unit vectors: Cosine Similarity = 1 - (L2_distance^2) / 2
        return [(r[0], max(0.0, 1.0 - (r[1] ** 2) / 2.0)) for r in rows]

    def compute_triangulation(self, neighbors: List[Tuple[str, float]]) -> float:
        """
        Rewards candidates that bridge non-identical clusters (graph distance >= 2)
        while maintaining strong semantic coherence (> 0.45) with at least two anchors.
        """
        valid_anchors = [(gid, sim) for gid, sim in neighbors if 0.45 <= sim < 0.88]
        if len(valid_anchors) < 2:
            return 0.05  # Untriangulated island penalty
        
        cur = self.db.cursor()
        tri_score = 0.0
        for i in range(len(valid_anchors)):
            for j in range(i + 1, len(valid_anchors)):
                u, sim_u = valid_anchors[i]
                v, sim_v = valid_anchors[j]
                # Check if u and v are already directly linked (distance = 1)
                cur.execute("""
                    SELECT 1 FROM gene_synapses 
                    WHERE (source_gene_id = ? AND target_gene_id = ?)
                       OR (source_gene_id = ? AND target_gene_id = ?)
                """, (u, v, v, u))
                directly_linked = cur.fetchone() is not None
                # Bridging previously unlinked or multi-hop nodes yields higher triangulation value
                bridge_bonus = 1.0 if not directly_linked else 0.4
                tri_score += (sim_u * sim_v) * bridge_bonus
                
        return min(2.0, tri_score)

    def evaluate_candidate(self, c: CandidateGene) -> Tuple[Literal["TREASURE", "MERGE", "RUBBISH"], float]:
        """Executes the Epistemic Gravity Admission Gate."""
        _, tau_mt = self.get_current_mass_threshold()
        neighbors = self.compute_redundancy_and_neighbors(c.embedding)
        
        r_max = neighbors[0][1] if neighbors else 0.0
        c_tri = self.compute_triangulation(neighbors)
        
        numerator = c.validity_score * (c_tri ** self.alpha) * (c.novelty_score ** self.beta)
        denominator = 1.0 + (self.lambda_red * max(0.0, r_max - 0.65))
        s_c = numerator / denominator

        if r_max >= 0.88 and c.novelty_score < 0.4:
            return "RUBBISH", s_c
        elif s_c >= tau_mt:
            return "TREASURE", s_c
        elif s_c >= (0.5 * tau_mt) and r_max >= 0.72:
            return "MERGE", s_c
        else:
            return "RUBBISH", s_c

    def route_inference(self, task_type: str, ambiguity_score: float, payload: dict) -> str:
        """
        Hybrid Orchestration Router:
        Prioritizes RTX 4070 Local LLM; escalates to Claude/Codex/Antigravity only under strict criteria.
        """
        if task_type in ("DISTILL", "TRIAGE", "SCHEMA_EXTRACT") or ambiguity_score < 0.65:
            return "LOCAL_RTX4070_QWEN14B"
        
        if self.daily_cloud_tokens_used >= self.max_daily_cloud_tokens:
            return "LOCAL_HYBRID_MOE_30B"  # Fallback to 96GB DDR5 + 4070 when cloud quota hits cap
            
        if task_type == "EMPIRICAL_CODE_VERIFY":
            return "CLOUD_CODEX_ANTIGRAVITY_SANDBOX"
        elif task_type == "DIALECTICAL_PARADOX_RESOLUTION":
            return "CLOUD_CLAUDE_ARCHITECT"
            
        return "LOCAL_RTX4070_QWEN14B"

```

---

## 6. Guardrails for Unattended 24/7 Operation

Running an autonomous multi-agent loop 24/7 introduces three fatal failure modes: **Epistemic Echo Chambers** (agents citing their own earlier hallucinations), **Runaway API Spend**, and **Prompt Injection via Scraped Sources**. Bake these four controls directly into the daemon:

1. **Strict Source Quarantine (Anti-Prompt Injection):** The Forager never passes raw HTML/text directly into an agent with tool-calling privileges. The local RTX 4070 Distiller runs with **zero tool access** and a constrained JSON grammar (`llama.cpp` GBNF grammar enforcement) so a malicious webpage cannot hijack the agent hive.
2. **No Self-Citation Loops:** When calculating the Triangulation Coefficient $C_{\text{tri}}(c)$, two nodes only count as independent anchors if their `provenance_ledger` entries trace back to distinct root domains or independent empirical runs. An agent's own `HYPOTHESIS` node has a validity weight of $0$ until corroborated externally.
3. **The "Sleep & Prune" Consolidation Cycle (03:00–04:00 Local Time):** Once every 24 hours, pause external foraging and run a local graph maintenance pass:
* Run PageRank / Betweenness Centrality over `gene_synapses` to identify load-bearing "Axiom Genes."
* Compact fragmented `EXTENDS` chains into versioned gene upgrades.
* Export a visual interactive knowledge map (via **Cytoscape.js** or **Cosmograph** reading directly from `akashic_core.db`) so you can visually inspect clusters, spot nascent "genes" of thought, and inject human steering vectors in seconds.


4. **Token Bucket & Deadlock Breakers:** Enforce a hard daily token cap on Claude/Codex API calls, and a maximum retry depth of `2` per hypothesis. If a hypothesis cannot be triangulated after 2 foraging cycles, its status is locked as `UNVERIFIED_FRONTIER` until new external mass naturally connects to it later.
