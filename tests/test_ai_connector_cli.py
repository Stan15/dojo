import json
from helpers import run_cli


def test_connect_ai_command_persists_descriptor_defaults_and_default_marker(tmp_path):
    out = run_cli(tmp_path, "connect", "ai", "command", "hermes", "--default", "--", "hermes", "chat", "-Q", "--stdin").stdout
    connector = json.loads(out)
    assert connector["name"] == "hermes"
    assert connector["kind"] == "command"
    assert connector["argv"] == ["hermes", "chat", "-Q", "--stdin"]
    assert connector["input_mode"] == "stdin-prompt"
    assert connector["output_mode"] == "stdout-json-or-text"
    assert connector["timeout_seconds"] == 120
    assert connector["is_default"] is True
    assert connector["next"] == "dojo connect ai test hermes"

    listed = json.loads(run_cli(tmp_path, "connect", "ai", "list").stdout)
    assert listed[0]["name"] == "hermes"


def test_duplicate_requires_replace_and_replace_updates(tmp_path):
    run_cli(tmp_path, "connect", "ai", "command", "hermes", "--", "old")
    dup = run_cli(tmp_path, "connect", "ai", "command", "hermes", "--", "new", check=False)
    assert dup.returncode != 0
    assert "already exists" in dup.stderr

    out = run_cli(tmp_path, "connect", "ai", "command", "hermes", "--replace", "--timeout", "45", "--", "new").stdout
    connector = json.loads(out)
    assert connector["argv"] == ["new"]
    assert connector["timeout_seconds"] == 45


def test_use_moves_default_and_remove_default_requires_force(tmp_path):
    run_cli(tmp_path, "connect", "ai", "command", "hermes", "--default", "--", "hermes")
    run_cli(tmp_path, "connect", "ai", "command", "local", "--", "local-llm")

    used = json.loads(run_cli(tmp_path, "connect", "ai", "use", "local").stdout)
    assert used["is_default"] is True

    refused = run_cli(tmp_path, "connect", "ai", "remove", "local", check=False)
    assert refused.returncode != 0
    assert "refusing to remove default" in refused.stderr

    removed = json.loads(run_cli(tmp_path, "connect", "ai", "remove", "local", "--force").stdout)
    assert removed == {"removed": "local", "was_default": True}


def test_invalid_name_and_empty_command_fail(tmp_path):
    bad = run_cli(tmp_path, "connect", "ai", "command", "1bad", "--", "echo", check=False)
    assert bad.returncode != 0
    assert "invalid AI connector name" in bad.stderr

    empty = run_cli(tmp_path, "connect", "ai", "command", "empty", check=False)
    assert empty.returncode != 0
    assert "requires argv" in empty.stderr
