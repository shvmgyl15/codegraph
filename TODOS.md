# codegraph — Multi-language Workspace Code Graph

## Vision

`codegraph` is a thin orchestration layer that sits at the root of a multi-language,
multi-repository workspace (monorepo or submodule-based). It:

1. **Auto-discovers** every service, frontend, gateway, and library in the workspace
2. **Orchestrates builds** by shelling out to language-specific tools (`gograph`,
   `tsgraph`, `pygraph`) in each entry's directory
3. **Merges** all per-entry `graph.json` outputs into a single unified graph
4. **Exposes a single MCP server** with tools that can query any symbol in any
   service, regardless of language

### Design principles

- **Language-agnostic** — no language is special. All entries are equal in the schema.
- **Resilient** — one entry failing to build doesn't block others. Partial results are useful.
- **Clean state** — single `.codegraph/` output directory. `codegraph clean` removes everything.
- **User-enriched** — auto-detection is a best-effort default. The user overrides via `codegraph.jsonc`.

---

## Completed

### Core features
- [x] Phase 1: Config forwarding (CODEGRAPH_EVENT_CONFIG env var)
- [x] Phase 2a: pygraph event boundary extraction (event_productions, event_consumptions)
- [x] Phase 2b: tsgraph SSE subscriber extraction
- [x] Phase 3: Flow correlation pass (dispatch_routes, sse_edges, flow_resolver, flow_warnings)
- [x] Phase 4: Plugin MCP tool API (MCPTool dataclass, register_tools hook)
- [x] Phase 5: Built-in async flow MCP tools (dispatch_map, trace_async_flow, flow_warnings, sse_edges)

### Bug fixes
- [x] _match_callee handles Call node values (SomeClass().method())
- [x] extract_dispatch_guards handles data.get("key") == value and chained attribute right sides
- [x] Recursive guard path extraction (all if/elif nesting levels)
- [x] extract_dispatch_guards scans all top-level statements (not just body[0])
- [x] flow_resolver: event_boundaries parameter was hardcoded to empty list

### Quality of life
- [x] filter_noise on context()/callees() with dotted chain prefix walk
- [x] filter_dict_accessors, filter_constructors surfaced on context()
- [x] context(source=True) scoped to symbol's lines only
- [x] query_symbols results include token-efficient snippet field
- [x] source_snippet + note on dispatch_map responses

### Team sharing
- [x] classification.json moved to codegraph.d/ (outside .codegraph/)
- [x] Auto-discover drops entries with missing paths
- [x] Auto-scan codegraph.d/plugins/ for plugins
- [x] Migration: old .codegraph/classification.json copied to codegraph.d/ on first load

### Documentation
- [x] AGENTS.md: plugin MCP tool API documented
- [x] README.md: plugin system, async flow config, MCP tool table updated
- [x] Install instructions corrected (workspace-graph, pygraph-mcp, @shvmgyl15/tsgraph)

### Tests
- [x] Test coverage for flow_resolver dispatch_routes, async_flows, flow_warnings, sse_edges
- [x] Test coverage for _load_source_snippet, _make_snippet
- [x] 124 tests total
