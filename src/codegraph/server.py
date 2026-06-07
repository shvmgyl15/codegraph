from __future__ import annotations

import json
import time
from contextlib import suppress
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP

from codegraph.graph.serialize import read_graph
from codegraph.query import WorkspaceQuery

server = FastMCP(
    "codegraph",
    instructions="Query a multi-language workspace using codegraph's unified graph.",
)

_query_override: WorkspaceQuery | None = None
_query_cache: dict[str, WorkspaceQuery] = {}
_last_load_ms: float = 0.0


def set_query_override(query: WorkspaceQuery | None) -> None:
    global _query_override
    _query_override = query


def create_query(root: str) -> WorkspaceQuery:
    global _last_load_ms
    if _query_override is not None:
        return _query_override
    root_key = str(Path(root).resolve())
    cached = _query_cache.get(root_key)
    if cached is not None:
        _last_load_ms = 0
        return cached
    load_start = time.monotonic()
    graph_path = Path(root_key) / ".codegraph" / "workspace.graph.json"
    if not graph_path.exists():
        raise FileNotFoundError(
            f"Graph not found at {graph_path}. Run `codegraph build` first."
        )
    graph = read_graph(graph_path)
    q = WorkspaceQuery(graph, root=root_key)
    _query_cache[root_key] = q
    _last_load_ms = int((time.monotonic() - load_start) * 1000)
    return q


def _duration(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _box(items: list[Any], start: float) -> dict[str, Any]:
    return {
        "items": items,
        "duration_ms": _duration(start),
        "load_ms": int(_last_load_ms),
        "query_ms": _duration(start) - int(_last_load_ms),
    }


def _truncate(items: list[Any], max_results: int | None) -> tuple[list[Any], bool]:
    if max_results is not None and len(items) > max_results:
        return items[:max_results], True
    return items, False


@server.tool()
def entry_status(root: str = ".") -> dict[str, Any]:
    """List workspace entries with language, type, and build status"""
    _s = time.monotonic()
    q = create_query(root)
    if q.graph.manifest is None:
        return {"entries": [], "duration_ms": _duration(_s)}
    return {
        "entries": [
            {
                "name": e.name,
                "language": e.language,
                "type": e.type,
                "path": e.path,
                "build_status": e.build_status,
                "symbol_count": e.symbol_count,
                "call_count": e.call_count,
                "route_count": e.route_count,
            }
            for e in q.graph.manifest.entries
        ],
        "duration_ms": _duration(_s),
    }


@server.tool()
def query_symbols(
    pattern: str,
    kind: str | None = None,
    entry_kind: str | None = None,
    min_calls: int | None = None,
    max_calls: int | None = None,
    max_results: int = 50,
    root: str = ".",
) -> dict[str, Any]:
    """Search symbols by pattern (regex or substring) across all entries.
    Filters: kind (e.g. 'utility', '!utility'), entry_kind (e.g. 'library', '!library'),
    min_calls (exclude if fan-in >= N), max_calls (exclude if fan-in <= N)."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.find_symbols(
        pattern, kind=kind, entry_kind=entry_kind,
        min_calls=min_calls, max_calls=max_calls,
        max_results=max_results,
    )
    return {
        "items": result["items"],
        "total": result["total"],
        "truncated": result["truncated"],
        "duration_ms": _duration(_s),
        "load_ms": int(_last_load_ms),
        "query_ms": _duration(_s) - int(_last_load_ms),
    }


def _summary_box(items: list[dict[str, Any]], start: float, group_key: str) -> dict[str, Any]:
    groups: dict[str, dict[str, Any]] = {}
    for item in items:
        key = item.get(group_key, "")
        entry = item.get("entry_name", "")
        composite = f"{entry}::{key}"
        if composite not in groups:
            groups[composite] = {
                group_key: key,
                "entry_name": entry,
                "call_count": 0,
                "unique_files": set(),
                "unique_callers": set(),
            }
        groups[composite]["call_count"] += 1
        groups[composite]["unique_files"].add(item.get("file", ""))
        caller = item.get("caller") or item.get("callee")
        if caller:
            groups[composite]["unique_callers"].add(caller)

    result = []
    for g in groups.values():
        g["unique_files"] = len(g["unique_files"])
        g["unique_callers"] = len(g["unique_callers"])
        result.append(g)
    result.sort(key=lambda x: -x["call_count"])
    return {
        "items": result,
        "total": len(groups),
        "duration_ms": _duration(start),
        "load_ms": int(_last_load_ms),
        "query_ms": _duration(start) - int(_last_load_ms),
    }


@server.tool()
def callers(
    name: str,
    summary: bool = True,
    kind: str | None = None,
    entry_kind: str | None = None,
    min_calls: int | None = None,
    max_calls: int | None = None,
    max_results: int = 50,
    root: str = ".",
) -> dict[str, Any]:
    """Show who calls the given symbol.
    summary=True groups by caller name; summary=False returns raw edges.
    Filters: kind (e.g. '!utility'), entry_kind, min_calls, max_calls."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.get_callers(
        name, kind=kind, entry_kind=entry_kind,
        min_calls=min_calls, max_calls=max_calls,
        max_results=None,  # raw first, then truncate
    )
    items = result["items"]
    raw_total = result["total"]
    items, truncated = _truncate(items, max_results)
    if summary and items:
        return _summary_box(items, _s, "caller")
    return {
        "items": items,
        "total": raw_total,
        "truncated": truncated,
        "duration_ms": _duration(_s),
        "load_ms": int(_last_load_ms),
        "query_ms": _duration(_s) - int(_last_load_ms),
    }


