from __future__ import annotations

from pathlib import Path
from unittest.mock import patch

from codegraph.builder import build_all, build_and_write
from codegraph.graph.types import WorkspaceEntry
from tests.conftest import create_file, create_json  # noqa: F401


def _make_graph_data(entry_name: str, language: str, symbol_count: int = 3) -> dict:
    return {
        "schema_version": "1",
        "generated_at": "2026-01-01T00:00:00+00:00",
        "project_root": f"/fake/{entry_name}",
        "packages": [{"name": entry_name, "dir": f"/fake/{entry_name}"}],
        "files": [{"path": f"src/main.{language}", "lines": 50}],
        "symbols": [
            {
                "id": f"{entry_name}::func_{i}",
                "kind": "function",
                "name": f"func_{i}",
                "file": f"src/main.{language}",
                "line": i * 10,
            }
            for i in range(symbol_count)
        ],
        "calls": [
            {
                "caller_symbol_id": f"{entry_name}::func_0",
                "caller_name": "func_0",
                "callee_raw": "func_1",
                "file": f"src/main.{language}",
                "line": 5,
            }
        ],
        "imports": [{"from_file": f"src/main.{language}", "import_path": "os"}],
        "routes": [
            {
                "method": "GET",
                "path": "/api/test",
                "handler": "func_0",
                "file": f"src/main.{language}",
                "line": 1,
            }
        ],
        "env_reads": [
            {"key": "DATABASE_URL", "accessor": "os.getenv",
             "file": f"src/main.{language}", "line": 2},
        ],
        "errors": [
            {"message": "ValueError('bad')", "function_name": "func_1",
             "file": f"src/main.{language}", "line": 3},
        ],
        "test_edges": [
            {"test_func": "test_func_0", "target": "func_0",
             "file": f"src/test_main.{language}", "line": 1},
        ],
        "mutations": [],
        "implements": [],
        "blueprints": [],
        "blueprint_registrations": [],
        "template_refs": [],
        "extensions": [],
        "dependencies": [],
    }


def test_build_all_with_mock_graphs(temp_workspace: Path) -> None:
    go_entry = WorkspaceEntry(
        name="go-svc", language="go", type="service",
        path="go-svc", build_status="unbuilt",
    )
    ts_entry = WorkspaceEntry(
        name="ts-frontend", language="typescript", type="frontend",
        path="ts-frontend", build_status="unbuilt",
    )

    (temp_workspace / "go-svc" / ".gograph").mkdir(parents=True)
    create_json(
        temp_workspace / "go-svc" / ".gograph" / "graph.json",
        _make_graph_data("go-svc", "go"),
    )
    (temp_workspace / "ts-frontend" / ".tsgraph").mkdir(parents=True)
    create_json(
        temp_workspace / "ts-frontend" / ".tsgraph" / "graph.json",
        _make_graph_data("ts-frontend", "typescript"),
    )

    with patch("codegraph.builder._run_tool_build") as mock_build:
        def _fake_build(entry: WorkspaceEntry, root_path: Path) -> WorkspaceEntry:
            entry.build_status = "ok"
            entry.tool_version = "1.0.0"
            return entry

        mock_build.side_effect = _fake_build

        unified = build_all(
            str(temp_workspace),
            entries=[go_entry, ts_entry],
        )

    assert unified.manifest is not None
    assert len(unified.manifest.entries) == 2
    assert len(unified.symbols) == 6  # 3 per entry
    assert len(unified.calls) == 2
    assert len(unified.routes) == 2
    assert len(unified.env_reads) == 2
    assert len(unified.errors) == 2

    for sym in unified.symbols:
        assert "entry_name" in sym
        assert "language" in sym
        assert "type" in sym

    for call in unified.calls:
        assert "entry_name" in call


def test_build_and_write_creates_output(temp_workspace: Path) -> None:
    svc_dir = temp_workspace / "svc"
    svc_dir.mkdir()
    create_file(svc_dir / "go.mod", "module svc\n")
    create_file(svc_dir / "main.go", "package main\n")

    (svc_dir / ".gograph").mkdir(parents=True)
    create_json(
        svc_dir / ".gograph" / "graph.json",
        _make_graph_data("svc", "go", symbol_count=1),
    )

    with patch("codegraph.builder._run_tool_build") as mock_build:
        def _fake_build(entry: WorkspaceEntry, root_path: Path) -> WorkspaceEntry:
            entry.build_status = "ok"
            entry.tool_version = "1.0.0"
            return entry

        mock_build.side_effect = _fake_build

        out_path = build_and_write(str(temp_workspace))

    assert out_path.exists()
    assert out_path.name == "workspace.graph.json"
    assert out_path.parent.name == ".codegraph"

    import json as _json
    data = _json.loads(out_path.read_text())
    assert data["schema_version"] == "1"
    assert len(data["symbols"]) == 1


def test_unsupported_language_is_skipped(temp_workspace: Path) -> None:
    rust_entry = WorkspaceEntry(
        name="rust-crate", language="rust", type="library",
        path="rust-crate", build_status="unsupported",
    )

    with patch("codegraph.builder._run_tool_build") as mock_build:
        unified = build_all(
            str(temp_workspace),
            entries=[rust_entry],
        )

    assert unified.manifest is not None
    assert unified.manifest.entries[0].build_status == "unsupported"
    assert len(unified.symbols) == 0
    mock_build.assert_not_called()


def test_failed_build_does_not_collect(temp_workspace: Path) -> None:
    entry = WorkspaceEntry(
        name="broken", language="go", type="service",
        path="broken", build_status="unbuilt",
    )

    with patch("codegraph.builder._run_tool_build") as mock_build:
        def _fake_build(entry: WorkspaceEntry, root_path: Path) -> WorkspaceEntry:
            entry.build_status = "failed"
            return entry

        mock_build.side_effect = _fake_build

        unified = build_all(
            str(temp_workspace),
            entries=[entry],
        )

    assert unified.manifest is not None
    assert unified.manifest.entries[0].build_status == "failed"
    assert len(unified.symbols) == 0
