from __future__ import annotations

from pathlib import Path

import pytest

from codegraph.config import find_config, load_config
from tests.conftest import create_file, create_json  # noqa: F401


def test_no_config_file_returns_default(temp_workspace: Path) -> None:
    config = load_config(str(temp_workspace))
    assert config.version == 1
    assert config.auto_discover is True
    assert config.entries == []


def test_find_config_returns_none_when_missing(temp_workspace: Path) -> None:
    assert find_config(str(temp_workspace)) is None


def test_find_config_finds_jsonc(temp_workspace: Path) -> None:
    cfg = create_file(temp_workspace / "codegraph.jsonc", "{}")
    found = find_config(str(temp_workspace))
    assert found == cfg


def test_find_config_finds_json(temp_workspace: Path) -> None:
    cfg = create_file(temp_workspace / "codegraph.json", "{}")
    found = find_config(str(temp_workspace))
    assert found == cfg


def test_jsonc_with_comments(temp_workspace: Path) -> None:
    create_file(
        temp_workspace / "codegraph.jsonc",
        """{
  "version": 1,
  "auto_discover": false,
  "entries": [
    // a frontend service
    { "name": "frontend", "path": "./frontend", "language": "typescript", "type": "frontend" }
  ]
}""",
    )
    config = load_config(str(temp_workspace))
    assert config.version == 1
    assert config.auto_discover is False
    assert len(config.entries) == 1
    assert config.entries[0].name == "frontend"
    assert config.entries[0].language == "typescript"
    assert config.entries[0].type == "frontend"


def test_load_explicit_entries(temp_workspace: Path) -> None:
    create_json(
        temp_workspace / "codegraph.jsonc",
        {
            "version": 1,
            "auto_discover": False,
            "entries": [
                {"name": "svc-a", "path": "./svc-a", "language": "go", "type": "service"},
                {"name": "lib-x", "path": "./libs/x", "language": "python", "type": "library"},
            ],
        },
    )
    config = load_config(str(temp_workspace))
    assert len(config.entries) == 2
    assert config.entries[0].name == "svc-a"
    assert config.entries[1].type == "library"


def test_invalid_version_raises(temp_workspace: Path) -> None:
    create_json(
        temp_workspace / "codegraph.jsonc",
        {"version": 999},
    )
    with pytest.raises(ValueError, match="Unsupported config version"):
        load_config(str(temp_workspace))


def test_invalid_json_raises(temp_workspace: Path) -> None:
    create_file(temp_workspace / "codegraph.jsonc", "not json")
    with pytest.raises(ValueError, match="Invalid config"):
        load_config(str(temp_workspace))
