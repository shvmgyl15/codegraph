from __future__ import annotations

from pathlib import Path

from codegraph.graph.types import make_unified_graph
from codegraph.plugin import run_plugins
from tests.conftest import create_file  # noqa: F401

GOOD_PLUGIN = """
from codegraph.graph.types import make_unified_graph

def run(graph):
    graph.symbols.append({
        "id": "plugin::added",
        "name": "plugin_added",
        "kind": "function",
        "file": "plugin.py",
        "line": 1,
        "entry_name": "plugin",
        "language": "python",
        "type": "library",
    })
"""

NO_RUN_PLUGIN = """
x = 1
"""

RAISY_PLUGIN = """
def run(graph):
    raise RuntimeError("plugin oops")
"""


class TestRunPlugins:
    def test_runs_plugin_and_modifies_graph(self, temp_workspace: Path) -> None:
        create_file(temp_workspace / "codegraph.jsonc",
                    '{"version":1,"plugins":["my_plugin.py"]}')
        create_file(temp_workspace / "my_plugin.py", GOOD_PLUGIN)
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        assert len(graph.symbols) == 0
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 1
        assert graph.symbols[0]["name"] == "plugin_added"

    def test_missing_plugin_warns(self, temp_workspace: Path) -> None:
        create_file(temp_workspace / "codegraph.jsonc",
                    '{"version":1,"plugins":["ghost.py"]}')
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 0

    def test_plugin_with_no_run_function_warns(self, temp_workspace: Path) -> None:
        create_file(temp_workspace / "codegraph.jsonc",
                    '{"version":1,"plugins":["no_run.py"]}')
        create_file(temp_workspace / "no_run.py", NO_RUN_PLUGIN)
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 0

    def test_plugin_that_raises_warns_and_continues(self, temp_workspace: Path) -> None:
        create_file(temp_workspace / "codegraph.jsonc",
                    '{"version":1,"plugins":["raisy.py"]}')
        create_file(temp_workspace / "raisy.py", RAISY_PLUGIN)
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 0

    def test_no_plugins_no_op(self, temp_workspace: Path) -> None:
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 0

    def test_multiple_plugins_run_in_order(self, temp_workspace: Path) -> None:
        create_file(temp_workspace / "codegraph.jsonc",
                    '{"version":1,"plugins":["p1.py","p2.py"]}')
        create_file(temp_workspace / "p1.py", GOOD_PLUGIN)
        create_file(temp_workspace / "p2.py", GOOD_PLUGIN)
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 2

    def test_plugin_failure_does_not_block_next(self, temp_workspace: Path) -> None:
        create_file(temp_workspace / "codegraph.jsonc",
                    '{"version":1,"plugins":["raisy.py","good.py"]}')
        create_file(temp_workspace / "raisy.py", RAISY_PLUGIN)
        create_file(temp_workspace / "good.py", GOOD_PLUGIN)
        graph = make_unified_graph(workspace_root=str(temp_workspace))
        run_plugins(graph, str(temp_workspace))
        assert len(graph.symbols) == 1
        assert graph.symbols[0]["name"] == "plugin_added"
