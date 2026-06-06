from __future__ import annotations

import json
import time
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


def set_query_override(query: WorkspaceQuery | None) -> None:
    global _query_override
    _query_override = query


def create_query(root: str) -> WorkspaceQuery:
    if _query_override is not None:
        return _query_override
    root_key = str(Path(root).resolve())
    cached = _query_cache.get(root_key)
    if cached is not None:
        return cached
    graph_path = Path(root_key) / ".codegraph" / "workspace.graph.json"
    if not graph_path.exists():
        raise FileNotFoundError(
            f"Graph not found at {graph_path}. Run `codegraph build` first."
        )
    graph = read_graph(graph_path)
    q = WorkspaceQuery(graph, root=root_key)
    _query_cache[root_key] = q
    return q


def _duration(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


def _box(items: list[Any], start: float) -> dict[str, Any]:
    return {"items": items, "duration_ms": _duration(start)}


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
def query_symbols(pattern: str, root: str = ".") -> dict[str, Any]:
    """Search symbols by pattern (regex or substring) across all entries"""
    _s = time.monotonic()
    q = create_query(root)
    items = [
        {
            "name": s.get("name", ""),
            "kind": s.get("kind", ""),
            "file": s.get("file", ""),
            "line": s.get("line", 0),
            "entry_name": s.get("entry_name", ""),
            "language": s.get("language", ""),
            "type": s.get("type", ""),
            "is_exported": s.get("is_exported", False),
        }
        for s in q.find_symbols(pattern)
    ]
    return _box(items, _s)


@server.tool()
def callers(name: str, root: str = ".") -> dict[str, Any]:
    """Show who calls the given symbol"""
    _s = time.monotonic()
    q = create_query(root)
    items = [
        {
            "caller": cs.get("name", ""),
            "file": ce.get("file", ""),
            "line": ce.get("line", 0),
            "callee_raw": ce.get("callee_raw", ""),
            "entry_name": ce.get("entry_name", ""),
        }
        for cs, ce in q.get_callers(name)
    ]
    return _box(items, _s)


@server.tool()
def callees(name: str, root: str = ".") -> dict[str, Any]:
    """Show what the given symbol calls"""
    _s = time.monotonic()
    q = create_query(root)
    items = [
        {
            "callee": cs.get("name", "") if cs else ce.get("callee_raw", ""),
            "file": ce.get("file", ""),
            "line": ce.get("line", 0),
            "callee_raw": ce.get("callee_raw", ""),
            "entry_name": ce.get("entry_name", ""),
        }
        for cs, ce in q.get_callees(name)
    ]
    return _box(items, _s)


@server.tool()
def context(
    name: str, include_source: bool = False, root: str = "."
) -> dict[str, Any]:
    """Show symbol with callers, callees, and tests"""
    _s = time.monotonic()
    q = create_query(root)
    result = q.get_context(name, include_source=include_source)
    result["duration_ms"] = _duration(_s)
    return result


@server.tool()
def routes(
    entry: str | None = None,
    type_filter: str | None = None,
    root: str = ".",
) -> dict[str, Any]:
    """List HTTP routes across the workspace, optionally filtered"""
    _s = time.monotonic()
    q = create_query(root)
    results = list(q.graph.routes)
    if entry:
        results = [r for r in results if r.get("entry_name") == entry]
    if type_filter:
        results = [r for r in results if r.get("type") == type_filter]
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
    name: str, max_depth: int | None = None, root: str = "."
) -> dict[str, Any]:
    """Show downstream impact (BFS from symbol)"""
    _s = time.monotonic()
    q = create_query(root)
    items = q.get_impact(name, max_depth=max_depth)
    return _box(items, _s)


@server.tool()
def orphans(
    include_public: bool = False,
    exclude_type: str | None = None,
    root: str = ".",
) -> dict[str, Any]:
    """List unreachable symbols (dead code)"""
    _s = time.monotonic()
    q = create_query(root)
    results = q.get_orphans(include_public=include_public)
    if exclude_type:
        results = [o for o in results if o.get("type") != exclude_type]
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
        for o in results
    ]
    return _box(items, _s)


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


def run_server(root: str = ".") -> None:
    server.run(transport="stdio")
