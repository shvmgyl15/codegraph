from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from codegraph.config import load_config
from codegraph.discover import BUILT_LANGUAGES, resolve_entries
from codegraph.graph.serialize import write_graph, write_manifest
from codegraph.graph.types import UnifiedGraph, WorkspaceEntry, make_unified_graph

TOOL_BY_LANGUAGE: dict[str, str] = {
    "go": "gograph",
    "python": "pygraph",
    "typescript": "tsgraph",
}

GRAPH_FILE_BY_LANGUAGE: dict[str, str] = {
    "go": ".gograph/graph.json",
    "python": ".pygraph/graph.json",
    "typescript": ".tsgraph/graph.json",
}


def _run_tool_build(entry: WorkspaceEntry, root_path: Path) -> WorkspaceEntry:
    tool = TOOL_BY_LANGUAGE.get(entry.language)
    if tool is None:
        entry.build_status = "unsupported"
        return entry

    entry_path = root_path / entry.path
    if not entry_path.is_dir():
        entry.build_status = "failed"
        return entry

    start = time.monotonic()
    try:
        result = subprocess.run(
            [tool, "build", "--root", str(entry_path)],
            capture_output=True, text=True, timeout=120,
            cwd=str(entry_path),
        )
        elapsed = int((time.monotonic() - start) * 1000)
        entry.build_duration_ms = elapsed

        if result.returncode != 0:
            entry.build_status = "failed"
            return entry

        entry.build_status = "ok"

        try:
            version_result = subprocess.run(
                [tool, "--version"],
                capture_output=True, text=True, timeout=10,
            )
            ver = version_result.stdout.strip() if version_result.returncode == 0 else ""
            entry.tool_version = ver
        except (OSError, subprocess.SubprocessError, subprocess.TimeoutExpired):
            entry.tool_version = ""

    except (OSError, subprocess.TimeoutExpired, subprocess.SubprocessError):
        entry.build_status = "failed"

    return entry


def _prefix_ids(items: list[dict[str, Any]], prefix: str, id_fields: set[str]) -> None:
    for item in items:
        for field in id_fields:
            if field in item and isinstance(item[field], str):
                item[field] = f"{prefix}::{item[field]}"


SYMBOL_ID_FIELDS = {"id"}
CALL_ID_FIELDS = {"caller_symbol_id"}
FILE_ID_FIELDS = {"id"}
PACKAGE_ID_FIELDS = {"id"}
TEST_EDGE_ID_FIELDS = {"test_func", "target"}
ERROR_ID_FIELDS = {"function_name"}
MUTATION_ID_FIELDS = {"function_name"}
ENV_ID_FIELDS = {"function_name"}
IMPLEMENTS_ID_FIELDS = {"interface", "concrete"}


def _stamp_and_collect(
    entry: WorkspaceEntry,
    root_path: Path,
    unified: UnifiedGraph,
) -> None:
    graph_rel = GRAPH_FILE_BY_LANGUAGE.get(entry.language)
    if graph_rel is None:
        return

    graph_path = root_path / entry.path / graph_rel
    if not graph_path.exists():
        return

    try:
        raw = graph_path.read_text()
        data: dict[str, Any] = json.loads(raw)
    except (OSError, json.JSONDecodeError, ValueError):
        return

    entry_name = entry.name
    prefix = entry_name

    packages = data.get("packages", [])
    _prefix_ids(packages, prefix, PACKAGE_ID_FIELDS)
    for p in packages:
        p["entry_name"] = entry_name
        p["language"] = entry.language
        p["type"] = entry.type
    unified.packages.extend(packages)

    files = data.get("files", [])
    _prefix_ids(files, prefix, FILE_ID_FIELDS)
    for f in files:
        f["entry_name"] = entry_name
        f["language"] = entry.language
        f["type"] = entry.type
    unified.files.extend(files)

    symbols = data.get("symbols", [])
    _prefix_ids(symbols, prefix, SYMBOL_ID_FIELDS)
    for s in symbols:
        s["entry_name"] = entry_name
        s["language"] = entry.language
        s["type"] = entry.type
    unified.symbols.extend(symbols)
    entry.symbol_count = len(symbols)

    calls = data.get("calls", [])
    _prefix_ids(calls, prefix, CALL_ID_FIELDS)
    for c in calls:
        c["entry_name"] = entry_name
        c["language"] = entry.language
        c["type"] = entry.type
    unified.calls.extend(calls)
    entry.call_count = len(calls)

    imports = data.get("imports", [])
    for im in imports:
        im["entry_name"] = entry_name
        im["language"] = entry.language
        im["type"] = entry.type
    unified.imports.extend(imports)

    routes = data.get("routes", [])
    for r in routes:
        r["entry_name"] = entry_name
        r["language"] = entry.language
        r["type"] = entry.type
    unified.routes.extend(routes)
    entry.route_count = len(routes)

    all_lists: list[tuple[list[dict[str, Any]] | None, str, set[str]]] = [
        (data.get("env_reads"), "env_reads", ENV_ID_FIELDS),
        (data.get("errors"), "errors", ERROR_ID_FIELDS),
        (data.get("test_edges"), "test_edges", TEST_EDGE_ID_FIELDS),
        (data.get("mutations"), "mutations", MUTATION_ID_FIELDS),
        (data.get("implements"), "implements", IMPLEMENTS_ID_FIELDS),
        (data.get("blueprints"), "blueprints", set()),
        (data.get("blueprint_registrations"), "blueprint_registrations", set()),
        (data.get("template_refs"), "template_refs", set()),
        (data.get("extensions"), "extensions", set()),
        (data.get("dependencies"), "dependencies", set()),
    ]
    for items, field_name, id_fields in all_lists:
        if items:
            _prefix_ids(items, prefix, id_fields)
            for item in items:
                item["entry_name"] = entry_name
                item["language"] = entry.language
                item["type"] = entry.type
            getattr(unified, field_name).extend(items)


def _build_single(entry: WorkspaceEntry, root_path: Path) -> None:
    if entry.language not in BUILT_LANGUAGES:
        entry.build_status = "unsupported"
        return

    _run_tool_build(entry, root_path)


def build_entry(entry: WorkspaceEntry, root_path: Path) -> WorkspaceEntry:
    result = _run_tool_build(entry, root_path)
    return result


def build_all(
    root: str,
    entries: list[WorkspaceEntry] | None = None,
) -> UnifiedGraph:
    root_path = Path(root).resolve()
    config = load_config(root)

    if entries is None:
        entries = resolve_entries(config, root)

    unified = make_unified_graph(workspace_root=str(root_path))

    for entry in entries:
        if entry.language not in BUILT_LANGUAGES:
            entry.build_status = "unsupported"
            if unified.manifest is not None:
                unified.manifest.entries.append(entry)
            continue

        entry = _run_tool_build(entry, root_path)

        if entry.build_status == "ok":
            _stamp_and_collect(entry, root_path, unified)

        if unified.manifest is not None:
            unified.manifest.entries.append(entry)

    return unified


def build_and_write(
    root: str,
    entry_name: str | None = None,
) -> Path:
    root_path = Path(root).resolve()
    config = load_config(root)
    entries = resolve_entries(config, root)

    if entry_name is not None:
        entries = [e for e in entries if e.name == entry_name]

    unified = build_all(root, entries)
    out_dir = root_path / ".codegraph"
    graph_path = out_dir / "workspace.graph.json"
    write_graph(unified, graph_path)

    if unified.manifest is not None:
        manifest_path = out_dir / "manifest.json"
        write_manifest(unified.manifest, manifest_path)

    return graph_path
