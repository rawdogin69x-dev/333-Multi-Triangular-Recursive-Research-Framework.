"""SQLite connection, pragmas and migrations. One file holds relations, FTS5 and vectors."""

from __future__ import annotations

import re
import sqlite3
from importlib import resources
from pathlib import Path

import sqlite_vec

from .config import Config


def connect(path: str | Path, *, readonly: bool = False) -> sqlite3.Connection:
    """Open the core DB with WAL, foreign keys and sqlite-vec loaded.

    Only the Arbiter process should open it writable; workers open it read-only.
    """
    path = str(path)
    if path != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    uri = f"file:{path}?mode=ro" if readonly else path
    conn = sqlite3.connect(uri, uri=readonly, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.enable_load_extension(True)
    sqlite_vec.load(conn)
    conn.enable_load_extension(False)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA busy_timeout = 5000")
    if not readonly:
        conn.execute("PRAGMA journal_mode = WAL")
        conn.execute("PRAGMA synchronous = NORMAL")
    # Use the big RAM via the page cache and mmap instead of a RAMDisk copy.
    conn.execute("PRAGMA mmap_size = 8589934592")
    conn.execute("PRAGMA cache_size = -2000000")  # ~2 GB, in KiB
    return conn


def _migrations() -> list[tuple[int, str]]:
    files = resources.files("akashic.migrations")
    out = []
    for f in files.iterdir():
        if f.name.endswith(".sql"):
            out.append((int(f.name.split("_", 1)[0]), f.read_text(encoding="utf-8")))
    return sorted(out)


def migrate(conn: sqlite3.Connection, cfg: Config) -> int:
    """Apply pending migrations; returns the schema version reached."""
    current = conn.execute("PRAGMA user_version").fetchone()[0]
    for version, sql in _migrations():
        if version <= current:
            continue
        conn.execute("BEGIN")
        try:
            for stmt in _split(sql):
                conn.execute(stmt)
            if version == 1:
                _create_virtual_tables(conn, cfg)
            conn.execute(f"PRAGMA user_version = {version}")
            conn.execute("COMMIT")
        except Exception:
            conn.execute("ROLLBACK")
            raise
        current = version
    return current


def _create_virtual_tables(conn: sqlite3.Connection, cfg: Config) -> None:
    # Contentless FTS: rowids map to gene_fts_map so we can search without duplicating text.
    conn.execute(
        "CREATE VIRTUAL TABLE gene_fts USING fts5(thesis, reason, nuance, scope, content='')"
    )
    conn.execute(
        "CREATE TABLE gene_fts_map (rowid INTEGER PRIMARY KEY, gene_id TEXT NOT NULL UNIQUE REFERENCES genes(gene_id))"
    )
    conn.execute(
        f"""CREATE VIRTUAL TABLE gene_vec USING vec0(
                gene_id TEXT PRIMARY KEY,
                embedding float[{int(cfg.embed_dims)}] distance_metric=cosine,
                frame TEXT,
                topic TEXT
            )"""
    )


def _split(sql: str) -> list[str]:
    """Split a migration into statements. Our SQL has no triggers and no ';' or '--' inside strings."""
    no_comments = re.sub(r"--[^\n]*", "", sql)
    return [s.strip() for s in no_comments.split(";") if s.strip()]
