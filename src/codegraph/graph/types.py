from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

SCHEMA_VERSION = "1"


@dataclass
class WorkspaceEntry:
    name: str = ""
    language: str = ""
    type: str = "library"
    path: str = ""
    build_status: str = "unbuilt"
    build_duration_ms: int = 0
    tool_version: str = ""
    symbol_count: int = 0
    call_count: int = 0
    route_count: int = 0


@dataclass
class Manifest:
    generated_at: str = ""
    workspace_root: str = ""
    entries: list[WorkspaceEntry] = field(default_factory=list)


@dataclass
class UnifiedGraph:
    schema_version: str = SCHEMA_VERSION
    generated_at: str = ""
    workspace_root: str = ""
    manifest: Manifest | None = None
    packages: list[dict[str, Any]] = field(default_factory=list)
    files: list[dict[str, Any]] = field(default_factory=list)
    symbols: list[dict[str, Any]] = field(default_factory=list)
    calls: list[dict[str, Any]] = field(default_factory=list)
    imports: list[dict[str, Any]] = field(default_factory=list)
    routes: list[dict[str, Any]] = field(default_factory=list)
    env_reads: list[dict[str, Any]] = field(default_factory=list)
    errors: list[dict[str, Any]] = field(default_factory=list)
    test_edges: list[dict[str, Any]] = field(default_factory=list)
    mutations: list[dict[str, Any]] = field(default_factory=list)
    implements: list[dict[str, Any]] = field(default_factory=list)
    blueprints: list[dict[str, Any]] = field(default_factory=list)
    blueprint_registrations: list[dict[str, Any]] = field(default_factory=list)
    template_refs: list[dict[str, Any]] = field(default_factory=list)
    extensions: list[dict[str, Any]] = field(default_factory=list)
    dependencies: list[dict[str, Any]] = field(default_factory=list)


def make_unified_graph(workspace_root: str = "") -> UnifiedGraph:
    return UnifiedGraph(
        schema_version=SCHEMA_VERSION,
        generated_at=datetime.now(UTC).isoformat(),
        workspace_root=workspace_root,
        manifest=Manifest(
            generated_at=datetime.now(UTC).isoformat(),
            workspace_root=workspace_root,
        ),
    )