@server.tool()
def callees(
    name: str,
    summary: bool = True,
    filter_builtins: bool = True,
    filter_self: bool = True,
    filter_dict_accessors: bool = True,
    filter_constructors: bool = True,
    group_by_class: bool = True,
    kind: str | None = None,
    entry_kind: str | None = None,
    min_calls: int | None = None,
    max_calls: int | None = None,
    max_results: int = 50,
    root: str = ".",
) -> dict[str, Any]:
    """Show what the given symbol calls.
    summary=True groups by callee name; summary=False returns raw edges.
    filter_builtins=True hides Python builtins (str, len, print, etc.).
    filter_self=True hides calls to own class methods (self.*).
    filter_dict_accessors=True hides .get(), .items(), etc. (dict accessors).
    filter_constructors=True hides __init__, __new__ calls.
    group_by_class=True groups callees by class name.
    Filters: kind (e.g. '!utility'), entry_kind, min_calls, max_calls."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.get_callees(
        name, kind=kind, entry_kind=entry_kind,
        min_calls=min_calls, max_calls=max_calls,
        max_results=None,
        filter_builtins=filter_builtins,
        filter_self=filter_self,
        filter_dict_accessors=filter_dict_accessors,
        filter_constructors=filter_constructors,
        group_by_class=group_by_class,
    )
    items = result["items"]
    raw_total = result["total"]
    if group_by_class:
        result["duration_ms"] = _duration(_s)
        result["load_ms"] = int(_last_load_ms)
        result["query_ms"] = _duration(_s) - int(_last_load_ms)
        return result
    items, truncated = _truncate(items, max_results)
    if summary and items:
        return _summary_box(items, _s, "callee")
    return {
        "items": items,
        "total": raw_total,
        "truncated": truncated,
        "duration_ms": _duration(_s),
        "load_ms": int(_last_load_ms),
        "query_ms": _duration(_s) - int(_last_load_ms),
    }


@server.tool()
def context(
    name: str,
    include_source: bool = False,
    filter_builtins: bool = True,
    filter_self: bool = True,
    kind: str | None = None,
    entry_kind: str | None = None,
    min_calls: int | None = None,
    max_calls: int | None = None,
    max_results: int = 50,
    root: str = ".",
) -> dict[str, Any]:
    """Show symbol with callers, callees, and tests.
    Filters: kind (e.g. '!utility'), entry_kind, min_calls, max_calls."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.get_context(
        name, include_source=include_source,
        kind=kind, entry_kind=entry_kind,
        min_calls=min_calls, max_calls=max_calls,
        max_results=max_results,
        filter_builtins=filter_builtins,
        filter_self=filter_self,
    )
    result["duration_ms"] = _duration(_s)
    result["load_ms"] = int(_last_load_ms)
    result["query_ms"] = _duration(_s) - int(_last_load_ms)
    return result


