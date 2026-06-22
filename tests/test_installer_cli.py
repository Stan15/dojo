import json
import os
from helpers import run_cli

def test_install_hermes_and_openclaw(tmp_path):
    mock_home = tmp_path / "home"
    mock_home.mkdir()

    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(mock_home)
    try:
        # 1. Test installing hermes
        result_hermes = run_cli(tmp_path, "install", "hermes")
        assert result_hermes.returncode == 0

        # Check that it auto-outputs JSON in non-tty environment
        data_hermes = json.loads(result_hermes.stdout)
        assert data_hermes["ok"] is True
        assert data_hermes["type"] == "skill_installed"
        assert data_hermes["data"]["agent"] == "hermes"
        assert data_hermes["data"]["path"] == str(mock_home / ".hermes" / "skills" / "dojo")
        assert data_hermes["data"]["connector"]["name"] == "hermes"
        assert data_hermes["data"]["connector"]["is_default"] is True

        hermes_skill_file = mock_home / ".hermes" / "skills" / "dojo" / "SKILL.md"
        assert hermes_skill_file.exists()
        assert "Dojo Learning System Skill" in hermes_skill_file.read_text()

        # 2. Test reinstalling hermes (cleanup logic)
        result_reinstall = run_cli(tmp_path, "install", "hermes")
        assert result_reinstall.returncode == 0
        assert hermes_skill_file.exists()

        # 3. Test installing openclaw
        result_openclaw = run_cli(tmp_path, "install", "openclaw")
        assert result_openclaw.returncode == 0

        data_openclaw = json.loads(result_openclaw.stdout)
        assert data_openclaw["ok"] is True
        assert data_openclaw["type"] == "skill_installed"
        assert data_openclaw["data"]["agent"] == "openclaw"
        assert data_openclaw["data"]["path"] == str(mock_home / ".openclaw" / "skills" / "dojo")
        assert data_openclaw["data"]["connector"]["name"] == "openclaw"
        assert data_openclaw["data"]["connector"]["is_default"] is True

        openclaw_skill_file = mock_home / ".openclaw" / "skills" / "dojo" / "SKILL.md"
        assert openclaw_skill_file.exists()
        assert "Dojo Learning System Skill" in openclaw_skill_file.read_text()

        # 4. Test installing custom agent with custom destination and argv
        custom_dest = tmp_path / "custom_agent_skills" / "dojo"
        result_custom = run_cli(
            tmp_path,
            "install",
            "claude-code",
            "--dest", str(custom_dest),
            "--argv", "claude chat --stdin"
        )
        assert result_custom.returncode == 0
        data_custom = json.loads(result_custom.stdout)
        assert data_custom["ok"] is True
        assert data_custom["data"]["agent"] == "claude-code"
        assert data_custom["data"]["path"] == str(custom_dest)
        assert data_custom["data"]["connector"]["name"] == "claude-code"
        assert data_custom["data"]["connector"]["argv"] == ["claude", "chat", "--stdin"]
        assert data_custom["data"]["connector"]["is_default"] is True

        custom_skill_file = custom_dest / "SKILL.md"
        assert custom_skill_file.exists()
        assert "Dojo Learning System Skill" in custom_skill_file.read_text()

        # 5. Test install without agent or --dest in non-interactive (non-tty) mode fails
        result_no_agent = run_cli(tmp_path, "install", check=False)
        assert result_no_agent.returncode != 0
        assert "must specify agent name or --dest path" in result_no_agent.stderr
    finally:
        if old_home is not None:
            os.environ["HOME"] = old_home
        else:
            del os.environ["HOME"]


def test_installer_prevents_unowned_overwrite(tmp_path):
    mock_home = tmp_path / "home"
    mock_home.mkdir()

    old_home = os.environ.get("HOME")
    os.environ["HOME"] = str(mock_home)
    try:
        # Create an unowned skills/dojo directory
        target_dir = mock_home / ".hermes" / "skills" / "dojo"
        target_dir.mkdir(parents=True)
        (target_dir / "unrelated_file.txt").write_text("Hello")

        # 1. Try to install without --force (should fail)
        result_fail = run_cli(tmp_path, "install", "hermes", check=False)
        assert result_fail.returncode != 0
        assert "exists but does not appear to be owned by Dojo" in result_fail.stderr
        assert (target_dir / "unrelated_file.txt").exists()  # Kept intact!

        # 2. Install with --force (should succeed and overwrite)
        result_force = run_cli(tmp_path, "install", "hermes", "--force")
        assert result_force.returncode == 0
        assert not (target_dir / "unrelated_file.txt").exists()  # Overwritten!
        assert (target_dir / "SKILL.md").exists()
        assert "owner: github.com/Stan15/dojo" in (target_dir / "SKILL.md").read_text()
    finally:
        if old_home is not None:
            os.environ["HOME"] = old_home
        else:
            del os.environ["HOME"]
