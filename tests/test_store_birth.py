"""A store must be born healthy (real git, no mocks): the init scaffolding is
committed at creation, so the very first command a user ever runs — even the
read-only doctor — sees a clean audit trail. Regression for the deadlock where
doctor flagged the uncommitted init forever while rc=1 skipped the audit that
would have committed it."""
from __future__ import annotations

import subprocess
from pathlib import Path

from dojo.store import DojoStore


def test_fresh_store_is_born_committed(tmp_path: Path):
    store = DojoStore(tmp_path / "store")
    assert store.doctor.run()["Version control audit"] == []
    log = subprocess.run(
        ["git", "log", "--oneline"], cwd=store.dojo_dir,
        capture_output=True, text=True,
    ).stdout
    assert "dojo store initialized" in log


def test_audit_commits_without_configured_git_identity(tmp_path: Path):
    store = DojoStore(tmp_path / "store")
    (store.dojo_dir / "sources").mkdir(exist_ok=True)
    store.write_text("sources/src_x.md", "---\nid: src_x\ntitle: t\nkind: text\n---\n\nhello")
    env_isolated = subprocess.run(
        ["git", "-c", "user.name=", "-c", "user.email=", "status", "--porcelain"],
        cwd=store.dojo_dir, capture_output=True, text=True,
    )  # sanity: repo reachable
    assert env_isolated.returncode == 0
    store.engine.audit("test recovery point")
    status = subprocess.run(
        ["git", "status", "--porcelain"], cwd=store.dojo_dir,
        capture_output=True, text=True,
    ).stdout.strip()
    assert status == "", f"audit left uncommitted changes: {status}"
