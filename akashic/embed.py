"""Embedders. Production uses a local model over HTTP; the hashing embedder is for tests and dry runs only."""

from __future__ import annotations

import hashlib
import math
import re
from typing import Protocol

import httpx


class Embedder(Protocol):
    name: str
    dims: int

    def embed(self, texts: list[str]) -> list[list[float]]: ...


def _unit(v: list[float]) -> list[float]:
    n = math.sqrt(sum(x * x for x in v)) or 1.0
    return [x / n for x in v]


class HttpEmbedder:
    """OpenAI-compatible /embeddings (llama-server --embedding, LM Studio, Ollama /v1, TEI)."""

    def __init__(self, base_url: str, model: str, dims: int, timeout: float = 120):
        self.name, self.dims = model, dims
        self.client = httpx.Client(base_url=base_url, timeout=timeout)

    def embed(self, texts: list[str]) -> list[list[float]]:
        r = self.client.post("/embeddings", json={"model": self.name, "input": texts})
        r.raise_for_status()
        vecs = [d["embedding"] for d in sorted(r.json()["data"], key=lambda d: d["index"])]
        for v in vecs:
            if len(v) != self.dims:
                raise ValueError(f"embedding has {len(v)} dims, config says {self.dims}")
        return [_unit(v) for v in vecs]


class HashEmbedder:
    """Feature-hashed word and bigram counts. NOT semantic: synonyms look unrelated.

    Exists so the pipeline and tests run with no model. Never use it for a real library.
    """

    def __init__(self, dims: int = 256):
        self.name, self.dims = f"hash-{dims}", dims

    def embed(self, texts: list[str]) -> list[list[float]]:
        out = []
        for t in texts:
            words = re.findall(r"\w+", t.casefold())
            v = [0.0] * self.dims
            for tok in words + [a + " " + b for a, b in zip(words, words[1:])]:
                h = int.from_bytes(hashlib.blake2b(tok.encode(), digest_size=8).digest(), "big")
                v[h % self.dims] += 1.0 if (h >> 63) & 1 else -1.0
            out.append(_unit(v))
        return out
