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
    real_skill = Path(__file__).parent.parent / "src" / "dojo" / "skills" / "SKILL.md"
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


class TestInstallMethodDetection:
    """Pure-function pins for --self (owner-reported: resolving the venv
    symlink misdetected a venv install as bare pip on macOS/Homebrew)."""

    HOME = Path("/Users/someone")

    def _detect(self, **kw):
        from dojo.cli import _detect_install_method
        defaults = dict(
            executable=Path("/usr/bin/python3"), prefix=Path("/usr"),
            frozen=False, home=self.HOME, argv0=Path("dojo"),
        )
        defaults.update(kw)
        return _detect_install_method(**defaults)

    def test_install_sh_venv_detected_by_prefix_not_resolved_symlink(self):
        method, cmd = self._detect(
            prefix=self.HOME / ".dojo" / "venv",
            # what sys.executable RESOLVES to on macOS — must not matter
            executable=Path("/opt/homebrew/Cellar/python@3.13/3.13.11/Frameworks/"
                            "Python.framework/Versions/3.13/bin/python3.13"),
        )
        assert method == "venv"
        assert str(self.HOME / ".dojo") in cmd and ".local/bin/dojo" in cmd

    def test_pipx_detected(self):
        method, cmd = self._detect(
            prefix=self.HOME / ".local" / "pipx" / "venvs" / "dojo",
            executable=self.HOME / ".local" / "pipx" / "venvs" / "dojo" / "bin" / "python",
        )
        assert method == "pipx" and cmd == "pipx uninstall dojo"

    def test_frozen_binary_detected(self):
        method, cmd = self._detect(frozen=True, argv0=Path("/usr/local/bin/dojo"))
        assert method == "binary" and cmd == "rm /usr/local/bin/dojo"

    def test_bare_pip_fallback_uses_unresolved_executable(self):
        method, cmd = self._detect(executable=Path("/opt/python/bin/python3"))
        assert method == "pip" and cmd.startswith("/opt/python/bin/python3 -m pip uninstall")
