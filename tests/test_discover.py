from __future__ import annotations

from pathlib import Path

from codegraph.config import CodegraphConfig, EntryConfig
from codegraph.discover import auto_discover, resolve_entries
from tests.conftest import create_file  # noqa: F401


def _setup_go_service(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "go.mod", "module test\n")
    create_file(d / "main.go", "package main\n")
    return d


def _setup_go_library(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "go.mod", "module test\n")
    return d


def _setup_ts_library(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "package.json", '{"name": "test"}\n')
    return d


def _setup_ts_frontend(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "package.json", '{"dependencies": {"next": "14.0.0"}}\n')
    return d


def _setup_python_library(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "pyproject.toml", '[project]\nname = "test"\n')
    return d


def _setup_rust(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "Cargo.toml", '[package]\nname = "test"\n')
    return d


def _setup_java(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "pom.xml", "<project></project>\n")
    return d


def test_auto_discover_go_service(temp_workspace: Path) -> None:
    _setup_go_service(temp_workspace, "user-svc")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].name == "user-svc"
    assert entries[0].language == "go"
    assert entries[0].type == "service"
    assert entries[0].build_status == "unbuilt"


def test_auto_discover_go_library(temp_workspace: Path) -> None:
    _setup_go_library(temp_workspace, "go-lib")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].language == "go"
    assert entries[0].type == "library"


def _setup_rn_mobile(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "package.json", '{"dependencies": {"react-native": "0.76.0"}}\n')
    return d


def _setup_expo_mobile(ws: Path, name: str) -> Path:
    d = ws / name
    create_file(d / "package.json", '{"dependencies": {"expo": "52.0.0"}}\n')
    return d


def test_auto_discover_ts_frontend(temp_workspace: Path) -> None:
    _setup_ts_frontend(temp_workspace, "frontend")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].name == "frontend"
    assert entries[0].language == "typescript"
    assert entries[0].type == "frontend"


def test_auto_discover_ts_library(temp_workspace: Path) -> None:
    _setup_ts_library(temp_workspace, "ts-lib")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].language == "typescript"
    assert entries[0].type == "library"


def test_auto_discover_rn_mobile(temp_workspace: Path) -> None:
    _setup_rn_mobile(temp_workspace, "mobile-app")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].name == "mobile-app"
    assert entries[0].language == "typescript"
    assert entries[0].type == "mobile"


def test_auto_discover_expo_mobile(temp_workspace: Path) -> None:
    _setup_expo_mobile(temp_workspace, "expo-app")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].name == "expo-app"
    assert entries[0].language == "typescript"
    assert entries[0].type == "mobile"


def test_auto_discover_python_library(temp_workspace: Path) -> None:
    _setup_python_library(temp_workspace, "py-lib")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].language == "python"
    assert entries[0].type == "library"


def test_auto_discover_rust(temp_workspace: Path) -> None:
    _setup_rust(temp_workspace, "rust-crate")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].language == "rust"
    assert entries[0].type == "library"
    assert entries[0].build_status == "unsupported"


def test_auto_discover_java(temp_workspace: Path) -> None:
    _setup_java(temp_workspace, "java-app")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].language == "java"
    assert entries[0].type == "library"
    assert entries[0].build_status == "unsupported"


def test_auto_discover_mixed_workspace(temp_workspace: Path) -> None:
    _setup_go_service(temp_workspace, "go-svc")
    _setup_ts_frontend(temp_workspace, "frontend")
    _setup_python_library(temp_workspace, "py-lib")
    _setup_rust(temp_workspace, "rust-crate")
    entries = auto_discover(str(temp_workspace))
    names = {e.name for e in entries}
    assert names == {"go-svc", "frontend", "py-lib", "rust-crate"}
    langs = {e.language for e in entries}
    assert langs == {"go", "typescript", "python", "rust"}


def test_auto_discover_skips_hidden_and_common_dirs(temp_workspace: Path) -> None:
    _setup_go_service(temp_workspace, "my-svc")
    _setup_go_service(temp_workspace, ".git")
    _setup_go_service(temp_workspace, "node_modules")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].name == "my-svc"


def test_resolve_entries_with_auto_discover(temp_workspace: Path) -> None:
    _setup_go_service(temp_workspace, "svc-a")
    _setup_python_library(temp_workspace, "lib-x")
    config = CodegraphConfig()
    entries = resolve_entries(config, str(temp_workspace))
    assert len(entries) == 2


def test_resolve_entries_no_auto_discover_no_explicit(temp_workspace: Path) -> None:
    config = CodegraphConfig(auto_discover=False)
    entries = resolve_entries(config, str(temp_workspace))
    assert entries == []


def test_resolve_entries_explicit_only(temp_workspace: Path) -> None:
    (temp_workspace / "svc-a").mkdir(parents=True, exist_ok=True)
    config = CodegraphConfig(
        auto_discover=False,
        entries=[
            EntryConfig(name="svc-a", path="./svc-a", language="go", type="service"),
        ],
    )
    entries = resolve_entries(config, str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].name == "svc-a"
    assert entries[0].language == "go"
    assert entries[0].build_status == "unbuilt"


def test_resolve_entries_type_override(temp_workspace: Path) -> None:
    _setup_python_library(temp_workspace, "py-lib")
    config = CodegraphConfig(
        entries=[
            EntryConfig(name="py-lib", path="./py-lib", language="python", type="service"),
        ],
    )
    entries = resolve_entries(config, str(temp_workspace))
    assert len(entries) == 1
    assert entries[0].type == "service"


def test_skips_non_project_directories(temp_workspace: Path) -> None:
    (temp_workspace / "docs").mkdir()
    (temp_workspace / "scripts").mkdir()
    (temp_workspace / "random").mkdir()
    _setup_go_service(temp_workspace, "svc")
    entries = auto_discover(str(temp_workspace))
    assert len(entries) == 1
