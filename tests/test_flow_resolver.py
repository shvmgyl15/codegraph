from __future__ import annotations

from codegraph.flow_resolver import (
    check_flow_warnings,
    match_sse_backend_to_frontend,
    resolve_async_flows,
    resolve_dispatch_routes,
)
from codegraph.graph.types import UnifiedGraph, make_unified_graph


def _graph() -> UnifiedGraph:
    g = make_unified_graph(workspace_root="/test")
    g.symbols = [
        {
            "name": "Handler1",
            "event_consumptions": [{"guards": [{"field": "entityType", "value": "ORDER"}]}],
            "file": "app.py", "line": 10, "entry_name": "svc",
        },
        {
            "name": "Handler2",
            "event_consumptions": [{"guards": [{"field": "entityType", "value": "USER"}]}],
            "file": "app.py", "line": 20, "entry_name": "svc",
        },
        {
            "name": "Handler3",
            "event_productions": [{"boundary": "sse_emit", "url": "/events"}],
            "event_consumptions": [{"guards": [
                {"field": "entityType", "value": "ORDER"},
                {"field": "commandName", "value": "CREATE"},
            ]}],
            "file": "app.py", "line": 30, "entry_name": "svc",
        },
    ]
    return g


class TestResolveDispatchRoutes:
    def test_returns_routes_with_guards(self) -> None:
        g = _graph()
        routes = resolve_dispatch_routes(g)
        assert len(routes) == 3
        assert routes[0]["handler_symbol"] == "Handler1"
        assert routes[1]["handler_symbol"] == "Handler2"
        assert routes[2]["handler_symbol"] == "Handler3"

    def test_skips_symbols_without_guards(self) -> None:
        g = _graph()
        g.symbols.append({
            "name": "NoGuard",
            "event_consumptions": [{"boundary": "kafka_consume"}],
            "file": "x.py", "line": 1,
        })
        routes = resolve_dispatch_routes(g)
        names = {r["handler_symbol"] for r in routes}
        assert "NoGuard" not in names


class TestResolveAsyncFlows:
    def test_resolves_matching_flow(self) -> None:
        g = _graph()
        flows_cfg = [{
            "name": "test_flow",
            "steps": [{"type": "db_callback", "dispatch_key": {"entityType": "ORDER"}}],
        }]
        flows, warnings = resolve_async_flows(g, flows_cfg)
        assert len(flows) == 1
        assert flows[0]["resolved"] is True
        assert len(flows[0]["steps"]) == 2
        assert flows[0]["steps"][0]["symbol"] == "Handler1"
        assert flows[0]["steps"][1]["symbol"] == "Handler3"

    def test_incomplete_flow_warning(self) -> None:
        g = _graph()
        flows_cfg = [{
            "name": "bad_flow",
            "steps": [{"type": "db_callback", "dispatch_key": {"entityType": "NONEXISTENT"}}],
        }]
        flows, warnings = resolve_async_flows(g, flows_cfg)
        assert flows[0]["resolved"] is False
        assert len(warnings) == 1
        assert warnings[0]["code"] == "INCOMPLETE_FLOW"


class TestCheckFlowWarnings:
    def test_silent_deadend_detected(self) -> None:
        g = _graph()
        resolve_dispatch_routes(g)
        g.symbols = [s for s in g.symbols if s.get("name") != "Handler3"]
        warnings = check_flow_warnings(g, [])
        codes = {w["code"] for w in warnings}
        assert "SILENT_DEADEND" in codes

    def test_no_warning_when_handler_has_production(self) -> None:
        g = _graph()
        warnings = check_flow_warnings(g, [])
        handler3_warnings = [w for w in warnings if "Handler3" in w.get("message", "")]
        assert len(handler3_warnings) == 0


class TestMatchSSEEdges:
    def test_matches_by_url_prefix(self) -> None:
        g = _graph()
        g.symbols = [
            {"name": "Backend", "entry_name": "api",
             "event_productions": [{"boundary": "sse_emit", "url": "/api/events"}]},
            {"name": "Frontend", "entry_name": "web",
             "event_consumptions": [{"boundary": "sse_subscribe", "urlPattern": "/api/events"}]},
        ]
        boundaries = [
            {"name": "sse_emit", "type": "producer", "match": {}},
            {"name": "sse_subscribe", "type": "producer", "match": {}},
        ]
        edges = match_sse_backend_to_frontend(g, boundaries)
        assert len(edges) >= 1
        assert edges[0]["backend_entry"] == "api"
        assert edges[0]["frontend_entry"] == "web"
