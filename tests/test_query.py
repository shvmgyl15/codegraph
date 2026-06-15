from __future__ import annotations

from pathlib import Path

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
    def _callees(self, q, name, **kw):
        return q.get_callees(name, group_by_class=False,
                             filter_builtins=False, filter_self=False, **kw)

    def test_callees_exist(self, query: WorkspaceQuery) -> None:
        result = self._callees(query, "Handler1")
        assert result["total"] == 1
        assert result["items"][0]["callee"] == "Helper1"

    def test_callees_chain(self, query: WorkspaceQuery) -> None:
        result = self._callees(query, "Helper1")
        assert result["total"] == 1
        assert result["items"][0]["callee"] == "Helper2"

    def test_callees_leaf(self, query: WorkspaceQuery) -> None:
        result = self._callees(query, "Helper2")
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

    def test_impact_filter_noise_skips_noise(self, query: WorkspaceQuery) -> None:
        query._classification.setdefault("symbols", {})["Helper1"] = {"kind": "noise"}
        results = query.get_impact("Handler1", filter_noise=True)
        assert len(results) == 0  # Helper1 (noise) skipped, blocking Helper2

    def test_impact_filter_noise_skips_utility(self, query: WorkspaceQuery) -> None:
        query._classification.setdefault("symbols", {})["Helper1"] = {"kind": "utility"}
        results = query.get_impact("Handler1", filter_noise=True)
        assert len(results) == 0  # Helper1 (utility) skipped, blocking Helper2

    def test_impact_filter_noise_disabled(self, query: WorkspaceQuery) -> None:
        query._classification.setdefault("symbols", {})["Helper1"] = {"kind": "noise"}
        results = query.get_impact("Handler1", filter_noise=False)
        assert len(results) == 2  # Helper1 included even though noise


class TestGetOrphans:
    def test_orphans_private_only(self, query: WorkspaceQuery) -> None:
        orphans = query.get_orphans(include_public=False, skip_underscore=False)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" in orphan_names
        assert "_unused" in orphan_names
        assert "Handler1" not in orphan_names  # exported
        assert "get_user" not in orphan_names  # exported
        assert "Helper2" not in orphan_names  # reachable via Handler1→Helper1→Helper2

    def test_orphans_include_public(self, query: WorkspaceQuery) -> None:
        orphans = query.get_orphans(include_public=True, skip_underscore=False)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" in orphan_names
        assert "_unused" in orphan_names

    def test_orphans_filter_noise_skips_noise(self, query: WorkspaceQuery) -> None:
        query._classification.setdefault("symbols", {})["LegacyFunc"] = {"kind": "noise"}
        orphans = query.get_orphans(include_public=False, skip_underscore=False, filter_noise=True)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" not in orphan_names
        assert "_unused" in orphan_names

    def test_orphans_filter_noise_skips_utility(self, query: WorkspaceQuery) -> None:
        query._classification.setdefault("symbols", {})["LegacyFunc"] = {"kind": "utility"}
        orphans = query.get_orphans(include_public=False, skip_underscore=False, filter_noise=True)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" not in orphan_names
        assert "_unused" in orphan_names

    def test_orphans_filter_noise_disabled(self, query: WorkspaceQuery) -> None:
        query._classification.setdefault("symbols", {})["LegacyFunc"] = {"kind": "noise"}
        orphans = query.get_orphans(include_public=False, skip_underscore=False, filter_noise=False)
        orphan_names = {o["name"] for o in orphans}
        assert "LegacyFunc" in orphan_names
        assert "_unused" in orphan_names


class TestGetContext:
    def _context(self, query, **kw):
        return query.get_context("Handler1", include_source=False,
                                 filter_builtins=False, filter_self=False, **kw)

    def test_context_basic(self, query: WorkspaceQuery) -> None:
        ctx = self._context(query)
        assert ctx["symbol"] is not None
        assert ctx["symbol"]["name"] == "Handler1"
        assert len(ctx["callers"]) == 0
        assert len(ctx["callees"]) == 1
        assert len(ctx["tests"]) == 1

    def test_context_includes_tests(self, query: WorkspaceQuery) -> None:
        ctx = self._context(query)
        assert len(ctx["tests"]) == 1
        assert ctx["tests"][0]["test_func"] == "test_handler1"

    def test_context_source_not_loaded_when_disabled(self, query: WorkspaceQuery) -> None:
        ctx = self._context(query)
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


def test_load_source_snippet(temp_workspace: Path) -> None:
    from codegraph.query import _load_classifications, _save_classifications

    # Check that classification loads/saves to codegraph.d/
    data = {"symbols": {"test": {"kind": "noise"}}}
    _save_classifications(str(temp_workspace), data)
    assert (temp_workspace / "codegraph.d" / "classification.json").exists()
    loaded = _load_classifications(str(temp_workspace))
    assert loaded["symbols"]["test"]["kind"] == "noise"


