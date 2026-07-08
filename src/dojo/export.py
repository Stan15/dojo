"""Export: write the learner's entire store as a fresh markdown store at a
destination — entity by entity, through the Store protocol, blind to the
source backend (ADR 011).

Why not copy files? Because the source might not BE files. Reading through the
protocol makes export identical under any backend — with markdown it yields a
clean tree (no locks, caches, logs, or git history), and when a database
backend exists, the same command is the escape hatch that turns it back into
readable markdown. It is also, structurally, a backend migration tool: the
same loop pointed at a different destination store.

The destination is a complete, self-contained dojo store: `dojo --db <dest>`
works on it immediately, and it is born as a git repo with the export as its
first recovery point.
"""
from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .store import DojoStore


def export_store(src: DojoStore, dest_dir: str | Path) -> dict[str, Any]:
    dest_dir = Path(dest_dir).expanduser().resolve()
    if dest_dir == src.dojo_dir.resolve():
        raise ValueError("destination is the source store itself")
    if dest_dir.exists() and any(dest_dir.iterdir()):
        raise ValueError(
            f"destination {dest_dir} is not empty — export only writes into a fresh "
            "directory (it will never merge into or overwrite existing data)"
        )

    dest = DojoStore(dest_dir)
    counts: dict[str, int] = {}

    def bump(key: str, n: int = 1) -> None:
        counts[key] = counts.get(key, 0) + n

    for source in src.sources.list():
        dest.sources.save(source)
        bump("sources")
    for capture in src.captures.list():
        dest.captures.save(capture)
        bump("captures")
    for task in src.tasks.list():
        dest.tasks.save(task)
        bump("tasks")

    for campaign in src.campaigns.list():
        dest.campaigns.save(campaign)
        bump("campaigns")
        for ex in src.exercises.list(campaign.id):
            dest.exercises.save(campaign.id, ex)
            bump("exercises")
        for cand in src.candidates.list(campaign.id):
            dest.candidates.save(campaign.id, cand)
            bump("candidates")
        for att in src.attempts.list(campaign.id):
            dest.attempts.save(campaign.id, att)
            bump("attempts")
        for ins in src.insights.list(campaign.id):
            dest.insights.save(campaign.id, ins)
            bump("insights")

    for key, value in src.configs.all().items():
        dest.configs.set_value(key, value)
        bump("config_values")

    active = src.sessions.get_active()
    if active is not None:
        dest.sessions.save_active(active)
        bump("sessions")
    for sess in src.sessions.list_archived():
        dest.sessions.save_archived(sess)
        bump("sessions")

    # Honest boundary (I10): archived campaigns stay in the source for now.
    archived = [
        r for r in src.engine.query_index("campaign")
        if r["path"].startswith("archive/")
    ]
    skipped = {"archived_campaigns": len(archived)} if archived else {}

    dest.engine.audit(
        f"dojo export from {src.dojo_dir} at {datetime.now(timezone.utc).isoformat()}"
    )
    return {
        "destination": str(dest_dir),
        "counts": counts,
        "skipped": skipped,
        "next": f'the export is a complete dojo store — try: dojo --db "{dest_dir}" doctor',
    }
