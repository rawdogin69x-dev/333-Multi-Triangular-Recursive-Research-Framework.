"""LLM access. Every call goes through one gate that logs it to agent_runs and enforces budgets.

Local servers (llama.cpp, llama-swap, LM Studio, Ollama /v1) speak the OpenAI chat API.
Cloud providers are disabled unless the owner sets a positive monthly cap (assumption A2: $0).
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Callable, Protocol

import httpx

from .ids import now, uuid7


class BudgetExceeded(RuntimeError):
    """Raised instead of calling a provider whose cap is spent. The caller defers the task."""


@dataclass(frozen=True)
class Provider:
    name: str                       # e.g. 'local-day', 'local-night', 'anthropic'
    base_url: str
    model: str
    local: bool = True
    api_key_env: str | None = None  # read from the environment at call time; never stored or logged
    monthly_cap_usd: float = 0.0    # cloud only; 0 means disabled
    usd_per_mtok_in: float = 0.0
    usd_per_mtok_out: float = 0.0


@dataclass
class Reply:
    text: str
    tokens_in: int | None
    tokens_out: int | None
    cost_usd: float
    ms: int


class Transport(Protocol):
    def __call__(self, provider: Provider, messages: list[dict], **kw) -> Reply: ...


def http_transport(provider: Provider, messages: list[dict], *, json_mode: bool = False,
                   temperature: float = 0.1, max_tokens: int = 2048, grammar: str | None = None) -> Reply:
    import os

    headers = {}
    if provider.api_key_env:
        key = os.environ.get(provider.api_key_env)
        if not key:
            raise RuntimeError(f"environment variable {provider.api_key_env} is not set")
        headers["Authorization"] = f"Bearer {key}"
    body: dict = {"model": provider.model, "messages": messages, "temperature": temperature,
                  "max_tokens": max_tokens}
    if json_mode:
        body["response_format"] = {"type": "json_object"}
    if grammar and provider.local:
        body["grammar"] = grammar  # llama.cpp server extension: hard-constrains the output
    t0 = time.perf_counter()
    with httpx.Client(base_url=provider.base_url, headers=headers, timeout=900) as c:
        r = c.post("/chat/completions", json=body)
    r.raise_for_status()
    data = r.json()
    usage = data.get("usage") or {}
    tin, tout = usage.get("prompt_tokens"), usage.get("completion_tokens")
    cost = ((tin or 0) * provider.usd_per_mtok_in + (tout or 0) * provider.usd_per_mtok_out) / 1e6
    return Reply(data["choices"][0]["message"]["content"], tin, tout, cost, int((time.perf_counter() - t0) * 1000))


class Gateway:
    """The single door to every model. Logs each run; refuses cloud calls beyond the monthly cap."""

    def __init__(self, conn, providers: dict[str, Provider], transport: Transport = http_transport,
                 clock: Callable[[], str] = now):
        self.conn, self.providers, self.transport, self.clock = conn, providers, transport, clock

    def spent_this_month(self, provider: str) -> float:
        month = self.clock()[:7]
        row = self.conn.execute(
            "SELECT COALESCE(SUM(cost_usd), 0) FROM agent_runs WHERE provider = ? AND substr(started_at, 1, 7) = ?",
            (provider, month),
        ).fetchone()
        return float(row[0])

    def call(self, provider: str, role: str, messages: list[dict], *, task_id: str | None = None, **kw) -> Reply:
        p = self.providers[provider]
        if not p.local:
            if p.monthly_cap_usd <= 0:
                raise BudgetExceeded(f"{provider}: cloud disabled (monthly cap is $0)")
            if self.spent_this_month(provider) >= p.monthly_cap_usd:
                raise BudgetExceeded(f"{provider}: monthly cap ${p.monthly_cap_usd:.2f} reached")
        prompt_sha = hashlib.sha256(json.dumps(messages, sort_keys=True).encode()).hexdigest()
        started = self.clock()
        reply = self.transport(p, messages, **kw)
        self.conn.execute(
            """INSERT INTO agent_runs(run_id, task_id, role, provider, model, prompt_sha256, tokens_in, tokens_out,
                   cost_usd, ms, output_json, started_at) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            (uuid7(), task_id, role, provider, p.model, prompt_sha, reply.tokens_in, reply.tokens_out,
             reply.cost_usd, reply.ms, reply.text[:20000], started),
        )
        return reply


def fake_transport(responder: Callable[[list[dict]], str]) -> Transport:
    """For tests and dry runs: a deterministic stand-in for a model."""

    def _t(provider: Provider, messages: list[dict], **kw) -> Reply:
        return Reply(responder(messages), 0, 0, 0.0, 0)

    return _t