def _make_ts_graph() -> UnifiedGraph:
    """Simulate a frontend workspace with TypeScript-style call edges."""
    graph = make_unified_graph(workspace_root="/fake")
    assert graph.manifest is not None

    graph.manifest.entries = [
        WorkspaceEntry(name="frontend", language="typescript", type="frontend",
                       path="./frontend", build_status="ok"),
        WorkspaceEntry(name="ui-lib", language="typescript", type="library",
                       path="./ui-lib", build_status="ok"),
    ]

    # Frontend entry symbols
    graph.symbols = [
        # Page component
        {"id": "frontend::src/pages/dashboard.tsx::DashboardPage", "name": "DashboardPage",
         "kind": "function", "file": "src/pages/dashboard.tsx", "line": 10,
         "is_exported": True, "isClientComponent": True,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # A data-fetching function
        {"id": "frontend::src/api/users.ts::fetchUsers", "name": "fetchUsers",
         "kind": "function", "file": "src/api/users.ts", "line": 5,
         "is_exported": True,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # A utility function
        {"id": "frontend::src/lib/format.ts::formatDate", "name": "formatDate",
         "kind": "function", "file": "src/lib/format.ts", "line": 1,
         "is_exported": True,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # A custom hook
        {"id": "frontend::src/hooks/useAuth.ts::useAuth", "name": "useAuth",
         "kind": "function", "file": "src/hooks/useAuth.ts", "line": 3,
         "is_exported": True,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # A service object method (defined as const object with methods)
        {"id": "frontend::src/services/api.ts::handleResponse", "name": "handleResponse",
         "kind": "function", "file": "src/services/api.ts", "line": 8,
         "is_exported": False,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # UI library Button component
        {"id": "ui-lib::src/Button.tsx::Button", "name": "Button",
         "kind": "function", "file": "src/Button.tsx", "line": 1,
         "is_exported": True,
         "entry_name": "ui-lib", "language": "typescript", "type": "library"},
    ]

    # TypeScript-style call edges — calleeRaw patterns that were previously unresolvable
    graph.calls = [
        # Simple function call (same file)
        {"caller_symbol_id": "frontend::src/pages/dashboard.tsx::DashboardPage",
         "caller_name": "DashboardPage",
         "callee_raw": "fetchUsers()", "file": "src/pages/dashboard.tsx", "line": 15,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # Chained call on imported object: router.push("/dashboard")
        {"caller_symbol_id": "frontend::src/pages/dashboard.tsx::DashboardPage",
         "caller_name": "DashboardPage",
         "callee_raw": "router.push(\"/dashboard\")",
         "file": "src/pages/dashboard.tsx", "line": 20,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # Method call on service object: svc.track("page_view")
        {"caller_symbol_id": "frontend::src/pages/dashboard.tsx::DashboardPage",
         "caller_name": "DashboardPage",
         "callee_raw": "svc.track(\"page_view\")",
         "file": "src/pages/dashboard.tsx", "line": 25,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # Imported function call from another module
        {"caller_symbol_id": "frontend::src/pages/dashboard.tsx::DashboardPage",
         "caller_name": "DashboardPage",
         "callee_raw": "formatDate(new Date())",
         "file": "src/pages/dashboard.tsx", "line": 30,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # Custom hook call
        {"caller_symbol_id": "frontend::src/pages/dashboard.tsx::DashboardPage",
         "caller_name": "DashboardPage",
         "callee_raw": "useAuth()",
         "file": "src/pages/dashboard.tsx", "line": 35,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # Cross-entry call to UI library Button
        {"caller_symbol_id": "frontend::src/pages/dashboard.tsx::DashboardPage",
         "caller_name": "DashboardPage",
         "callee_raw": "Button",  # JSX usage appears as reference to Button
         "file": "src/pages/dashboard.tsx", "line": 40,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
        # Nested callee: fetchUsers calls handleResponse internally
        {"caller_symbol_id": "frontend::src/api/users.ts::fetchUsers",
         "caller_name": "fetchUsers",
         "callee_raw": "handleResponse(data)",
         "file": "src/api/users.ts", "line": 10,
         "entry_name": "frontend", "language": "typescript", "type": "frontend"},
    ]

    return graph


@pytest.fixture
def ts_query() -> WorkspaceQuery:
    graph = _make_ts_graph()
    return WorkspaceQuery(graph, root="/fake")


class TestTSCalleeResolution:
    """Verify TypeScript-style call edges resolve correctly."""

    def test_simple_function_call(self, ts_query: WorkspaceQuery) -> None:
        """fetchUsers() should resolve to fetchUsers symbol."""
        callers = ts_query.get_callers("fetchUsers")
        assert callers["total"] >= 1, "fetchUsers should have callers"
        assert any(c["caller"] == "DashboardPage" for c in callers["items"]), \
            "DashboardPage should be a caller of fetchUsers"

    def test_chained_call_last_segment(self, ts_query: WorkspaceQuery) -> None:
        """router.push(...) should not match any known symbol
        (router is a variable). But callee_raw should still be visible
        as an unresolved callee entry."""
        callees = ts_query.get_callees("DashboardPage", group_by_class=False,
                                       filter_builtins=False, filter_self=False)
        callee_raws = [c["callee_raw"] for c in callees["items"]]
        assert any("router.push" in r for r in callee_raws), \
            "router.push should appear in callee_raw list"

    def test_service_method_receiver_fallback(self, ts_query: WorkspaceQuery) -> None:
        """svc.track(...) — svc is a variable, track is not a user symbol.
        Last-segment fallback won't find 'track' either.
        But the callee edge should still be stored."""
        callees = ts_query.get_callees("DashboardPage", group_by_class=False,
                                       filter_builtins=False, filter_self=False)
        callee_raws = [c["callee_raw"] for c in callees["items"]]
        assert any("svc.track" in r for r in callee_raws), \
            "svc.track should appear in callee results"

    def test_imported_func_via_dot_notation(self, ts_query: WorkspaceQuery) -> None:
        """formatDate(...) should resolve to formatDate symbol (last-segment)."""
        callers = ts_query.get_callers("formatDate")
        assert callers["total"] >= 1, "formatDate should have callers"
        assert any(c["caller"] == "DashboardPage" for c in callers["items"])

    def test_custom_hook_call(self, ts_query: WorkspaceQuery) -> None:
        """useAuth() should resolve to useAuth symbol."""
        callers = ts_query.get_callers("useAuth")
        assert callers["total"] >= 1, "useAuth should have callers"

    def test_cross_entry_call(self, ts_query: WorkspaceQuery) -> None:
        """Button from ui-lib entry should be findable as callee."""
        callers = ts_query.get_callers("Button")
        assert callers["total"] >= 1, "Button should have callers from frontend"

    def test_nested_callee_chain(self, ts_query: WorkspaceQuery) -> None:
        """fetchUsers calls handleResponse — handleResponse should
        appear as a callee of fetchUsers."""
        callees = ts_query.get_callees("fetchUsers", group_by_class=False,
                                       filter_builtins=False, filter_self=False)
        assert any("handleResponse" in c["callee_raw"] for c in callees["items"]), \
            "handleResponse should be a callee of fetchUsers"

    def test_impact_traverses_ts_edges(self, ts_query: WorkspaceQuery) -> None:
        """Impact analysis should follow TS call edges."""
        results = ts_query.get_impact("DashboardPage")
        # Should at least find fetchUsers and handleResponse
        callees = {r["callee"] for r in results}
        assert "fetchUsers" in callees, "DashboardPage impact should include fetchUsers"
        # handleResponse is called by fetchUsers which DashboardPage calls
        # (depth = 2 from DashboardPage → fetchUsers → handleResponse)
        assert "handleResponse" in callees, \
            "DashboardPage impact should transitively include handleResponse"

    def test_orphan_reachability_via_ts_edges(self, ts_query: WorkspaceQuery) -> None:
        """Orphan detection should consider resolved TS edges."""
        orphans = ts_query.get_orphans(include_public=False, skip_underscore=False,
                                       filter_noise=False)
        orphan_names = {o["name"] for o in orphans}
        # handleResponse is called by fetchUsers (which DashboardPage calls)
        # So handleResponse should NOT be an orphan
        assert "handleResponse" not in orphan_names, \
            "handleResponse should be reachable from DashboardPage"

    def test_get_callers_with_unresolved_fallback(self, ts_query: WorkspaceQuery) -> None:
        """get_callers should still work for symbols referenced
        in unresolved patterns via normalized_raw matching."""
        # Let's test that a symbol name resolved from a dotted callee_raw
        callers = ts_query.get_callers("formatDate")
        assert callers["total"] >= 1


def test_make_snippet() -> None:
    from codegraph.query import _make_snippet

    sig = 'def foo(a, b):\n    """Docstring."""\n    return a + b\n'
    snippet = _make_snippet(sig)
    assert snippet is not None
    assert "def foo" in snippet
    assert "Docstring" in snippet
    assert "return a + b" not in snippet

    sig2 = "def bar():\n    pass\n"
    snippet2 = _make_snippet(sig2)
    assert snippet2 is not None
    assert "def bar" in snippet2
    assert snippet2 == "def bar():"

    assert _make_snippet("") is None
