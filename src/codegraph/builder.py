from __future__ import annotations

import concurrent.futures
import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any

from codegraph.config import load_config
from codegraph.cross_service import detect_cross_service_edges
from codegraph.discover import BUILT_LANGUAGES, resolve_entries
from codegraph.flow_resolver import (
    check_flow_warnings,
    match_sse_backend_to_frontend,
    resolve_async_flows,
    resolve_dispatch_routes,
)
from codegraph.graph.serialize import write_graph, write_manifest
from codegraph.graph.types import UnifiedGraph, WorkspaceEntry, make_unified_graph
from codegraph.plugin import run_plugins

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

CACHE_FILE_BY_LANGUAGE: dict[str, str] = {
    "python": ".pygraph/.build_cache.json",
    "typescript": ".tsgraph/cache.json",
    "go": ".gograph/cache.json",
}


def _clear_per_language_caches(entries: list[WorkspaceEntry], root_path: Path) -> None:
    for entry in entries:
        lang = entry.language
        cache_rel = CACHE_FILE_BY_LANGUAGE.get(lang)
        if cache_rel:
            cache_path = root_path / entry.path / cache_rel
            if cache_path.exists():
                cache_path.unlink()
        graph_rel = GRAPH_FILE_BY_LANGUAGE.get(lang)
        if graph_rel:
            graph_path = root_path / entry.path / graph_rel
            if graph_path.exists():
                graph_path.unlink()


def _build_cmd(tool: str, entry_path: Path) -> list[str]:
    if tool in ("gograph", "tsgraph"):
        return [tool, "build", str(entry_path)]
    return [tool, "build", "--root", str(entry_path)]


def _run_tool_build(
    entry: WorkspaceEntry, root_path: Path, event_config_json: str | None = None,
) -> WorkspaceEntry:
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
        env = None
        if event_config_json:
            env = os.environ.copy()
            env["CODEGRAPH_EVENT_CONFIG"] = event_config_json
        result = subprocess.run(
            _build_cmd(tool, entry_path),
            capture_output=True, text=True, timeout=120,
            cwd=str(entry_path),
            env=env,
        )
        elapsed = int((time.monotonic() - start) * 1000)
        entry.build_duration_ms = elapsed

        if result.returncode != 0:
            entry.build_status = "failed"
            if result.stderr:
                print(f"  [{entry.name}] stderr:", result.stderr.strip(), flush=True)
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
        (data.get("http_calls"), "http_calls", set()),
    ]
    for items, field_name, id_fields in all_lists:
        if items:
            _prefix_ids(items, prefix, id_fields)
            for item in items:
                item["entry_name"] = entry_name
                item["language"] = entry.language
                item["type"] = entry.type
            getattr(unified, field_name).extend(items)


def _build_single(
    entry: WorkspaceEntry, root_path: Path, event_config_json: str | None = None,
) -> None:
    if entry.language not in BUILT_LANGUAGES:
        entry.build_status = "unsupported"
        return

    _run_tool_build(entry, root_path, event_config_json)


def build_entry(
    entry: WorkspaceEntry, root_path: Path, event_config_json: str | None = None,
) -> WorkspaceEntry:
    result = _run_tool_build(entry, root_path, event_config_json)
    return result


def _build_one(
    entry: WorkspaceEntry, root_path: Path, event_config_json: str | None = None,
) -> WorkspaceEntry:
    if entry.language not in BUILT_LANGUAGES:
        entry.build_status = "unsupported"
        return entry
    start = time.monotonic()
    print(f"  [{entry.name}] building ({entry.language})...", flush=True)
    entry = _run_tool_build(entry, root_path, event_config_json)
    elapsed = time.monotonic() - start
    if entry.build_status == "ok":
        print(f"  [{entry.name}] done ({elapsed:.1f}s)", flush=True)
    elif entry.build_status == "failed":
        print(f"  [{entry.name}] FAILED ({elapsed:.1f}s)", flush=True)
    else:
        print(f"  [{entry.name}] {entry.build_status}", flush=True)
    return entry


def build_all(
    root: str,
    entries: list[WorkspaceEntry] | None = None,
    max_workers: int = 4,
    force: bool = False,
) -> UnifiedGraph:
    root_path = Path(root).resolve()
    config = load_config(root)

    if entries is None:
        entries = resolve_entries(config, root)

    if force:
        _clear_per_language_caches(entries, root_path)

    unified = make_unified_graph(workspace_root=str(root_path))

    buildable = [e for e in entries if e.language in BUILT_LANGUAGES]
    skipped = [e for e in entries if e.language not in BUILT_LANGUAGES]

    for e in skipped:
        e.build_status = "unsupported"
        if unified.manifest is not None:
            unified.manifest.entries.append(e)

    print(f"Building {len(buildable)} entries ({len(skipped)} skipped)...")
    overall_start = time.monotonic()

    event_config_json: str | None = None
    if config.event_boundaries:
        event_config_json = json.dumps(
            [b.model_dump() for b in config.event_boundaries]
        )

    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as pool:
        futures = {
            pool.submit(_build_one, entry, root_path, event_config_json): entry
            for entry in buildable
        }
        for future in concurrent.futures.as_completed(futures):
            entry = futures[future]
            try:
                result = future.result()
            except Exception as exc:
                print(f"  [{entry.name}] ERROR: {exc}", flush=True)
                result = entry
                result.build_status = "failed"

            if result.build_status == "ok":
                _stamp_and_collect(result, root_path, unified)

            if unified.manifest is not None:
                unified.manifest.entries.append(result)

    total_time = time.monotonic() - overall_start
    ok_count = sum(1 for e in buildable if e.build_status == "ok")
    fail_count = sum(1 for e in buildable if e.build_status == "failed")
    print(
        f"Built {ok_count}/{len(buildable)} entries "
        f"({fail_count} failed) in {total_time:.1f}s"
    )

    return unified


def build_and_write(
    root: str,
    entry_name: str | None = None,
    force: bool = False,
) -> Path:
    root_path = Path(root).resolve()
    config = load_config(root)
    entries = resolve_entries(config, root)

    if entry_name is not None:
        entries = [e for e in entries if e.name == entry_name]

    unified = build_all(root, entries, force=force)

    unified.cross_service_edges = detect_cross_service_edges(unified)

    # Async flow correlation pass
    unified.dispatch_routes = resolve_dispatch_routes(unified)
    eb = config.event_boundaries
    event_cfgs = [b.model_dump() for b in eb] if eb else []
    unified.sse_edges = match_sse_backend_to_frontend(unified, event_cfgs)
    flow_cfgs = [f.model_dump() for f in config.flows] if config.flows else []
    unified.flows, flow_warnings = resolve_async_flows(unified, flow_cfgs)
    unified.flow_warnings = check_flow_warnings(unified, unified.flows)
    unified.flow_warnings.extend(flow_warnings)

    run_plugins(unified, root)

    out_dir = root_path / ".codegraph"
    graph_path = out_dir / "workspace.graph.json"
    write_graph(unified, graph_path)

    if unified.manifest is not None:
        manifest_path = out_dir / "manifest.json"
        write_manifest(unified.manifest, manifest_path)

    return graph_path
