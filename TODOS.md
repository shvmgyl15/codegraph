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

## Async Flow Analysis

Extend codegraph + sub-tools with config-driven async flow analysis (callbacks, Kafka, SSE, etc.)

### Phase 1: Config forwarding (codegraph → sub-tools via CODEGRAPH_EVENT_CONFIG env var)

- [ ] 1a: Add `EventBoundaryConfig`, `EventBoundaryMatch`, `FlowStep`, `FlowConfig` models to `config.py`
- [ ] 1b: Pass `CODEGRAPH_EVENT_CONFIG` env var to sub-tools in `builder.py:_build_entry`
- [ ] 1c: Add `load_event_config()` to pygraph's `config.py` (reads env var, falls back to pyproject.toml)
- [ ] 1d: Add `loadEventConfig()` to tsgraph's `builder.ts`
- [ ] 1e: Verify: `codegraph build --force` forwards config, sub-tools receive it

### Phase 2a: pygraph event boundary extraction

- [ ] 2a1: Add `event_productions`, `event_consumptions` fields to pygraph `SymbolNode`
- [ ] 2a2: Create `extract_event_productions()` in `extractors/events.py` (match call sites against producer configs)
- [ ] 2a3: Create `extract_event_consumptions()` in `extractors/events.py` (match decorators, interfaces, guards)
- [ ] 2a4: Create `extract_dispatch_guards()` — first if/elif block literal comparisons
- [ ] 2a5: Integrate into `extractors/symbols.py` — call extractors during symbol construction
- [ ] 2a6: Add defaults in `serialize.py:_dict_to_symbol`
- [ ] 2a7: Tests + verify pygraph build produces new fields

### Phase 2b: tsgraph SSE subscriber extraction

- [ ] 2b1: Add `eventProductions`, `eventConsumptions` to tsgraph `SymbolNode`
- [ ] 2b2: Create `extractSSESubscriber()` in `extractors/events.ts` (EventSource, hook patterns, one-step variable trace)
- [ ] 2b3: Integrate into `builder.ts` — call extractors during symbol processing
- [ ] 2b4: Tests + verify tsgraph build produces new fields

### Phase 3: codegraph flow correlation pass

- [ ] 3a: Add `dispatch_routes`, `flows`, `sse_edges`, `flow_warnings` to `UnifiedGraph` + `ARRAY_FIELDS`
- [ ] 3b: Create `resolve_dispatch_routes()` in `flow_resolver.py`
- [ ] 3c: Create `match_sse_backend_to_frontend()` in `flow_resolver.py`
- [ ] 3d: Create `resolve_async_flows()` with branching (success/failure) in `flow_resolver.py`
- [ ] 3e: Create `check_flow_warnings()` in `flow_resolver.py`
- [ ] 3f: Integrate into `builder.py:build_and_write` — run after cross_service_edges
- [ ] 3g: **Checkpoint**: `codegraph build --force` with no flows → `dispatch_map()` returns handlers; then declare flow → `flows` + `flow_warnings` populated

### Phase 4: Plugin MCP tool API

- [ ] 4a: Add `MCPTool` dataclass to `plugin.py`
- [ ] 4b: Modify `run_plugins()` to check for `register_tools(graph)` and return `list[MCPTool]`
- [ ] 4c: Dynamic plugin tool registration in `server.py:run_server()`
- [ ] 4d: Verify: test plugin with `register_tools` → tool appears as `plugin.<stem>.<name>`

### Phase 5: Built-in async flow MCP tools

- [ ] 5a: Create `async_flow_tools.py` plugin with `dispatch_map`, `trace_async_flow`, `flow_warnings`, `sse_edges`
- [ ] 5b: Auto-load in `builder.py` as implicit built-in plugin
- [ ] 5c: Verify all 4 tools respond with pre-computed data from graph
- [ ] 5d: End-to-end test: full workspace build → query tools work