@server.tool()
def routes(
    entry: str | None = None,
    type_filter: str | None = None,
    include_route_wrappers: bool = True,
    root: str = ".",
) -> dict[str, Any]:
    """List HTTP routes across the workspace, optionally filtered.
    include_route_wrappers=True also detects calls to route_wrapper-classified symbols
    as synthetic route entries (mark via classify_symbol(kind='route_wrapper'))."""
    _s = time.monotonic()
    q = create_query(root)
    results = list(q.graph.routes)
    if entry:
        results = [r for r in results if r.get("entry_name") == entry]
    if type_filter:
        results = [r for r in results if r.get("type") == type_filter]

    if include_route_wrappers:
        wrapper_names = list(q.list_classifications(kind="route_wrapper").get("symbols", {}).keys())
        route_patterns = q._classification.get("route_patterns", {})
        seen_calls: set[tuple[str, str, int]] = set()

        for call in q.graph.calls:
            craw = call.get("callee_raw", "")
            matching_wrappers = [w for w in wrapper_names if w in craw]
            if not matching_wrappers:
                continue

            cid = call.get("caller_symbol_id", "")
            lineno = call.get("line", 0)
            k = (cid, craw, lineno)
            if k in seen_calls:
                continue
            seen_calls.add(k)

            caller_sym = q._symbols_by_id.get(cid)
            caller_name = caller_sym.get("name", "") if caller_sym else "<module>"

            wrapper_name = matching_wrappers[0]
            config = route_patterns.get(wrapper_name, {})
            class_idx = config.get("class_arg_index")

            if config:
                raw_args = q._extract_call_args(
                    call.get("file", ""), lineno, craw,
                )
                path_args = raw_args.get("args", [])
                if class_idx is not None and class_idx < len(path_args):
                    paths = [a for i, a in enumerate(path_args) if i != class_idx]
                else:
                    paths = path_args
                if not paths:
                    paths = [f"[{craw}]"]

                http_methods = ["GET"]
                cls_name = ""
                if class_idx is not None and class_idx < len(path_args):
                    cls_name = path_args[class_idx]
                    cls_methods = q._methods_by_class.get(cls_name, [])
                    if cls_methods:
                        http_methods = []
                        for m in cls_methods:
                            mname = m.get("name", "").lower()
                            method_map = {
                                "get": "GET", "post": "POST", "put": "PUT",
                                "delete": "DELETE", "patch": "PATCH",
                                "head": "HEAD", "options": "OPTIONS",
                            }
                            mapped = method_map.get(mname)
                            if mapped:
                                http_methods.append(mapped)
                        if not http_methods:
                            http_methods = ["GET"]

                for path in paths:
                    for method in http_methods:
                        results.append({
                            "method": method,
                            "path": path,
                            "handler": cls_name if cls_name else caller_name,
                            "file": call.get("file", ""),
                            "line": lineno,
                            "entry_name": call.get("entry_name", ""),
                            "language": call.get("language", ""),
                            "type": call.get("type", ""),
                            "detected_by": "route_pattern",
                        })
            else:
                results.append({
                    "method": "WRAPPER",
                    "path": f"[{craw}]",
                    "handler": caller_name,
                    "file": call.get("file", ""),
                    "line": lineno,
                    "entry_name": call.get("entry_name", ""),
                    "language": call.get("language", ""),
                    "type": call.get("type", ""),
                    "detected_by": "route_classification",
                })

    items = [
        {
            "method": r.get("method", ""),
            "path": r.get("path", ""),
            "handler": r.get("handler", ""),
            "file": r.get("file", ""),
            "line": r.get("line", 0),
            "entry_name": r.get("entry_name", ""),
            "language": r.get("language", ""),
            "type": r.get("type", ""),
        }
        for r in results
    ]
    return _box(items, _s)


@server.tool()
def impact(
    name: str,
    max_depth: int | None = None,
    max_results: int = 100,
    root: str = ".",
) -> dict[str, Any]:
    """Show downstream impact (BFS from symbol)"""
    _s = time.monotonic()
    q = create_query(root)
    items = q.get_impact(name, max_depth=max_depth)
    items, truncated = _truncate(items, max_results)
    result = _box(items, _s)
    result["truncated"] = truncated
    return result


@server.tool()
def orphans(
    include_public: bool = False,
    skip_underscore: bool = True,
    exclude_type: str | None = None,
    kind: str | None = None,
    entry_kind: str | None = None,
    max_results: int = 100,
    root: str = ".",
) -> dict[str, Any]:
    """List unreachable symbols (dead code).
    skip_underscore=True filters private _methods (likely false positives).
    Filters: kind (e.g. '!utility'), entry_kind."""
    _s = time.monotonic()
    q = create_query(root)
    results = q.get_orphans(include_public=include_public, skip_underscore=skip_underscore)
    filtered = []
    for o in results:
        if exclude_type and o.get("type") == exclude_type:
            continue
        if kind:
            sym_class = q._sym_classification(o.get("name", ""))
            if kind.startswith("!"):
                if sym_class == kind[1:]:
                    continue
            elif sym_class != kind:
                continue
        if entry_kind:
            entry_class = q._entry_classification(o.get("entry_name", ""))
            if entry_kind.startswith("!"):
                if entry_class == entry_kind[1:]:
                    continue
            elif entry_class != entry_kind:
                continue
        filtered.append(o)
    items = [
        {
            "name": o.get("name", ""),
            "kind": o.get("kind", ""),
            "file": o.get("file", ""),
            "line": o.get("line", 0),
            "entry_name": o.get("entry_name", ""),
            "language": o.get("language", ""),
            "type": o.get("type", ""),
        }
        for o in filtered
    ]
    items, truncated = _truncate(items, max_results)
    result = _box(items, _s)
    result["truncated"] = truncated
    return result


