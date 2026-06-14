from __future__ import annotations

from codegraph.cross_service import (
    _normalize_route_path,
    _parse_url_static_segments,
    _segments_match,
    detect_cross_service_edges,
)
from codegraph.graph.types import UnifiedGraph, WorkspaceEntry, make_unified_graph


class TestNormalizeRoutePath:
    def test_express_style(self) -> None:
        assert _normalize_route_path("/api/users/:id") == ["api", "users", "*"]

    def test_flask_style(self) -> None:
        assert _normalize_route_path("/api/users/<id>") == ["api", "users", "*"]

    def test_fastapi_style(self) -> None:
        assert _normalize_route_path("/api/users/{user_id}") == ["api", "users", "*"]

    def test_no_params(self) -> None:
        assert _normalize_route_path("/api/users") == ["api", "users"]

    def test_root(self) -> None:
        assert _normalize_route_path("/") == []

    def test_nested_with_param(self) -> None:
        assert _normalize_route_path("/v2/orgs/:orgId/members") == ["v2", "orgs", "*", "members"]


class TestParseUrlStaticSegments:
    def test_absolute_url(self) -> None:
        assert _parse_url_static_segments("https://user-svc/api/users") == ["api", "users"]

    def test_relative_url(self) -> None:
        assert _parse_url_static_segments("/api/users/123") == ["api", "users", "123"]

    def test_with_query(self) -> None:
        assert _parse_url_static_segments("/api/users?page=1") == ["api", "users"]

    def test_no_path(self) -> None:
        assert _parse_url_static_segments("https://user-svc") == []

    def test_trailing_slash(self) -> None:
        assert _parse_url_static_segments("/api/users/") == ["api", "users"]


class TestSegmentsMatch:
    def test_exact_match(self) -> None:
        assert _segments_match(["api", "users"], ["api", "users"]) is True

    def test_dynamic_match(self) -> None:
        assert _segments_match(["api", "users", "123"], ["api", "users", "*"]) is True

    def test_different_length(self) -> None:
        assert _segments_match(["api", "users"], ["api", "users", "extra"]) is False

    def test_mismatch(self) -> None:
        assert _segments_match(["api", "orders"], ["api", "users"]) is False

    def test_all_dynamic(self) -> None:
        assert _segments_match(["api", "users"], ["*", "*"]) is True

    def test_empty(self) -> None:
        assert _segments_match([], []) is True


