"""Tunable constants. Every value here is a starting guess to be calibrated in Phase 2.

Override any field from a YAML file (see config/akashic.example.yaml).
"""

from __future__ import annotations

from dataclasses import dataclass, field, fields
from pathlib import Path

import yaml


@dataclass(frozen=True)
class GravityConfig:
    # support threshold: tau_d = tau0 + gamma * ln(1 + M_d)
    tau0: float = 0.60
    gamma: float = 0.03
    tau_max: float = 0.95
    # required independent lineages: min(k_cap, k_base + floor(log10(1 + M_d)))
    k_base: int = 2
    k_cap: int = 4
    # four-valued state: a side "holds" when its score reaches this
    holds: float = 0.50
    # how many taxonomy levels define a topic for mass ("sci.ml.rag.dedup" -> "sci.ml")
    topic_depth: int = 2


@dataclass(frozen=True)
class EvidenceWeights:
    """Weight w per evidence type (pramana). Reliability r of the source multiplies it."""

    EXECUTED: float = 0.95   # ran it ourselves in the sandbox
    OBSERVED: float = 0.85   # pratyaksa: measurement, experiment, primary data
    INFERRED: float = 0.60   # anumana: argued from stated premises
    ABSENCE: float = 0.50    # anupalabdhi: documented null result
    TESTIMONY: float = 0.50  # sabda: someone credible says so
    ABDUCTION: float = 0.35  # arthapatti: best explanation
    ANALOGY: float = 0.20    # upamana: resembles a known case

    def of(self, evidence_type: str) -> float:
        return getattr(self, evidence_type)


def _default_providers() -> dict:
    # Cloud entries are absent by default: assumption A2, cloud spend is $0 until the owner sets a cap.
    return {
        "local-day": {"base_url": "http://127.0.0.1:8080/v1", "model": "local-day", "local": True},
        "local-night": {"base_url": "http://127.0.0.1:8080/v1", "model": "local-night", "local": True},
    }


def _default_embedder() -> dict:
    return {"base_url": "http://127.0.0.1:8081/v1", "model": "bge-m3"}


@dataclass(frozen=True)
class PipelineConfig:
    distill_provider: str = "local-day"
    judge_provider: str = "local-day"
    judge_floor: float = 0.80
    min_confidence_same: float = 0.75
    neighbours: int = 5
    max_claims_per_chunk: int = 8
    use_grammar: bool = True
    min_fetch_interval_s: float = 5.0


@dataclass(frozen=True)
class Config:
    db_path: str = "data/akashic_core.db"
    blob_dir: str = "data/blobs"
    embed_dims: int = 1024
    default_source_reliability: float = 0.5
    tombstone_days: int = 90
    max_forage_cycles: int = 2
    gravity: GravityConfig = field(default_factory=GravityConfig)
    weights: EvidenceWeights = field(default_factory=EvidenceWeights)
    pipeline: PipelineConfig = field(default_factory=PipelineConfig)
    providers: dict = field(default_factory=_default_providers)
    embedder: dict = field(default_factory=_default_embedder)


def load(path: str | Path | None = None) -> Config:
    if path is None or not Path(path).exists():
        return Config()
    raw = yaml.safe_load(Path(path).read_text(encoding="utf-8")) or {}
    gravity = GravityConfig(**raw.pop("gravity", {}))
    weights = EvidenceWeights(**raw.pop("weights", {}))
    pipeline = PipelineConfig(**raw.pop("pipeline", {}))
    known = {f.name for f in fields(Config)}
    unknown = set(raw) - known
    if unknown:
        raise ValueError(f"unknown config keys: {sorted(unknown)}")
    return Config(gravity=gravity, weights=weights, pipeline=pipeline, **raw)
