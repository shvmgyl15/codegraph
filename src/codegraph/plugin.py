from __future__ import annotations

import importlib.util
import sys
import traceback
from pathlib import Path

from codegraph.graph.types import UnifiedGraph


def _get_plugins_from_config(root: str) -> list[str]:
    from codegraph.config import load_config

    config = load_config(root)
    return list(config.plugins)


def run_plugins(graph: UnifiedGraph, root: str) -> None:
    plugins = _get_plugins_from_config(root)
    if not plugins:
        return

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

            if not hasattr(mod, "run"):
                print(
                    f"[codegraph] plugin {plugin_path} has no run(graph) function",
                    file=sys.stderr,
                )
                continue

            mod.run(graph)
        except Exception:
            print(
                f"[codegraph] plugin {plugin_path} raised an error:",
                file=sys.stderr,
            )
            traceback.print_exc(file=sys.stderr)
