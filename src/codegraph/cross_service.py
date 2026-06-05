from __future__ import annotations

from typing import Any

from codegraph.graph.types import UnifiedGraph


def _normalize_route_path(path: str) -> list[str]:
    parts = path.strip("/").split("/")
    result: list[str] = []
    for p in parts:
        if not p:
            continue
        is_param = p.startswith((":", "{", "<")) or p.endswith(("}", ">"))
        if is_param:
            result.append("*")
        else:
            result.append(p)
    return result


def _parse_url_static_segments(url: str) -> list[str]:
    if "://" in url:
        url = url.split("://", 1)[1]
        if "/" in url:
            url = url[url.index("/"):]
        else:
            return []
    if "?" in url:
        url = url.split("?", 1)[0]
    parts = url.strip("/").split("/")
    return [p for p in parts if p]


def _segments_match(
    url_segments: list[str], route_segments: list[str]
) -> bool:
    if len(url_segments) != len(route_segments):
        return False
    for u, r in zip(url_segments, route_segments, strict=True):
        if r == "*":
            continue
        if u != r:
            return False
    return True


def _extract_http_method(http_call: dict[str, Any]) -> str:
    raw = http_call.get("method", "GET")
    if not isinstance(raw, str) or not raw:
        return "GET"
    return raw.upper()


def detect_cross_service_edges(unified: UnifiedGraph) -> list[dict[str, Any]]:
    entries: dict[str, list[dict[str, Any]]] = {}
    for call in unified.http_calls:
        entry_name = call.get("entry_name", "")
        entries.setdefault(entry_name, []).append(call)

    routes_by_entry: dict[str, list[dict[str, Any]]] = {}
    for route in unified.routes:
        entry_name = route.get("entry_name", "")
        routes_by_entry.setdefault(entry_name, []).append(route)

    edges: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, int]] = set()

    for source_entry, calls in entries.items():
        for call in calls:
            method = _extract_http_method(call)
            url = call.get("url", "")
            call_segments = call.get("static_segments", [])
            parsed = call_segments if call_segments else _parse_url_static_segments(url)

            if not parsed:
                continue

            for target_entry, target_routes in routes_by_entry.items():
                if target_entry == source_entry:
                    continue

                for route in target_routes:
                    route_method = route.get("method", "").upper()
                    route_path = route.get("path", "")
                    route_segments = _normalize_route_path(route_path)

                    if not _segments_match(parsed, route_segments):
                        continue

                    confidence = "high" if method == route_method else "medium"

                    dedup_key = (
                        source_entry, target_entry,
                        method, route_path, call.get("source_line", 0),
                    )
                    if dedup_key in seen:
                        continue
                    seen.add(dedup_key)

                    edges.append({
                        "source_entry": source_entry,
                        "source_file": call.get("source_file", ""),
                        "source_line": call.get("source_line", 0),
                        "source_symbol": call.get("function_name", ""),
                        "method": method,
                        "url_pattern": url,
                        "target_entry": target_entry,
                        "target_route_path": route_path,
                        "target_route_handler": route.get("handler", ""),
                        "confidence": confidence,
                    })

    return edges
