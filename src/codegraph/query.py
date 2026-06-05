from __future__ import annotations

from codegraph.graph.types import UnifiedGraph


class WorkspaceQuery:
    def __init__(self, graph: UnifiedGraph, root: str = ".") -> None:
        self.graph = graph
        self.root = root