class TestDetectCrossServiceEdges:
    def _make_graph_with_calls(self, hs: list[dict], routes: list[dict]) -> UnifiedGraph:
        graph = make_unified_graph(workspace_root="/test")
        assert graph.manifest is not None
        graph.manifest.entries = [
            WorkspaceEntry(name="frontend", language="typescript", type="frontend",
                           path="./frontend", build_status="ok"),
            WorkspaceEntry(name="api", language="python", type="service",
                           path="./api", build_status="ok"),
        ]

        for h in hs:
            h.setdefault("entry_name", "frontend")
            h.setdefault("language", "typescript")
            h.setdefault("type", "frontend")
            h.setdefault("source_file", "frontend/src/api.ts")
            h.setdefault("source_line", 10)
            h.setdefault("function_name", "loadUsers")
            h.setdefault("method", "GET")
            h.setdefault("url", "https://api/users")
            h.setdefault("has_dynamic", False)
        graph.http_calls = hs

        for r in routes:
            r.setdefault("entry_name", "api")
            r.setdefault("language", "python")
            r.setdefault("type", "service")
            r.setdefault("method", "GET")
            r.setdefault("handler", "get_users")
            r.setdefault("file", "api/routes.py")
            r.setdefault("line", 5)
        graph.routes = routes

        return graph

    def test_matching_route_found(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[{
                "url": "https://api/users",
                "static_segments": ["api", "users"],
                "method": "GET",
            }],
            routes=[{
                "path": "/api/users",
            }],
        )
        edges = detect_cross_service_edges(graph)
        assert len(edges) == 1
        assert edges[0]["source_entry"] == "frontend"
        assert edges[0]["target_entry"] == "api"
        assert edges[0]["target_route_path"] == "/api/users"
        assert edges[0]["confidence"] == "high"

    def test_dynamic_route_match(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[{
                "url": "/api/users/42/profile",
                "static_segments": ["api", "users", "42", "profile"],
                "method": "GET",
            }],
            routes=[{
                "path": "/api/users/:id/profile",
                "method": "GET",
            }],
        )
        edges = detect_cross_service_edges(graph)
        assert len(edges) == 1
        assert edges[0]["target_route_path"] == "/api/users/:id/profile"

    def test_method_mismatch_lowers_confidence(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[{
                "url": "/api/users",
                "static_segments": ["api", "users"],
                "method": "POST",
            }],
            routes=[{
                "path": "/api/users",
                "method": "GET",
            }],
        )
        edges = detect_cross_service_edges(graph)
        assert len(edges) == 1
        assert edges[0]["confidence"] == "medium"

    def test_no_routes_match(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[{
                "url": "/api/orders",
                "static_segments": ["api", "orders"],
                "method": "GET",
            }],
            routes=[{
                "path": "/api/users",
                "method": "GET",
            }],
        )
        edges = detect_cross_service_edges(graph)
        assert edges == []

    def test_four_way_param_symmetry(self) -> None:
        """FastAPI {id}, Go :id, Flask <id>, and TS :id all normalize to * and match."""
        url_segments = ["api", "users", "42"]
        for route_path in ["/api/users/:id", "/api/users/<id>", "/api/users/{user_id}"]:
            route_segments = _normalize_route_path(route_path)
            assert _segments_match(url_segments, route_segments), (
                f"URL {url_segments} should match route {route_path} (got {route_segments})"
            )

    def test_four_way_detection(self) -> None:
        """Verify detect_cross_service_edges produces high-confidence edges for all param styles."""
        for route_path in ["/api/users/:id", "/api/users/<id>", "/api/users/{user_id}"]:
            graph = self._make_graph_with_calls(
                hs=[{
                    "url": "/api/users/42",
                    "static_segments": ["api", "users", "42"],
                    "method": "GET",
                }],
                routes=[{
                    "path": route_path,
                    "method": "GET",
                }],
            )
            edges = detect_cross_service_edges(graph)
            assert len(edges) == 1, f"No edge for route {route_path}"
            assert edges[0]["confidence"] == "high", (
                f"Expected high confidence for route {route_path}, got {edges[0]['confidence']}"
            )
            assert edges[0]["target_route_path"] == route_path

    def test_self_call_ignored(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[{
                "url": "/api/users",
                "static_segments": ["api", "users"],
                "method": "GET",
                "entry_name": "api",
            }],
            routes=[{
                "path": "/api/users",
                "method": "GET",
                "entry_name": "api",
            }],
        )
        edges = detect_cross_service_edges(graph)
        assert edges == []

    def test_multiple_calls_and_routes(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[
                {
                    "url": "/api/users",
                    "static_segments": ["api", "users"],
                    "method": "GET",
                    "source_line": 10,
                },
                {
                    "url": "/api/orders",
                    "static_segments": ["api", "orders"],
                    "method": "POST",
                    "source_line": 20,
                },
            ],
            routes=[
                {"path": "/api/users", "method": "GET", "handler": "get_users"},
                {"path": "/api/orders", "method": "POST", "handler": "create_order"},
                {"path": "/api/items", "method": "GET", "handler": "get_items"},
            ],
        )
        edges = detect_cross_service_edges(graph)
        assert len(edges) == 2

    def test_deduplicates_identical_edges(self) -> None:
        graph = self._make_graph_with_calls(
            hs=[
                {
                    "url": "/api/users",
                    "static_segments": ["api", "users"],
                    "method": "GET",
                    "source_line": 10,
                },
                {
                    "url": "/api/users",
                    "static_segments": ["api", "users"],
                    "method": "GET",
                    "source_line": 10,
                },
            ],
            routes=[{"path": "/api/users", "method": "GET"}],
        )
        edges = detect_cross_service_edges(graph)
        assert len(edges) == 1


class TestCrossServiceQueryIntegration:
    def test_query_returns_edges(self) -> None:
        from codegraph.query import WorkspaceQuery

        graph = make_unified_graph(workspace_root="/test")
        assert graph.manifest is not None
        graph.manifest.entries = [
            WorkspaceEntry(name="frontend", language="typescript", type="frontend",
                           path="./frontend", build_status="ok"),
        ]
        graph.http_calls = []
        graph.routes = []
        graph.cross_service_edges = [
            {
                "source_entry": "frontend",
                "source_file": "frontend/src/api.ts",
                "source_line": 10,
                "source_symbol": "loadUsers",
                "method": "GET",
                "url_pattern": "https://api/users",
                "target_entry": "api",
                "target_route_path": "/api/users",
                "target_route_handler": "get_users",
                "confidence": "high",
            },
        ]

        q = WorkspaceQuery(graph, root="/test")
        edges = q.get_cross_service_edges()
        assert len(edges) == 1
        assert edges[0]["source_entry"] == "frontend"
        assert edges[0]["target_entry"] == "api"

    def test_filter_by_source(self) -> None:
        from codegraph.query import WorkspaceQuery

        graph = make_unified_graph(workspace_root="/test")
        assert graph.manifest is not None
        graph.manifest.entries = [
            WorkspaceEntry(name="frontend", language="typescript", type="frontend",
                           path="./frontend", build_status="ok"),
            WorkspaceEntry(name="mobile", language="typescript", type="frontend",
                           path="./mobile", build_status="ok"),
        ]
        graph.cross_service_edges = [
            {
                "source_entry": "frontend", "source_file": "f.ts",
                "source_line": 1, "source_symbol": "f",
                "method": "GET", "url_pattern": "/api/users",
                "target_entry": "api", "target_route_path": "/api/users",
                "target_route_handler": "h", "confidence": "high",
            },
            {
                "source_entry": "mobile", "source_file": "m.ts",
                "source_line": 1, "source_symbol": "g",
                "method": "GET", "url_pattern": "/api/users",
                "target_entry": "api", "target_route_path": "/api/users",
                "target_route_handler": "h", "confidence": "high",
            },
        ]

        q = WorkspaceQuery(graph, root="/test")
        edges = q.get_cross_service_edges(source_entry="frontend")
        assert len(edges) == 1
        assert edges[0]["source_entry"] == "frontend"
