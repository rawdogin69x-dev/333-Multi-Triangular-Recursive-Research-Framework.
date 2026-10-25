"""Night-shift upkeep: the Rückschau replay and the daily digest."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

from .ids import now
from .store import Store, tx


def rueckschau(store: Store, max_rounds: int = 20) -> int:
    """Replay queued re-checks newest-first until the graph settles (ruling S7).

    Newest-first means a late change is applied before the older changes that depended on its
    predecessor, so cascades settle in fewer sweeps. Bounded so a cycle cannot loop forever.
    """
    done = 0
    for _ in range(max_rounds):
        tasks = store.conn.execute(
            "SELECT task_id, payload_json FROM tasks WHERE kind = 'RECHECK' AND state = 'QUEUED' "
            "ORDER BY created_at DESC, task_id DESC").fetchall()
        if not tasks:
            break
        seen: set[str] = set()
        for t in tasks:
            gid = json.loads(t["payload_json"])["gene_id"]
            with tx(store.conn):
                store.conn.execute("UPDATE tasks SET state = 'DONE', done_at = ? WHERE task_id = ?",
                                   (now(), t["task_id"]))
            if gid in seen:
                continue
            seen.add(gid)
            store.reassess(gid)
            done += 1
    return done


def digest(store: Store, hours: int = 24) -> str:
    """One page for the morning: what settled, what is contested, what fell, what to look at."""
    c = store.conn
    since = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat(timespec="seconds")

    def changed_to(state: str) -> list[str]:
        return [r[0] for r in c.execute(
            """SELECT v.thesis FROM events e JOIN genes g ON g.gene_id = e.gene_id
               JOIN gene_versions v ON v.gene_id = g.gene_id AND v.version = g.current_version
               WHERE e.kind = 'STATE' AND e.after = ? AND e.at >= ? ORDER BY e.at DESC""",
            (f'"{state}"', since))]

    rejected = c.execute(
        "SELECT reject_reason, COUNT(*) FROM genes WHERE state = 'REJECTED' AND updated_at >= ? GROUP BY 1",
        (since,)).fetchall()
    open_q = c.execute(
        """SELECT v.thesis, g.lineages_for, g.unintegrated, g.resonance FROM genes g
           JOIN gene_versions v ON v.gene_id = g.gene_id AND v.version = g.current_version
           WHERE g.state = 'HYPOTHESIS' ORDER BY COALESCE(g.resonance, 0) DESC, g.support DESC LIMIT 5""").fetchall()
    preds = c.execute("SELECT COUNT(*) FROM tasks WHERE kind = 'TEST_PREDICTION' AND state = 'QUEUED'").fetchone()[0]
    lines = [f"# Digest, last {hours} h", ""]
    for title, state in (("Newly corroborated", "CORROBORATED"), ("Newly contested", "CONTESTED"),
                         ("Refuted", "REFUTED")):
        items = changed_to(state)
        lines.append(f"## {title} ({len(items)})")
        lines += [f"- {t}" for t in items[:10]] or ["- none"]
        lines.append("")
    lines.append("## Rejected at the gate")
    lines += [f"- {r[0]}: {r[1]}" for r in rejected] or ["- none"]
    lines += ["", "## Open hypotheses worth a look"]
    for t, n, unint, res in open_q:
        why = "needs a connection" if unint else f"{n} lineage(s) so far"
        lines.append(f"- {t} ({why}{', resonates' if res and res > 0 else ''})")
    if not open_q:
        lines.append("- none")
    lines += ["", f"Predictions waiting to be tested: {preds}"]
    return "\n".join(lines)
