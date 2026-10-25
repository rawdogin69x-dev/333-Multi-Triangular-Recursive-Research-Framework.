"""Command line. Phase 0: init, charters, stats, gravity. Ingest arrives in Phase 1."""

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
    args = p.parse_args(argv)
    return args.fn(args)


if __name__ == "__main__":
    sys.exit(main())