@server.tool()
def trace(message: str, root: str = ".") -> dict[str, Any]:
    """Find error messages matching the given text"""
    _s = time.monotonic()
    q = create_query(root)
    results = q.get_errorflow(message)
    if not results:
        plain = q.get_trace(message)
        items = [
            {
                "message": r["message"],
                "function": r["function"],
                "file": r["file"],
                "line": r["line"],
                "entry_name": r["entry_name"],
            }
            for r in plain
        ]
        return _box(items, _s)
    items = [
        {
            "error": {
                "message": item["error"].get("message", ""),
                "function": item["error"].get("function_name", ""),
                "file": item["error"].get("file", ""),
                "line": item["error"].get("line", 0),
                "entry_name": item["error"].get("entry_name", ""),
            },
            "trace": item["trace"],
        }
        for item in results
    ]
    return _box(items, _s)


@server.tool()
def cross_service_calls(
    source_entry: str | None = None,
    target_entry: str | None = None,
    root: str = ".",
) -> dict[str, Any]:
    """List cross-service HTTP call edges between entries"""
    _s = time.monotonic()
    q = create_query(root)
    items = q.get_cross_service_edges(
        source_entry=source_entry, target_entry=target_entry,
    )
    return _box(items, _s)


@server.tool()
def add_opencode_plugin(root: str = ".") -> dict[str, Any]:
    """Create .opencode.json with codegraph MCP config + architect agent"""
    _s = time.monotonic()
    root_path = Path(root).resolve()
    config_path = root_path / ".opencode.json"

    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp_servers": {
            "codegraph": {
                "command": "uv",
                "args": ["run", "codegraph", "mcp", "--root", str(root_path)],
                "env": {},
            },
        },
        "agents": {
            "architect": {
                "model": "opencode-go/deepseek-v4-flash",
                "instructions": [
                    "Use codegraph MCP tools to query the workspace code graph.",
                    "Search symbols, find callers/callees, list routes, "
                    "detect dead code, trace errors, and discover "
                    "cross-service HTTP call edges.",
                ],
            },
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    return {"message": f"Created {config_path}", "duration_ms": _duration(_s)}


@server.tool()
def classify_symbol(
    names: list[str],
    kind: str = "utility",
    root: str = ".",
) -> dict[str, Any]:
    """Tag symbols by kind (utility, business_logic, infrastructure, etc.)
    Classified symbols are filtered out by '!utility' in query tools."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.classify_symbol(names, kind)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def classify_entry(
    names: list[str],
    kind: str = "library",
    root: str = ".",
) -> dict[str, Any]:
    """Tag entire entries by kind (library, infrastructure, business_logic, etc.)
    Classified entries are filtered out by '!library' in query tools."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.classify_entry(names, kind)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def unclassify_symbol(
    names: list[str],
    root: str = ".",
) -> dict[str, Any]:
    """Remove classification tags from symbols."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.unclassify_symbol(names)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def unclassify_entry(
    names: list[str],
    root: str = ".",
) -> dict[str, Any]:
    """Remove classification tags from entries."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.unclassify_entry(names)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def list_classifications(
    kind: str | None = None,
    root: str = ".",
) -> dict[str, Any]:
    """View all classified symbols and entries, optionally filtered by kind."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.list_classifications(kind=kind)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def classify_discover(
    min_calls: int = 10,
    root: str = ".",
) -> dict[str, Any]:
    """Auto-detect candidate utility symbols by fan-in (unique caller count).
    Returns symbols called from >= min_calls unique entries that aren't classified yet.
    Review candidates with list_classifications() and commit with classify_symbol()."""
    _s = time.monotonic()
    q = create_query(root)
    result = q.classify_discover(min_calls=min_calls)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def define_route_pattern(
    name: str,
    path_arg_index: int = 0,
    class_arg_index: int | None = None,
    root: str = ".",
) -> dict[str, Any]:
    """Define a custom route wrapper pattern for synthetic route detection.
    name: function name (e.g. 'register_path', 'add_resource')
    path_arg_index: which positional arg contains the route path (0-based)
    class_arg_index: which positional arg contains the handler class (optional)

    After defining a pattern, use classify_symbol(kind='route_wrapper') to
    activate detection, then routes(include_route_wrappers=True) shows results.
    Stored in .codegraph/classification.json — persists across sessions.
    """
    _s = time.monotonic()
    q = create_query(root)
    data = q._classification
    patterns = data.setdefault("route_patterns", {})
    patterns[name] = {
        "path_arg_index": path_arg_index,
        "class_arg_index": class_arg_index,
    }
    from codegraph.query import _save_classifications
    _save_classifications(root, data)
    q._classification["route_patterns"] = patterns
    return {
        "defined": name,
        "path_arg_index": path_arg_index,
        "class_arg_index": class_arg_index,
        "duration_ms": _duration(_s),
    }


def run_server(root: str = ".") -> None:
    with suppress(FileNotFoundError):
        create_query(root)
    server.run(transport="stdio")
