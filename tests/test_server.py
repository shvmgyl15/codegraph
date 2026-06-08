from __future__ import annotations

import pytest

from codegraph.graph.types import WorkspaceEntry, make_unified_graph
from codegraph.query import WorkspaceQuery
from codegraph.server import (
    callees,
    callers,
    context,
    entry_status,
    impact,
    orphans,
    query_symbols,
    routes,
    set_query_override,
    trace,
)


def _items(response: dict) -> list:
    return response.get("items", [])


def _make_query() -> WorkspaceQuery:
    graph = make_unified_graph(workspace_root="/test")
    assert graph.manifest is not None

    graph.manifest.entries = [
        WorkspaceEntry(name="frontend", language="typescript", type="frontend",
                       path="./frontend", build_status="ok"),
        WorkspaceEntry(name="api", language="python", type="gateway",
                       path="./api", build_status="ok"),
    ]

    graph.symbols = [
        {"id": "frontend::getUser", "name": "getUser", "kind": "function",
         "file": "frontend/src/api.ts", "line": 5, "is_exported": True,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        {"id": "frontend::helper", "name": "_helper", "kind": "function",
         "file": "frontend/src/utils.ts", "line": 10, "is_exported": False,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        {"id": "api::get_user", "name": "get_user", "kind": "function",
         "file": "api/routes.py", "line": 15, "is_exported": True,
         "entry_name": "api", "language": "python", "type": "gateway"},
        {"id": "api::query_db", "name": "query_db", "kind": "function",
         "file": "api/db.py", "line": 8, "is_exported": False,
         "entry_name": "api", "language": "python", "type": "gateway"},
        {"id": "api::legacy", "name": "_old_helper", "kind": "function",
         "file": "api/legacy.py", "line": 1, "is_exported": False,
         "entry_name": "api", "language": "python", "type": "gateway"},
    ]

    graph.calls = [
        {"caller_symbol_id": "frontend::getUser", "caller_name": "getUser",
         "callee_raw": "_helper", "file": "frontend/src/api.ts", "line": 6,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        {"caller_symbol_id": "api::get_user", "caller_name": "get_user",
         "callee_raw": "query_db", "file": "api/routes.py", "line": 20,
         "entry_name": "api", "language": "python", "type": "gateway"},
    ]

    graph.routes = [
        {"method": "GET", "path": "/api/users", "handler": "get_user",
         "file": "api/routes.py", "line": 14,
         "entry_name": "api", "language": "python", "type": "gateway"},
    ]

    graph.errors = [
        {"message": "ValueError('not found')", "function_name": "query_db",
         "file": "api/db.py", "line": 10,
         "entry_name": "api", "language": "python", "type": "gateway"},
    ]

    return WorkspaceQuery(graph, root="/test")


@pytest.fixture(autouse=True)
def _setup_query() -> WorkspaceQuery:
    q = _make_query()
    set_query_override(q)
    yield q
    set_query_override(None)


class TestEntryStatus:
    def test_returns_entries(self, _setup_query: WorkspaceQuery) -> None:
        result = entry_status()
        assert "entries" in result
        assert "duration_ms" in result
        assert len(result["entries"]) == 2
        names = {e["name"] for e in result["entries"]}
        assert names == {"frontend", "api"}

    def test_entry_fields(self, _setup_query: WorkspaceQuery) -> None:
        result = entry_status()
        api = [e for e in result["entries"] if e["name"] == "api"][0]
        assert api["language"] == "python"
        assert api["type"] == "gateway"
        assert api["build_status"] == "ok"


class TestQuerySymbols:
    def test_pattern_match(self, _setup_query: WorkspaceQuery) -> None:
        result = query_symbols("get")
        assert result["duration_ms"] >= 0
        items = _items(result)
        assert len(items) == 2
        names = {r["name"] for r in items}
        assert names == {"getUser", "get_user"}

    def test_no_match(self, _setup_query: WorkspaceQuery) -> None:
        result = query_symbols("nonexistent")
        assert _items(result) == []


class TestCallers:
    def test_callers_found(self, _setup_query: WorkspaceQuery) -> None:
        result = callers("_helper")
        assert result["duration_ms"] >= 0
        items = _items(result)
        assert len(items) == 1
        assert items[0]["caller"] == "getUser"
        assert items[0]["entry_name"] == "frontend"

    def test_no_callers(self, _setup_query: WorkspaceQuery) -> None:
        result = callers("nonexistent")
        assert _items(result) == []


class TestCallees:
    def test_callees_found(self, _setup_query: WorkspaceQuery) -> None:
        result = callees("get_user", group_by_class=False)
        assert result["duration_ms"] >= 0
        items = _items(result)
        assert len(items) == 1
        assert items[0]["callee"] == "query_db"
        assert items[0]["entry_name"] == "api"

    def test_no_callees(self, _setup_query: WorkspaceQuery) -> None:
        result = callees("_helper", filter_builtins=False, filter_self=False, group_by_class=False)
        assert _items(result) == []


class TestContext:
    def test_context_returns_data(self, _setup_query: WorkspaceQuery) -> None:
        ctx = context("get_user", include_source=False, filter_builtins=False, filter_self=False)
        assert "duration_ms" in ctx
        assert ctx["symbol"] is not None
        assert ctx["symbol"]["name"] == "get_user"
        assert len(ctx["callers"]) == 0
        assert len(ctx["callees"]) == 1


class TestRoutes:
    def test_all_routes(self, _setup_query: WorkspaceQuery) -> None:
        result = routes()
        assert result["duration_ms"] >= 0
        items = _items(result)
        assert len(items) == 1
        assert items[0]["path"] == "/api/users"

    def test_filter_by_entry(self, _setup_query: WorkspaceQuery) -> None:
        result = routes(entry="frontend")
        assert _items(result) == []

    def test_filter_by_type(self, _setup_query: WorkspaceQuery) -> None:
        result = routes(type_filter="frontend")
        assert _items(result) == []


class TestImpact:
    def test_impact_downstream(self, _setup_query: WorkspaceQuery) -> None:
        result = impact("get_user")
        assert result["duration_ms"] >= 0
        items = _items(result)
        assert len(items) == 1
        assert items[0]["callee"] == "query_db"

    def test_impact_no_results(self, _setup_query: WorkspaceQuery) -> None:
        result = impact("nonexistent")
        assert _items(result) == []

    def test_impact_filter_noise(self, _setup_query: WorkspaceQuery) -> None:
        _setup_query._classification.setdefault("symbols", {})["query_db"] = {"kind": "noise"}
        result = impact("get_user", filter_noise=True)
        assert _items(result) == []

    def test_impact_no_filter_noise(self, _setup_query: WorkspaceQuery) -> None:
        _setup_query._classification.setdefault("symbols", {})["query_db"] = {"kind": "noise"}
        result = impact("get_user", filter_noise=False)
        assert len(_items(result)) == 1


class TestOrphans:
    def test_orphans_found(self, _setup_query: WorkspaceQuery) -> None:
        result = orphans(skip_underscore=False)
        assert result["duration_ms"] >= 0
        items = _items(result)
        orphan_names = {r["name"] for r in items}
        assert "_old_helper" in orphan_names
        assert "get_user" not in orphan_names

    def test_orphans_exclude_type(self, _setup_query: WorkspaceQuery) -> None:
        result = orphans(skip_underscore=False, exclude_type="frontend")
        items = _items(result)
        assert all(r["type"] != "frontend" for r in items)

    def test_orphans_include_public(self, _setup_query: WorkspaceQuery) -> None:
        result = orphans(include_public=True, skip_underscore=False)
        items = _items(result)
        assert len(items) >= 1

    def test_orphans_filter_noise(self, _setup_query: WorkspaceQuery) -> None:
        _setup_query._classification.setdefault("symbols", {})["_old_helper"] = {"kind": "noise"}
        result = orphans(skip_underscore=False, filter_noise=True)
        items = _items(result)
        assert "_old_helper" not in {r["name"] for r in items}

    def test_orphans_no_filter_noise(self, _setup_query: WorkspaceQuery) -> None:
        _setup_query._classification.setdefault("symbols", {})["_old_helper"] = {"kind": "noise"}
        result = orphans(skip_underscore=False, filter_noise=False)
        items = _items(result)
        assert "_old_helper" in {r["name"] for r in items}


class TestTrace:
    def test_trace_match(self, _setup_query: WorkspaceQuery) -> None:
        result = trace("not found")
        assert result["duration_ms"] >= 0
        items = _items(result)
        assert len(items) >= 1
        first = items[0]
        fn = first.get("function") or first.get("error", {}).get("function")
        assert fn == "query_db"

    def test_trace_no_match(self, _setup_query: WorkspaceQuery) -> None:
        result = trace("nonexistent error")
        assert _items(result) == []
