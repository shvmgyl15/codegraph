from __future__ import annotations

from typing import Any

from codegraph.graph.types import UnifiedGraph


def resolve_dispatch_routes(graph: UnifiedGraph) -> list[dict[str, Any]]:
    routes: list[dict[str, Any]] = []
    for sym in graph.symbols:
        for ec in sym.get("event_consumptions", []):
            guards = ec.get("guards")
            if not guards:
                continue
            routes.append({
                "guards": guards,
                "handler_symbol": sym.get("name", ""),
                "handler_file": sym.get("file", ""),
                "handler_line": sym.get("line", 0),
                "service": sym.get("entry_name", ""),
                "flow_outcome": "unknown",
            })
    return routes


def match_sse_backend_to_frontend(
    graph: UnifiedGraph,
    event_boundaries: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    backend_producers: list[dict[str, Any]] = []
    for sym in graph.symbols:
        for ep in sym.get("event_productions", []):
            if any(
                b.get("type") == "producer"
                and ep.get("boundary") == b.get("name")
                for b in (event_boundaries or [])
            ):
                backend_producers.append({
                    "symbol": sym.get("name", ""),
                    "file": sym.get("file", ""),
                    "entry": sym.get("entry_name", ""),
                    **{k: v for k, v in ep.items() if k != "boundary"},
                })

    frontend_consumers: list[dict[str, Any]] = []
    for sym in graph.symbols:
        for ec in sym.get("event_consumptions", []):
            for b in (event_boundaries or []):
                if b.get("type") != "producer":
                    continue
                if ec.get("boundary") != b.get("name"):
                    continue
                frontend_consumers.append({
                    "symbol": sym.get("name", ""),
                    "file": sym.get("file", ""),
                    "entry": sym.get("entry_name", ""),
                    **{k: v for k, v in ec.items() if k != "boundary"},
                })

    edges: list[dict[str, Any]] = []
    for prod in backend_producers:
        prod_url = prod.get("url", "")
        if not prod_url:
            continue
        for cons in frontend_consumers:
            cons_url = cons.get("url", "") or cons.get("urlPattern", "")
            if not cons_url:
                continue
            if cons_url in prod_url or prod_url in cons_url:
                edges.append({
                    "backend_symbol": prod["symbol"],
                    "backend_file": prod["file"],
                    "backend_entry": prod["entry"],
                    "frontend_symbol": cons["symbol"],
                    "frontend_file": cons["file"],
                    "frontend_entry": cons["entry"],
                    "url_pattern": prod_url,
                    "match_type": "prefix",
                })

    return edges


def _resolve_step(
    step: dict[str, Any],
    graph: UnifiedGraph,
    dispatch_routes: list[dict[str, Any]],
    event_boundaries: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    step_type = step.get("type", "")
    resolved: list[dict[str, Any]] = []

    if step_type == "http_handler":
        handler = step.get("dispatch_key", {}).get("handler", "")
        for route in graph.routes:
            if handler and route.get("handler") != handler:
                continue
            resolved.append({
                "step_type": "http_handler",
                "symbol": route.get("handler", ""),
                "file": route.get("file", ""),
                "line": route.get("line", 0),
                "method": route.get("method", ""),
                "path": route.get("path", ""),
                "outcome": step.get("outcome"),
            })

    elif step_type == "db_callback":
        dk = step.get("dispatch_key", {})
        for dr in dispatch_routes:
            guards = {g["field"]: g.get("value") for g in dr.get("guards", [])}
            match = True
            for k, v in dk.items():
                if guards.get(k) != v:
                    match = False
                    break
            if match:
                resolved.append({
                    "step_type": "db_callback",
                    "symbol": dr["handler_symbol"],
                    "file": dr["handler_file"],
                    "line": dr["handler_line"],
                    "service": dr.get("service", ""),
                    "outcome": step.get("outcome"),
                })

    elif step_type == "kafka_bridge":
        target_topic = step.get("topic", "")
        for sym in graph.symbols:
            for ep in sym.get("event_productions", []):
                if ep.get("topic") == target_topic:
                    resolved.append({
                        "step_type": "kafka_bridge",
                        "symbol": sym.get("name", ""),
                        "file": sym.get("file", ""),
                        "line": ep.get("line", 0),
                        "topic": target_topic,
                        "outcome": step.get("outcome"),
                    })

    elif step_type == "sse_push":
        for sym in graph.symbols:
            for ep in sym.get("event_productions", []):
                for b in event_boundaries:
                    if b.get("type") != "producer":
                        continue
                    if ep.get("boundary") != b.get("name"):
                        continue
                    resolved.append({
                        "step_type": "sse_push",
                        "symbol": sym.get("name", ""),
                        "file": sym.get("file", ""),
                        "line": ep.get("line", 0),
                        "outcome": step.get("outcome"),
                    })

    return resolved


def resolve_async_flows(
    graph: UnifiedGraph,
    flow_configs: list[dict[str, Any]],
    event_boundaries: list[dict[str, Any]] | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    dispatch_routes = resolve_dispatch_routes(graph)
    warnings: list[dict[str, Any]] = []
    resolved_flows: list[dict[str, Any]] = []
    event_boundaries = event_boundaries or []

    for flow_cfg in flow_configs:
        flow_name: str = flow_cfg.get("name", "unnamed")
        flow_steps: list[dict[str, Any]] = []
        all_ok = True

        def walk_steps(
            steps: list[dict[str, Any]],
            outcome: str | None = None,
            _fn: str = flow_name,
            _fs: list[dict[str, Any]] = flow_steps,
        ) -> None:
            nonlocal all_ok
            for step in steps:
                s = dict(step)
                if outcome is not None:
                    s["outcome"] = outcome
                resolved = _resolve_step(s, graph, dispatch_routes, event_boundaries)
                if not resolved:
                    stype = step.get("type", "?")
                    msg = (
                        f"Step '{stype}' in flow '{_fn}'"
                        " could not be resolved to any symbol"
                    )
                    warnings.append({
                        "severity": "error",
                        "code": "INCOMPLETE_FLOW",
                        "message": msg,
                        "flow": _fn,
                        "step": len(_fs),
                        "hint": "Check that the step config matches symbols in the graph",
                    })
                    all_ok = False
                _fs.extend(resolved)

                walk_steps(step.get("success", []), "success", _fn, _fs)
                walk_steps(step.get("failure", []), "failure", _fn, _fs)

        walk_steps(flow_cfg.get("steps", []))

        resolved_flows.append({
            "name": flow_name,
            "resolved": all_ok,
            "steps": flow_steps,
            "warnings": [],
        })

    return resolved_flows, warnings


def check_flow_warnings(
    graph: UnifiedGraph,
    flows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    warnings: list[dict[str, Any]] = []

    dispatch_routes = resolve_dispatch_routes(graph)

    for dr in dispatch_routes:
        handler_name = dr["handler_symbol"]
        has_production = False
        for sym in graph.symbols:
            if sym.get("name") == handler_name:
                for _ in sym.get("event_productions", []):
                    has_production = True
                    break
        if not has_production:
            warnings.append({
                "severity": "warning",
                "code": "SILENT_DEADEND",
                "message": (
                    f"Dispatch handler '{handler_name}' has no event "
                    "productions (kafka_publish, sse_push, etc.)"
                ),
                "flow": "",
                "step": 0,
                "hint": (
                    "This handler runs but produces no async event. "
                    "Confirm this is intentional or add a "
                    "kafka_publish/sse_push call."
                ),
            })

    for flow in flows:
        for step in flow.get("steps", []):
            if step.get("step_type") == "sse_push":
                has_subscriber = any(
                    e.get("backend_symbol") == step.get("symbol")
                    for e in graph.sse_edges
                )
                if not has_subscriber:
                    warnings.append({
                        "severity": "warning",
                        "code": "MISSING_SSE_SUBSCRIBER",
                        "message": (
                            f"SSE push from '{step.get('symbol')}' "
                            "has no matching frontend subscriber"
                        ),
                        "flow": flow.get("name", ""),
                        "step": 0,
                        "hint": (
                            "Check that a frontend EventSource or "
                            "hook is listening for this event."
                        ),
                    })

    return warnings
