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
        results = query_symbols("get")
        assert len(results) == 2
        names = {r["name"] for r in results}
        assert names == {"getUser", "get_user"}

    def test_no_match(self, _setup_query: WorkspaceQuery) -> None:
        results = query_symbols("nonexistent")
        assert results == []


class TestCallers:
    def test_callers_found(self, _setup_query: WorkspaceQuery) -> None:
        results = callers("_helper")
        assert len(results) == 1
        assert results[0]["caller"] == "getUser"
        assert results[0]["entry_name"] == "frontend"

    def test_no_callers(self, _setup_query: WorkspaceQuery) -> None:
        results = callers("nonexistent")
        assert results == []


class TestCallees:
    def test_callees_found(self, _setup_query: WorkspaceQuery) -> None:
        results = callees("get_user")
        assert len(results) == 1
        assert results[0]["callee"] == "query_db"
        assert results[0]["entry_name"] == "api"

    def test_no_callees(self, _setup_query: WorkspaceQuery) -> None:
        results = callees("_helper")
        assert results == []


class TestContext:
    def test_context_returns_data(self, _setup_query: WorkspaceQuery) -> None:
        ctx = context("get_user", include_source=False)
        assert ctx["symbol"] is not None
        assert ctx["symbol"]["name"] == "get_user"
        assert len(ctx["callers"]) == 0
        assert len(ctx["callees"]) == 1


class TestRoutes:
    def test_all_routes(self, _setup_query: WorkspaceQuery) -> None:
        results = routes()
        assert len(results) == 1
        assert results[0]["path"] == "/api/users"

    def test_filter_by_entry(self, _setup_query: WorkspaceQuery) -> None:
        results = routes(entry="frontend")
        assert results == []

    def test_filter_by_type(self, _setup_query: WorkspaceQuery) -> None:
        results = routes(type_filter="frontend")
        assert results == []


class TestImpact:
    def test_impact_downstream(self, _setup_query: WorkspaceQuery) -> None:
        results = impact("get_user")
        assert len(results) == 1
        assert results[0]["callee"] == "query_db"

    def test_impact_no_results(self, _setup_query: WorkspaceQuery) -> None:
        results = impact("nonexistent")
        assert results == []


class TestOrphans:
    def test_orphans_found(self, _setup_query: WorkspaceQuery) -> None:
        results = orphans()
        orphan_names = {r["name"] for r in results}
        assert "_old_helper" in orphan_names
        assert "get_user" not in orphan_names

    def test_orphans_exclude_type(self, _setup_query: WorkspaceQuery) -> None:
        results = orphans(exclude_type="frontend")
        assert all(r["type"] != "frontend" for r in results)

    def test_orphans_include_public(self, _setup_query: WorkspaceQuery) -> None:
        results = orphans(include_public=True)
        assert len(results) >= 1


class TestTrace:
    def test_trace_match(self, _setup_query: WorkspaceQuery) -> None:
        results = trace("not found")
        assert len(results) >= 1
        first = results[0]
        fn = first.get("function") or first.get("error", {}).get("function")
        assert fn == "query_db"

    def test_trace_no_match(self, _setup_query: WorkspaceQuery) -> None:
        results = trace("nonexistent error")
        assert results == []
