from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from codegraph.graph.types import UnifiedGraph
from codegraph.plugin import MCPTool


def run(graph: UnifiedGraph) -> None:
    pass


def register_tools(graph: UnifiedGraph) -> list[MCPTool]:
    return [
        MCPTool(
            name="dispatch_map",
            description="List dispatch handlers with optional entity/command filters",
            input_schema={
                "type": "object",
                "properties": {
                    "entity_type": {"type": "string", "description": "Filter by entity type"},
                    "command_name": {"type": "string", "description": "Filter by command name"},
                },
            },
            handler=lambda args, g: _handle_dispatch_map(args, g),
        ),
        MCPTool(
            name="trace_async_flow",
            description="Resolved steps for a named flow with optional filter",
            input_schema={
                "type": "object",
                "properties": {
                    "flow_name": {"type": "string", "description": "Name of the flow to trace"},
                    "entity_type": {"type": "string", "description": "Filter by entity type"},
                    "command_name": {"type": "string", "description": "Filter by command name"},
                    "outcome": {
                        "type": "string", "enum": ["success", "failure"],
                        "description": "Filter by outcome branch",
                    },
                },
                "required": ["flow_name"],
            },
            handler=lambda args, g: _handle_trace_async_flow(args, g),
        ),
        MCPTool(
            name="flow_warnings",
            description="Flow completeness warnings filterable by severity/code/flow",
            input_schema={
                "type": "object",
                "properties": {
                    "severity": {
                        "type": "string", "enum": ["error", "warning"],
                        "description": "Filter by severity",
                    },
                    "code": {"type": "string", "description": "Filter by warning code"},
                    "flow_name": {"type": "string", "description": "Filter by flow name"},
                },
            },
            handler=lambda args, g: _handle_flow_warnings(args, g),
        ),
        MCPTool(
            name="sse_edges",
            description="SSE backend-to-frontend edges filterable by service",
            input_schema={
                "type": "object",
                "properties": {
                    "service_from": {"type": "string", "description": "Filter by source service"},
                    "service_to": {"type": "string", "description": "Filter by target service"},
                },
            },
            handler=lambda args, g: _handle_sse_edges(args, g),
        ),
    ]


def _handle_dispatch_map(args: dict[str, Any], graph: UnifiedGraph) -> str:
    items = list(graph.dispatch_routes)
    et = args.get("entity_type")
    cn = args.get("command_name")
    workspace_root = graph.workspace_root

    for item in items:
        for g in item.get("guards", []):
            if g.get("const_ref"):
                fp = item.get("handler_file", "")
                line = item.get("handler_line", 0)
                if fp and line:
                    try:
                        resolved = Path(workspace_root) / fp if workspace_root else Path(fp)
                        lines = resolved.read_text().splitlines()
                        if 0 < line <= len(lines):
                            g["source_snippet"] = lines[line - 1].rstrip()
                    except OSError:
                        pass

    if et or cn:
        filtered = []
        for item in items:
            guards = {g["field"]: g.get("value") for g in item.get("guards", [])}
            if et and guards.get("entityType") != et:
                continue
            if cn and guards.get("commandName") != cn:
                continue
            filtered.append(item)
        items = filtered

    return json.dumps({
        "items": items,
        "count": len(items),
        "note": (
            "Guard extraction is best-effort (first if/elif or try block). "
            "Guards with const_ref=true have unresolved values — inspect "
            "source_snippet to resolve them, or use context()/callers() "
            "to trace cross-function delegation."
        ),
    }, indent=2)


def _handle_trace_async_flow(args: dict[str, Any], graph: UnifiedGraph) -> str:
    flow_name = args.get("flow_name", "")
    et = args.get("entity_type")
    cn = args.get("command_name")
    outcome = args.get("outcome")

    for flow in graph.flows:
        if flow.get("name") != flow_name:
            continue
        steps = list(flow.get("steps", []))

        if et or cn:
            steps = [s for s in steps if _matches_guards(s, et, cn)]
        if outcome:
            steps = [s for s in steps if s.get("outcome") == outcome]

        return json.dumps({
            "flow": flow_name,
            "resolved": flow.get("resolved", False),
            "steps": steps,
            "count": len(steps),
        }, indent=2)

    return json.dumps({"error": f"Flow '{flow_name}' not found"})


def _matches_guards(
    step: dict[str, Any],
    entity_type: str | None,
    command_name: str | None,
) -> bool:
    for guard in step.get("guards", []):
        f = guard.get("field")
        v = guard.get("value")
        if entity_type and f == "entityType" and v == entity_type:
            return True
        if command_name and f == "commandName" and v == command_name:
            return True
    return not entity_type and not command_name


def _handle_flow_warnings(args: dict[str, Any], graph: UnifiedGraph) -> str:
    items = list(graph.flow_warnings)
    severity = args.get("severity")
    code = args.get("code")
    flow_name = args.get("flow_name")

    if severity:
        items = [w for w in items if w.get("severity") == severity]
    if code:
        items = [w for w in items if w.get("code") == code]
    if flow_name:
        items = [w for w in items if w.get("flow") == flow_name]

    return json.dumps({"items": items, "count": len(items)}, indent=2)


def _handle_sse_edges(args: dict[str, Any], graph: UnifiedGraph) -> str:
    items = list(graph.sse_edges)
    service_from = args.get("service_from")
    service_to = args.get("service_to")

    if service_from:
        items = [e for e in items if e.get("backend_entry") == service_from]
    if service_to:
        items = [e for e in items if e.get("frontend_entry") == service_to]

    return json.dumps({"items": items, "count": len(items)}, indent=2)
