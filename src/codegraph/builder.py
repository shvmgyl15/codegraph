from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

from codegraph.config import load_config
from codegraph.discover import BUILT_LANGUAGES, resolve_entries
from codegraph.graph.serialize import write_graph
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

    packages = data.get("packages", [])
    for p in packages:
        p["entry_name"] = entry_name
        p["language"] = entry.language
        p["type"] = entry.type
    unified.packages.extend(packages)
    entry.symbol_count = sum(
        1 for s in data.get("symbols", [])
    )

    files = data.get("files", [])
    for f in files:
        f["entry_name"] = entry_name
        f["language"] = entry.language
        f["type"] = entry.type
    unified.files.extend(files)

    symbols = data.get("symbols", [])
    for s in symbols:
        s["entry_name"] = entry_name
        s["language"] = entry.language
        s["type"] = entry.type
    unified.symbols.extend(symbols)

    calls = data.get("calls", [])
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

    env_reads = data.get("env_reads", [])
    for e in env_reads:
        e["entry_name"] = entry_name
        e["language"] = entry.language
        e["type"] = entry.type
    unified.env_reads.extend(env_reads)

    errors = data.get("errors", [])
    for er in errors:
        er["entry_name"] = entry_name
        er["language"] = entry.language
        er["type"] = entry.type
    unified.errors.extend(errors)

    test_edges = data.get("test_edges", [])
    for te in test_edges:
        te["entry_name"] = entry_name
        te["language"] = entry.language
        te["type"] = entry.type
    unified.test_edges.extend(test_edges)

    mutations = data.get("mutations", [])
    for m in mutations:
        m["entry_name"] = entry_name
        m["language"] = entry.language
        m["type"] = entry.type
    unified.mutations.extend(mutations)

    implements = data.get("implements", [])
    for im in implements:
        im["entry_name"] = entry_name
        im["language"] = entry.language
        im["type"] = entry.type
    unified.implements.extend(implements)

    blueprints = data.get("blueprints", [])
    for b in blueprints:
        b["entry_name"] = entry_name
        b["language"] = entry.language
        b["type"] = entry.type
    unified.blueprints.extend(blueprints)

    blueprint_registrations = data.get("blueprint_registrations", [])
    for br in blueprint_registrations:
        br["entry_name"] = entry_name
        br["language"] = entry.language
        br["type"] = entry.type
    unified.blueprint_registrations.extend(blueprint_registrations)

    template_refs = data.get("template_refs", [])
    for tr in template_refs:
        tr["entry_name"] = entry_name
        tr["language"] = entry.language
        tr["type"] = entry.type
    unified.template_refs.extend(template_refs)

    extensions = data.get("extensions", [])
    for ex in extensions:
        ex["entry_name"] = entry_name
        ex["language"] = entry.language
        ex["type"] = entry.type
    unified.extensions.extend(extensions)

    dependencies = data.get("dependencies", [])
    for de in dependencies:
        de["entry_name"] = entry_name
        de["language"] = entry.language
        de["type"] = entry.type
    unified.dependencies.extend(dependencies)


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
    out_path = out_dir / "workspace.graph.json"
    write_graph(unified, out_path)
    return out_path
