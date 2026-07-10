from __future__ import annotations

import io
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch
from contextlib import redirect_stdout, redirect_stderr
import pytest

from dojo.schemas import (
    Source,
    Campaign,
    Exercise,
    Candidate,
    Attempt,
    Insight,
    PracticeSession,
    AttackPlanPhase,
    CriteriaEntry
)
from dojo.store import DojoStore, slugify
from dojo.api import DojoAPI
from dojo.cli import main

# ==========================================
# Mock Git Operations Globally
# ==========================================

@pytest.fixture(autouse=True)
def mock_git_operations():
    with patch("dojo.store.engine.init_git") as mock_init, patch("dojo.store.engine.commit_git") as mock_commit:
        yield mock_init, mock_commit


# ==========================================
# CLI Runner Helper
# ==========================================

class MockCompletedProcess:
    def __init__(self, returncode: int, stdout: str, stderr: str):
        self.returncode = returncode
        self.stdout = stdout
        self.stderr = stderr


def run_cli(tmp_path: Path, *args: str, check: bool = True) -> MockCompletedProcess:
    cli_args = ["--db", str(tmp_path)] + list(args)
    stdout_buf = io.StringIO()
    stderr_buf = io.StringIO()
    returncode = 0
    try:
        with redirect_stdout(stdout_buf), redirect_stderr(stderr_buf):
            try:
                ret = main(cli_args)
                if ret is not None:
                    returncode = ret
            except SystemExit as exc:
                if isinstance(exc.code, int):
                    returncode = exc.code
                elif exc.code is None:
                    returncode = 0
                else:
                    returncode = 1
                    stderr_buf.write(str(exc.code))
    except Exception as e:
        returncode = 1
        stderr_buf.write(str(e))
        
    stdout = stdout_buf.getvalue()
    stderr = stderr_buf.getvalue()
    
    if check and returncode != 0:
        raise AssertionError(f"command failed: {cli_args}\nstdout={stdout}\nstderr={stderr}")
        
    return MockCompletedProcess(returncode, stdout, stderr)


# ==========================================
# Schema Tests
# ==========================================

def test_pydantic_exclude_defaults_frontmatter(tmp_path: Path):
    store = DojoStore(tmp_path)
    
    # Save a source note, check defaults omission
    source = Source(
        id="src_test",
        title="Test Source",
        kind="text",
        content="Test content lines here."
    )
    store.sources.save(source)
    
    source_file = tmp_path / "sources" / "src_test.md"
    assert source_file.exists()
    content = source_file.read_text(encoding="utf-8")
    
    # Default parameters should not be serialized
    assert "mission:" not in content
    assert "path:" not in content
    
    # Reload and check values
    reloaded = store.sources.get("src_test")
    assert reloaded is not None
    assert reloaded.title == "Test Source"
    assert reloaded.mission is None
    assert reloaded.content == "Test content lines here."


# ==========================================
# Store Tests
# ==========================================

def test_store_atomic_write_and_locking(tmp_path: Path):
    store = DojoStore(tmp_path)
    
    # Perform standard writes, verify lock file exists during transaction
    campaign = Campaign(
        id="test",
        name="Test Campaign",
        mission="Succeed"
    )
    store.campaigns.save(campaign)
    
    campaign_file = tmp_path / "campaigns" / "camp_test" / "campaign.md"
    assert campaign_file.exists()
    
    # Locking is transient, but make sure dojo.lock is created or managed
    assert (tmp_path / "dojo.lock").exists()


def test_store_incremental_index_sync(tmp_path: Path):
    store = DojoStore(tmp_path)
    
    source = Source(
        id="src_1",
        title="Source One",
        kind="text",
        content="Hello source text"
    )
    store.sources.save(source)
    
    # Check index cache created
    index_file = tmp_path / ".index.json"
    assert index_file.exists()
    
    # Reload index directly
    index_data = json.loads(index_file.read_text(encoding="utf-8"))
    assert "sources/src_1.md" in index_data["files"]
    
    # Modify file mtime artificially, reload
    file_path = tmp_path / "sources" / "src_1.md"
    os.utime(file_path, (file_path.stat().st_atime, file_path.stat().st_mtime - 100))
    
    # Reload store
    store2 = DojoStore(tmp_path)
    assert store2.sources.get("src_1").title == "Source One"


