from __future__ import annotations

import pytest

from codegraph.graph.types import UnifiedGraph, WorkspaceEntry, make_unified_graph
from codegraph.query import WorkspaceQuery


def _make_graph() -> UnifiedGraph:
    graph = make_unified_graph(workspace_root="/fake")
    assert graph.manifest is not None

    graph.manifest.entries = [
        WorkspaceEntry(name="svc-a", language="go", type="service",
                       path="./svc-a", build_status="ok"),
        WorkspaceEntry(name="svc-b", language="python", type="service",
                       path="./svc-b", build_status="ok"),
    ]

    graph.symbols = [
        {"id": "svc-a::handler1", "name": "Handler1", "kind": "function",
         "file": "svc-a/main.go", "line": 10, "is_exported": True,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"id": "svc-a::helper1", "name": "Helper1", "kind": "function",
         "file": "svc-a/helper.go", "line": 5, "is_exported": False,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"id": "svc-a::helper2", "name": "Helper2", "kind": "function",
         "file": "svc-a/helper.go", "line": 20, "is_exported": False,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"id": "svc-a::legacy", "name": "LegacyFunc", "kind": "function",
         "file": "svc-a/legacy.go", "line": 1, "is_exported": False,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"id": "svc-b::unused_helper", "name": "_unused", "kind": "function",
         "file": "svc-b/old.py", "line": 50, "is_exported": False,
         "entry_name": "svc-b", "language": "python", "type": "service"},
        {"id": "svc-b::apiuser_get", "name": "get_user", "kind": "function",
         "file": "svc-b/routes.py", "line": 15, "is_exported": True,
         "entry_name": "svc-b", "language": "python", "type": "service"},
        {"id": "svc-b::db_query", "name": "query_db", "kind": "function",
         "file": "svc-b/db.py", "line": 8, "is_exported": False,
         "entry_name": "svc-b", "language": "python", "type": "service"},
    ]

    graph.calls = [
        {"caller_symbol_id": "svc-a::handler1", "caller_name": "Handler1",
         "callee_raw": "Helper1", "file": "svc-a/main.go", "line": 12,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"caller_symbol_id": "svc-a::helper1", "caller_name": "Helper1",
         "callee_raw": "Helper2", "file": "svc-a/helper.go", "line": 7,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"caller_symbol_id": "svc-b::apiuser_get", "caller_name": "get_user",
         "callee_raw": "query_db", "file": "svc-b/routes.py", "line": 20,
         "entry_name": "svc-b", "language": "python", "type": "service"},
    ]

    graph.routes = [
        {"method": "GET", "path": "/api/users", "handler": "Handler1",
         "file": "svc-a/main.go", "line": 9,
         "entry_name": "svc-a", "language": "go", "type": "service"},
        {"method": "GET", "path": "/api/users", "handler": "get_user",
         "file": "svc-b/routes.py", "line": 14,
         "entry_name": "svc-b", "language": "python", "type": "service"},
    ]

    graph.errors = [
        {"message": "ValueError('not found')", "function_name": "query_db",
         "file": "svc-b/db.py", "line": 10,
         "entry_name": "svc-b", "language": "python", "type": "service"},
    ]

    graph.test_edges = [
        {"test_func": "test_handler1", "target": "Handler1",
         "file": "svc-a/main_test.go", "line": 1,
         "entry_name": "svc-a", "language": "go", "type": "service"},
    ]

    graph.env_reads = [
        {"key": "DATABASE_URL", "accessor": "os.getenv",
         "file": "svc-b/db.py", "line": 1,
         "entry_name": "svc-b", "language": "python", "type": "service"},
    ]

    return graph


@pytest.fixture
def query() -> WorkspaceQuery:
    graph = _make_graph()
    return WorkspaceQuery(graph, root="/fake")


class TestFindSymbols:
    def test_pattern_match(self, query: WorkspaceQuery) -> None:
        result = query.find_symbols("Handler")
        items = result["items"]
        assert len(items) >= 1
        names = {r["name"] for r in items}
        assert "Handler1" in names

    def test_substring_match(self, query: WorkspaceQuery) -> None:
        result = query.find_symbols("Helper")
        assert result["total"] == 2

    def test_no_match(self, query: WorkspaceQuery) -> None:
        result = query.find_symbols("NonExistent")
        assert result["items"] == []
        assert result["total"] == 0

    def test_cross_entry(self, query: WorkspaceQuery) -> None:
        result = query.find_symbols("get_user")
        assert result["total"] == 1
        assert result["items"][0]["entry_name"] == "svc-b"


