"""Command line: init, charters, stats, gravity, ingest, show, search, brief, digest, rueckschau, resonate."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml

from . import config as config_mod
from .db import connect, migrate
from .store import Store


def _open(args) -> Store:
    cfg = config_mod.load(args.config)
    conn = connect(args.db or cfg.db_path)
    migrate(conn, cfg)
    return Store(conn, cfg, actor="human")


def cmd_init(args) -> int:
    store = _open(args)
    v = store.conn.execute("PRAGMA user_version").fetchone()[0]
    print(f"schema v{v} ready")
    return 0


def cmd_charters(args) -> int:
    store = _open(args)
    if args.load:
        data = yaml.safe_load(Path(args.load).read_text(encoding="utf-8")) or {}
        for c in data.get("charters", []):
            cid = store.add_charter(c["question"], c.get("scope"), c.get("priority", 3), c.get("done_when"))
            print(f"added {cid}  {c['question']}")
    for r in store.conn.execute("SELECT charter_id, priority, status, question FROM charters ORDER BY priority"):
        print(f"{r['charter_id']}  p{r['priority']}  {r['status']:<6}  {r['question']}")
    return 0


def cmd_stats(args) -> int:
    store = _open(args)
    states = dict(store.conn.execute("SELECT state, COUNT(*) FROM genes GROUP BY state").fetchall())
    out = {
        "genes_by_state": states,
        "sources": store.conn.execute("SELECT COUNT(*) FROM sources").fetchone()[0],
        "evidence": store.conn.execute("SELECT COUNT(*) FROM evidence").fetchone()[0],
        "edges": store.conn.execute("SELECT COUNT(*) FROM edges").fetchone()[0],
        "queued_tasks": store.conn.execute("SELECT COUNT(*) FROM tasks WHERE state = 'QUEUED'").fetchone()[0],
    }
    print(json.dumps(out, indent=2))
    return 0


def cmd_gravity(args) -> int:
    store = _open(args)
    print(json.dumps(store.gravity_view(args.taxonomy), indent=2))
    return 0


def _pipeline(store: Store):
    from .embed import HttpEmbedder
    from .forage import BlobStore, Forager, Politeness
    from .ingest import Pipeline
    from .llm import Gateway, Provider

    cfg = store.cfg
    providers = {name: Provider(name=name, **p) for name, p in cfg.providers.items()}
    gw = Gateway(store.conn, providers)
    emb = HttpEmbedder(cfg.embedder["base_url"], cfg.embedder["model"], cfg.embed_dims)
    pc = cfg.pipeline
    forager = Forager(BlobStore(cfg.blob_dir), politeness=Politeness(min_interval_s=pc.min_fetch_interval_s))
    return Pipeline(store, forager, gw, emb, distill_provider=pc.distill_provider,
                    judge_provider=pc.judge_provider, judge_floor=pc.judge_floor,
                    min_confidence_same=pc.min_confidence_same, neighbours=pc.neighbours,
                    max_claims_per_chunk=pc.max_claims_per_chunk, use_grammar=pc.use_grammar)


def cmd_ingest(args) -> int:
    from dataclasses import asdict

    store = _open(args)
    pipe = _pipeline(store)
    for target in args.targets:
        rep = pipe.ingest_file(target, args.charter) if Path(target).exists() else pipe.ingest_url(target, args.charter)
        print(json.dumps({"target": target, **{k: v for k, v in asdict(rep).items() if k != "gene_ids"}}))
    return 0


def _resolve_id(store: Store, prefix: str) -> str:
    rows = store.conn.execute("SELECT gene_id FROM genes WHERE gene_id LIKE ?", (prefix + "%",)).fetchall()
    if len(rows) != 1:
        raise SystemExit(f"{len(rows)} genes match '{prefix}'")
    return rows[0][0]


def cmd_show(args) -> int:
    store = _open(args)
    gid = _resolve_id(store, args.gene)
    g = store.conn.execute("SELECT * FROM genes WHERE gene_id = ?", (gid,)).fetchone()
    print(f"{gid}  {g['state']}  {g['frame']}  {g['taxonomy']}  support={g['support']:.2f} "
          f"against={g['against']:.2f} lineages={g['lineages_for']}/{g['lineages_against']}"
          f"{'  UNINTEGRATED' if g['unintegrated'] else ''}")
    for v in store.conn.execute("SELECT * FROM gene_versions WHERE gene_id = ? ORDER BY version", (gid,)):
        print(f"\n  v{v['version']} ({v['author']}, {v['created_at']})\n  thesis: {v['thesis']}\n  reason: {v['reason']}"
              f"\n  example: {v['example']}\n  scope: {v['scope']}\n  application: {v['application']}")
    print("\n  evidence:")
    for e in store.conn.execute(
            """SELECT e.stance, e.evidence_type, e.verified_quote, e.quote, s.uri, s.lineage_id FROM evidence e
               JOIN sources s USING(source_id) WHERE e.gene_id = ?""", (gid,)):
        print(f"   {e['stance']:<7} {e['evidence_type']:<9} {'ok' if e['verified_quote'] else 'UNVERIFIED'}  "
              f"[{e['lineage_id']}] \"{e['quote'][:120]}\"  <{e['uri']}>")
    print("\n  edges:")
    for r in store.conn.execute("SELECT src, rel, dst FROM edges WHERE src = ? OR dst = ?", (gid, gid)):
        print(f"   {r['src'][:13]} -{r['rel']}-> {r['dst'][:13]}")
    return 0


def cmd_search(args) -> int:
    from .search import hybrid

    store = _open(args)
    vec = None if args.no_vectors else _pipeline(store).embedder.embed([args.query])[0]
    for h in hybrid(store.conn, args.query, vec, k=args.k):
        print(f"{h.gene_id[:13]}  {h.state:<12} s={h.support:.2f}  {h.thesis}")
    return 0


def cmd_brief(args) -> int:
    from .brief import brief

    store = _open(args)
    emb = None if args.no_vectors else _pipeline(store).embedder
    print(brief(store.conn, args.topic, emb, budget_tokens=args.tokens))
    return 0


def cmd_digest(args) -> int:
    from .maintenance import digest

    print(digest(_open(args), args.hours))
    return 0


def cmd_rueckschau(args) -> int:
    from .maintenance import rueckschau

    print(f"re-checked {rueckschau(_open(args))} genes")
    return 0


def cmd_resonate(args) -> int:
    store = _open(args)
    store.set_resonance(_resolve_id(store, args.gene), args.value)
    return 0


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="akashic")
    p.add_argument("--config", default="config/akashic.yaml")
    p.add_argument("--db", help="override db_path from config")
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init", help="create or migrate the core DB").set_defaults(fn=cmd_init)
    c = sub.add_parser("charters", help="list charters, optionally loading a YAML file first")
    c.add_argument("--load")
    c.set_defaults(fn=cmd_charters)
    sub.add_parser("stats").set_defaults(fn=cmd_stats)
    g = sub.add_parser("gravity", help="show mass, tau and k_required for a topic")
    g.add_argument("taxonomy")
    g.set_defaults(fn=cmd_gravity)
    i = sub.add_parser("ingest", help="fetch or read sources and admit their claims through the gate")
    i.add_argument("targets", nargs="+", help="URLs or local files (txt, html, pdf)")
    i.add_argument("--charter", help="charter id the sources bear on")
    i.set_defaults(fn=cmd_ingest)
    s_ = sub.add_parser("show", help="one gene with versions, evidence and edges")
    s_.add_argument("gene", help="gene id or unique prefix")
    s_.set_defaults(fn=cmd_show)
    q = sub.add_parser("search", help="hybrid FTS5 + vector search")
    q.add_argument("query")
    q.add_argument("-k", type=int, default=10)
    q.add_argument("--no-vectors", action="store_true", help="words only; no embedding server needed")
    q.set_defaults(fn=cmd_search)
    b = sub.add_parser("brief", help="folded, token-budgeted brief on a topic")
    b.add_argument("topic")
    b.add_argument("--tokens", type=int, default=3000)
    b.add_argument("--no-vectors", action="store_true")
    b.set_defaults(fn=cmd_brief)
    d = sub.add_parser("digest", help="what changed in the last N hours")
    d.add_argument("--hours", type=int, default=24)
    d.set_defaults(fn=cmd_digest)
    sub.add_parser("rueckschau", help="replay queued re-checks newest-first").set_defaults(fn=cmd_rueckschau)
    r = sub.add_parser("resonate", help="mark how a gene resonates with you (-2..2); affects priority only")
    r.add_argument("gene")
    r.add_argument("value", type=int)
    r.set_defaults(fn=cmd_resonate)
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