# ==========================================
# Doctor and Install Gate Tests
# ==========================================

def test_dojo_doctor_clean_and_dirty(tmp_path: Path):
    # 1. Clean run on freshly initialized empty directory (JSON output by default)
    res = run_cli(tmp_path, "doctor")
    data = json.loads(res.stdout)
    assert data["ok"] is True
    assert data["errors"] == []
    assert res.returncode == 0

    # Human-friendly print verification
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor")
        assert "Repository directory is completely compliant and clean" in res.stdout
        assert res.returncode == 0

    # 3. Dirty run with unexpected file at root
    dirty_file = tmp_path / "unexpected.txt"
    dirty_file.write_text("random file content", encoding="utf-8")
    
    # JSON verification
    res = run_cli(tmp_path, "doctor", check=False)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "Unexpected file at root: unexpected.txt" in data["errors"]

    # Human-readable verification
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor", check=False)
        assert res.returncode == 1
        assert "Dojo Doctor Diagnostics" in res.stdout
        assert "Unexpected file at root: unexpected.txt" in res.stdout
        assert "Dojo Doctor found 1 issues" in res.stdout

    # 4. Clean up dirty file, verify it works again
    dirty_file.unlink()
    res = run_cli(tmp_path, "doctor")
    assert res.returncode == 0


def test_dojo_doctor_catches_broken_install(tmp_path: Path):
    """Installation integrity: a registered task kind whose prompt template
    is not packaged must fail doctor — install.sh gates on it — instead of
    surfacing as a TemplateError mid-conversation (owner field report
    2026-07-09)."""
    with patch.dict("dojo.tasks.compiler.TEMPLATES", {"fake.kind": "nope.md"}):
        res = run_cli(tmp_path, "doctor", check=False)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert any("nope.md" in e for e in data["errors"])


def test_dojo_doctor_validation_errors(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    
    # Invalid markdown in campaigns (missing campaign.md)
    camp_dir = tmp_path / "campaigns" / "camp_invalid"
    camp_dir.mkdir(parents=True, exist_ok=True)
    
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor", check=False)
        assert res.returncode == 1
        assert "Missing required 'campaign.md'" in res.stdout

    # Invalid YAML frontmatter / schema violation in campaign.md
    camp_md = camp_dir / "campaign.md"
    camp_md.write_text("---\nid: different_id\nname: Test\n---\nSyllabus outline", encoding="utf-8")
    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "doctor", check=False)
        assert res.returncode == 1
        assert "Invalid campaign file" in res.stdout


def test_dojo_install_safety_gate(tmp_path: Path):
    tmp_path.mkdir(parents=True, exist_ok=True)
    dirty_file = tmp_path / "unknown_file.txt"
    dirty_file.write_text("something", encoding="utf-8")

    # Trying to install should fail loudly because repository is dirty
    res = run_cli(tmp_path, "install", "hermes", "--dest", str(tmp_path / "hermes_skill"), check=False)
    assert res.returncode == 1
    data = json.loads(res.stdout)
    assert data["ok"] is False
    assert "Dojo repository validation failed" in data["error"]
    assert "Unexpected file at root: unknown_file.txt" in data["errors"]

    with patch("dojo.cli._use_json", return_value=False):
        res = run_cli(tmp_path, "install", "hermes", "--dest", str(tmp_path / "hermes_skill"), check=False)
        assert res.returncode == 1
        assert "Dojo Doctor found issues in your repository" in res.stdout
        assert "To bypass this check, run install with --force" in res.stdout
        assert not (tmp_path / "hermes_skill").exists()

    # Installing with --force should succeed
    with patch("dojo.cli._is_owned_by_dojo", return_value=True):
        res = run_cli(tmp_path, "install", "hermes", "--dest", str(tmp_path / "hermes_skill"), "--force")
        assert res.returncode == 0
        assert (tmp_path / "hermes_skill").exists()
