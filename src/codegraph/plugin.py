from __future__ import annotations

import importlib.util
import sys
import traceback
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from codegraph.graph.types import UnifiedGraph


@dataclass
class MCPTool:
    name: str
    description: str
    input_schema: dict[str, Any] = field(default_factory=dict)
    handler: Callable[[dict[str, Any], UnifiedGraph], str] | None = None


def _get_plugins_from_config(root: str) -> list[str]:
    from codegraph.config import load_config

    config = load_config(root)
    return list(config.plugins)


def run_plugins(graph: UnifiedGraph, root: str) -> list[MCPTool]:
    plugins = _get_plugins_from_config(root)
    tools: list[MCPTool] = []

    if not plugins:
        return tools

    root_path = Path(root).resolve()
    for plugin_rel in plugins:
        plugin_path = (root_path / plugin_rel).resolve()
        if not plugin_path.exists():
            print(
                f"[codegraph] plugin not found: {plugin_path}",
                file=sys.stderr,
            )
            continue

        try:
            spec = importlib.util.spec_from_file_location(
                f"_codegraph_plugin_{plugin_path.stem}", plugin_path
            )
            if spec is None or spec.loader is None:
                print(
                    f"[codegraph] failed to load plugin: {plugin_path}",
                    file=sys.stderr,
                )
                continue

            mod = importlib.util.module_from_spec(spec)
            sys.modules[mod.__name__] = mod
            spec.loader.exec_module(mod)

            if hasattr(mod, "run"):
                mod.run(graph)

            if hasattr(mod, "register_tools"):
                plugin_tools = mod.register_tools(graph)
                if plugin_tools:
                    tools.extend(plugin_tools)
        except Exception:
            print(
                f"[codegraph] plugin {plugin_path} raised an error:",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)

    return tools
