from __future__ import annotations

from pathlib import Path

import pytest

from codegraph.graph.serialize import deserialize, read_graph, serialize, write_graph
from codegraph.graph.types import WorkspaceEntry, make_unified_graph


def test_roundtrip_empty_graph(temp_workspace: Path) -> None:
    graph = make_unified_graph(workspace_root=str(temp_workspace))
    serialized = serialize(graph)
    deserialized = deserialize(serialized)
    assert deserialized.schema_version == graph.schema_version
    assert deserialized.workspace_root == graph.workspace_root


def test_roundtrip_with_entries(temp_workspace: Path) -> None:
    graph = make_unified_graph(workspace_root=str(temp_workspace))
    assert graph.manifest is not None
    graph.manifest.entries = [
        WorkspaceEntry(
            name="svc-a", language="go", type="service",
            path="./svc-a", build_status="ok",
        ),
    ]
    graph.symbols = [
        {"id": "svc-a::f1", "name": "f1",
         "entry_name": "svc-a", "language": "go", "type": "service"},
    ]
    graph.calls = [
        {"caller_name": "f1", "callee_raw": "f2",
         "entry_name": "svc-a", "language": "go", "type": "service"},
    ]
    graph.routes = [
        {"method": "GET", "path": "/api", "handler": "f1",
         "entry_name": "svc-a", "language": "go", "type": "service"},
    ]

    serialized = serialize(graph)
    deserialized = deserialize(serialized)

    assert deserialized.manifest is not None
    assert len(deserialized.manifest.entries) == 1
    assert deserialized.manifest.entries[0].name == "svc-a"
    assert len(deserialized.symbols) == 1
    assert deserialized.symbols[0]["name"] == "f1"
    assert len(deserialized.calls) == 1
    assert len(deserialized.routes) == 1


def test_write_and_read_graph(temp_workspace: Path) -> None:
    graph = make_unified_graph(workspace_root=str(temp_workspace))
    out_path = temp_workspace / ".codegraph" / "workspace.graph.json"

    write_graph(graph, out_path)
    assert out_path.exists()

    loaded = read_graph(out_path)
    assert loaded.schema_version == graph.schema_version
    assert loaded.workspace_root == graph.workspace_root


def test_deserialize_invalid_json() -> None:
    with pytest.raises(ValueError, match="Invalid JSON"):
        deserialize("not json")


def test_deserialize_missing_fields() -> None:
    with pytest.raises(ValueError, match="Missing required field"):
        deserialize('{"schema_version": "1"}')


def test_deserialize_version_mismatch() -> None:
    data = (
        '{"schema_version": "999", "generated_at": "", "workspace_root": "",'
        '"packages": [], "files": [], "symbols": [], "calls": [], "imports": [],'
        '"routes": [], "env_reads": [], "errors": [], "test_edges": [],'
        '"mutations": [], "implements": [], "blueprints": [],'
        '"blueprint_registrations": [], "template_refs": [],'
        '"extensions": [], "dependencies": []}'
    )
    with pytest.raises(ValueError, match="Graph version mismatch"):
        deserialize(data)
