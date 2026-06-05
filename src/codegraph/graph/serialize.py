from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from codegraph.graph.types import (  # noqa: F401
    SCHEMA_VERSION,
    Manifest,
    UnifiedGraph,
    WorkspaceEntry,
)

ARRAY_FIELDS: set[str] = {
    "packages", "files", "symbols", "calls", "imports", "routes",
    "env_reads", "errors", "test_edges", "mutations", "implements",
    "blueprints", "blueprint_registrations", "template_refs",
    "extensions", "dependencies", "http_calls", "cross_service_edges",
}

REQUIRED_FIELDS: set[str] = {
    "packages", "files", "symbols", "calls", "imports", "routes",
    "env_reads", "errors", "test_edges", "mutations", "implements",
    "blueprints", "blueprint_registrations", "template_refs",
    "extensions", "dependencies",
} | {"schema_version", "generated_at", "workspace_root"}


def _filter_none(obj: dict[str, Any]) -> dict[str, Any]:
    return {k: v for k, v in obj.items() if v is not None}


def _entry_to_dict(entry: WorkspaceEntry) -> dict[str, Any]:
    return _filter_none(asdict(entry))


def _manifest_to_dict(manifest: Manifest) -> dict[str, Any]:
    return {
        "generated_at": manifest.generated_at,
        "workspace_root": manifest.workspace_root,
        "entries": [_entry_to_dict(e) for e in manifest.entries],
    }


def _dict_to_entry(data: dict[str, Any]) -> WorkspaceEntry:
    return WorkspaceEntry(**data)


def _dict_to_manifest(data: dict[str, Any]) -> Manifest:
    return Manifest(
        generated_at=data.get("generated_at", ""),
        workspace_root=data.get("workspace_root", ""),
        entries=[_dict_to_entry(e) for e in data.get("entries", [])],
    )


def graph_to_dict(graph: UnifiedGraph) -> dict[str, Any]:
    result: dict[str, Any] = {
        "schema_version": graph.schema_version,
        "generated_at": graph.generated_at,
        "workspace_root": graph.workspace_root,
    }
    if graph.manifest is not None:
        result["manifest"] = _manifest_to_dict(graph.manifest)
    for field_name in ARRAY_FIELDS:
        items = getattr(graph, field_name, [])
        result[field_name] = [item for item in items]
    return result


def dict_to_graph(data: dict[str, Any]) -> UnifiedGraph:
    kwargs: dict[str, Any] = {
        "schema_version": data.get("schema_version", SCHEMA_VERSION),
        "generated_at": data.get("generated_at", ""),
        "workspace_root": data.get("workspace_root", ""),
    }
    raw_manifest = data.get("manifest")
    if raw_manifest is not None:
        kwargs["manifest"] = _dict_to_manifest(raw_manifest)
    for field_name in ARRAY_FIELDS:
        kwargs[field_name] = data.get(field_name, [])
    return UnifiedGraph(**kwargs)


def serialize(graph: UnifiedGraph) -> str:
    if graph.schema_version != SCHEMA_VERSION:
        msg = f"Graph version mismatch: expected {SCHEMA_VERSION}, got {graph.schema_version}"
        raise ValueError(msg)
    return json.dumps(graph_to_dict(graph), indent=2)


def _ensure_fields(parsed: dict[str, Any]) -> None:
    for field_name in REQUIRED_FIELDS:
        if field_name not in parsed:
            msg = f"Missing required field: {field_name}"
            raise ValueError(msg)
    for field_name in ARRAY_FIELDS:
        if field_name in parsed and not isinstance(parsed[field_name], list):
            msg = f"Field '{field_name}' must be a list"
            raise ValueError(msg)


def deserialize(json_str: str) -> UnifiedGraph:
    try:
        parsed = json.loads(json_str)
    except json.JSONDecodeError as e:
        msg = f"Invalid JSON: {e}"
        raise ValueError(msg) from e

    if not isinstance(parsed, dict):
        msg = "Invalid graph structure: expected a JSON object"
        raise ValueError(msg)

    _ensure_fields(parsed)

    if parsed["schema_version"] != SCHEMA_VERSION:
        msg = (
            f"Graph version mismatch: expected {SCHEMA_VERSION}, "
            f"got {parsed['schema_version']}"
        )
        raise ValueError(msg)

    return dict_to_graph(parsed)


def write_graph(graph: UnifiedGraph, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(serialize(graph))


def write_manifest(manifest: Manifest, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w") as f:
        f.write(json.dumps(_manifest_to_dict(manifest), indent=2))


def read_graph(path: Path) -> UnifiedGraph:
    with open(path) as f:
        return deserialize(f.read())
