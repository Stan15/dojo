"""dojo uninstall: reverses install without ever touching learning data, and
refuses to delete directories it doesn't own — an uninstaller that could eat a
user's unrelated files is worse than none."""
from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

import pytest

from dojo.cli import main


@pytest.fixture(autouse=True)
def no_git():
    with patch("dojo.store.engine.init_git"), patch("dojo.store.engine.commit_git"):
        yield


def run(capsys, *argv: str) -> tuple[int, dict]:
    rc = main(list(argv))
    return rc, json.loads(capsys.readouterr().out.strip().splitlines()[-1])


def test_uninstall_removes_dojo_owned_skill(tmp_path: Path, capsys):
    skill_dir = tmp_path / "skills" / "dojo"
    skill_dir.mkdir(parents=True)
    real_skill = Path(__file__).parent.parent / "skills" / "dojo" / "SKILL.md"
    (skill_dir / "SKILL.md").write_text(real_skill.read_text(encoding="utf-8"), encoding="utf-8")

    rc, data = run(capsys, "--db", str(tmp_path / "store"), "uninstall", "--dest", str(skill_dir))
    assert rc == 0 and data["removed"] == [str(skill_dir)]
    assert not skill_dir.exists()
    assert "learning data" in data["note"], "must reassure that data survives"


def test_uninstall_refuses_foreign_directories(tmp_path: Path, capsys):
    foreign = tmp_path / "skills" / "dojo"
    foreign.mkdir(parents=True)
    (foreign / "SKILL.md").write_text("---\nname: something-else\n---\nnot ours",
                                      encoding="utf-8")
    (foreign / "precious.txt").write_text("user data", encoding="utf-8")

    rc, data = run(capsys, "--db", str(tmp_path / "store"), "uninstall", "--dest", str(foreign))
    assert rc == 1 and not data["ok"]
    assert foreign.exists() and (foreign / "precious.txt").exists(), "nothing deleted"


def test_uninstall_missing_target_is_honest_noop(tmp_path: Path, capsys):
    rc, data = run(capsys, "--db", str(tmp_path / "store"), "uninstall",
                   "--dest", str(tmp_path / "nowhere"))
    assert rc == 0 and data["removed"] == []


def test_self_uninstall_reports_method_without_deleting_anything(tmp_path: Path, capsys):
    rc, data = run(capsys, "--db", str(tmp_path / "store"), "uninstall", "--self")
    assert rc == 0
    assert data["install_method"] in ("pipx", "venv", "binary", "pip")
    assert "uninstall" in data["run_this"] or "rm" in data["run_this"]
    assert "learning data" in data["note"]
