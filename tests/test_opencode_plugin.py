from __future__ import annotations

import json
from pathlib import Path

from codegraph.graph.types import make_unified_graph
from codegraph.query import WorkspaceQuery
from codegraph.server import add_opencode_plugin, set_query_override


class TestAddOpencodePlugin:
    def test_writes_config_file(self, temp_workspace: Path) -> None:
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        q = WorkspaceQuery(graph, root=str(temp_workspace))
        set_query_override(q)
        try:
            result = add_opencode_plugin(root=str(temp_workspace))
            assert "Created" in result
            config_path = temp_workspace / ".opencode.json"
            assert config_path.exists()
            data = json.loads(config_path.read_text())
            assert "mcp_servers" in data
            assert "codegraph" in data["mcp_servers"]
            assert "agents" in data
            assert "architect" in data["agents"]
        finally:
            set_query_override(None)

    def test_contains_mcp_command(self, temp_workspace: Path) -> None:
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        q = WorkspaceQuery(graph, root=str(temp_workspace))
        set_query_override(q)
        try:
            result = add_opencode_plugin(root=str(temp_workspace))
            assert "Created" in result
            data = json.loads((temp_workspace / ".opencode.json").read_text())
            args = data["mcp_servers"]["codegraph"]["args"]
            assert "codegraph" in args
            assert "mcp" in args
        finally:
            set_query_override(None)

    def test_writes_valid_json(self, temp_workspace: Path) -> None:
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        q = WorkspaceQuery(graph, root=str(temp_workspace))
        set_query_override(q)
        try:
            result = add_opencode_plugin(root=str(temp_workspace))
            assert "Created" in result
            raw = (temp_workspace / ".opencode.json").read_text()
            json.loads(raw)
        finally:
            set_query_override(None)