class TestGetSymbol:
    def test_get_existing(self, query: WorkspaceQuery) -> None:
        sym = query.get_symbol("Handler1")
        assert sym is not None
        assert sym["name"] == "Handler1"
        assert sym["entry_name"] == "svc-a"

    def test_get_nonexistent(self, query: WorkspaceQuery) -> None:
        sym = query.get_symbol("NonExistent")
        assert sym is None

    def test_get_first_of_duplicates(self, query: WorkspaceQuery) -> None:
        sym = query.get_symbol("Helper1")
        assert sym is not None
        assert sym["name"] == "Helper1"


class TestGetCallers:
    def test_callers_exist(self, query: WorkspaceQuery) -> None:
        result = query.get_callers("Helper1")
        assert result["total"] == 1
        assert result["items"][0]["caller"] == "Handler1"

    def test_callers_chain(self, query: WorkspaceQuery) -> None:
        result = query.get_callers("Helper2")
        assert result["total"] == 1
        assert result["items"][0]["caller"] == "Helper1"

    def test_callers_nonexistent(self, query: WorkspaceQuery) -> None:
        result = query.get_callers("NonExistent")
        assert result["items"] == []
        assert result["total"] == 0


class TestGetCallees:
    def test_callees_exist(self, query: WorkspaceQuery) -> None:
        result = query.get_callees("Handler1")
        assert result["total"] == 1
        assert result["items"][0]["callee"] == "Helper1"

    def test_callees_chain(self, query: WorkspaceQuery) -> None:
        result = query.get_callees("Helper1")
        assert result["total"] == 1
        assert result["items"][0]["callee"] == "Helper2"

    def test_callees_leaf(self, query: WorkspaceQuery) -> None:
        result = query.get_callees("Helper2")
        assert result["items"] == []
        assert result["total"] == 0


class TestGetRoutes:
    def test_all_routes(self, query: WorkspaceQuery) -> None:
        routes = query.get_routes()
        assert len(routes) == 2

    def test_route_entries(self, query: WorkspaceQuery) -> None:
        routes = query.get_routes()
        entries = {r["entry_name"] for r in routes}
        assert entries == {"svc-a", "svc-b"}


class TestGetImpact:
    def test_impact_downstream(self, query: WorkspaceQuery) -> None:
        results = query.get_impact("Handler1")
        assert len(results) == 2  # Handler1 → Helper1, Helper1 → Helper2
        callees = {r["callee"] for r in results}
        assert callees == {"Helper1", "Helper2"}

    def test_impact_with_max_depth(self, query: WorkspaceQuery) -> None:
        results = query.get_impact("Handler1", max_depth=1)
        assert len(results) == 1
        assert results[0]["callee"] == "Helper1"

    def test_impact_leaf(self, query: WorkspaceQuery) -> None:
        results = query.get_impact("Helper2")
        assert results == []


class TestGetOrphans:
    def test_orphans_private_only(self, query: WorkspaceQuery) -> None:
        orphans = query.get_orphans(include_public=False)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" in orphan_names
        assert "_unused" in orphan_names
        assert "Handler1" not in orphan_names  # exported
        assert "get_user" not in orphan_names  # exported
        assert "Helper2" not in orphan_names  # reachable via Handler1→Helper1→Helper2

    def test_orphans_include_public(self, query: WorkspaceQuery) -> None:
        orphans = query.get_orphans(include_public=True)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" in orphan_names
        assert "_unused" in orphan_names


class TestGetContext:
    def test_context_basic(self, query: WorkspaceQuery) -> None:
        ctx = query.get_context("Handler1", include_source=False)
        assert ctx["symbol"] is not None
        assert ctx["symbol"]["name"] == "Handler1"
        assert len(ctx["callers"]) == 0  # top-level, no callers
        assert len(ctx["callees"]) == 1
        assert len(ctx["tests"]) == 1

    def test_context_includes_tests(self, query: WorkspaceQuery) -> None:
        ctx = query.get_context("Handler1", include_source=False)
        assert len(ctx["tests"]) == 1
        assert ctx["tests"][0]["test_func"] == "test_handler1"

    def test_context_source_not_loaded_when_disabled(self, query: WorkspaceQuery) -> None:
        ctx = query.get_context("Handler1", include_source=False)
        assert ctx["source"] is None


class TestGetTrace:
    def test_trace_match(self, query: WorkspaceQuery) -> None:
        results = query.get_trace("not found")
        assert len(results) == 1
        assert results[0]["function"] == "query_db"
        assert results[0]["entry_name"] == "svc-b"

    def test_trace_no_match(self, query: WorkspaceQuery) -> None:
        results = query.get_trace("nonexistent error")
        assert results == []


class TestGetErrorflow:
    def test_errorflow_match(self, query: WorkspaceQuery) -> None:
        results = query.get_errorflow("not found")
        assert len(results) == 1
        assert results[0]["error"]["function_name"] == "query_db"

    def test_errorflow_no_match(self, query: WorkspaceQuery) -> None:
        results = query.get_errorflow("nonexistent")
        assert results == []
