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
- **User-enriched** — auto-detection is a best-effort default. The user overrides
  via `codegraph.jsonc`.

### Boundaries

- **gograph/tsgraph/pygraph**: Own all per-language extraction (symbols, calls, routes,
  HTTP client calls, errors, env reads, test edges).
- **codegraph**: Owns workspace orchestration, cross-service analysis, and unified MCP.
  Does NOT duplicate per-language extraction.

---

## Completed

- [x] Phase 1: Scaffold + Config + Auto-Discovery
- [x] Phase 2: Merge + Query Engine
- [x] Phase 3: MCP Server

## Phase 4: Cross-Service Edges

Detect HTTP client calls in each entry and link them to server-side route definitions
across different entries using ordered segment matching.

### Implementation

**Step A — Per-language HTTP call extraction** (in gograph/tsgraph/pygraph):
- Add `HttpCallEdge` type to each tool's schema
- Extract HTTP client calls from source AST: `requests.get`, `fetch`, `http.Get`, etc.
- Record: source file, line, function name, HTTP method, URL string, static path segments

**Step B — codegraph merge + match**:
- Read `http_calls` array from each tool's graph.json (stamp entry metadata)
- Implement ordered segment URL → route matching
- Generate `CrossServiceEdge` entries linking source calls to target routes
- Add `cross_service_edges` to `UnifiedGraph` schema + serialization

**Step C — Query + MCP + CLI**:
- `WorkspaceQuery.get_cross_service_edges()` — list all edges
- `WorkspaceQuery.get_impact()` — optionally follow cross-service edges
- MCP tool: `cross_service_calls`
- CLI: `codegraph cross-service`

### Tasks

- [x] pygraph: Add `HttpCallEdge` type + `extract_http_calls()` extractor
- [x] tsgraph: Add `HttpCallEdge` type + HTTP client call extraction
- [x] gograph: Add `HttpCallEdge` type + HTTP client call extraction
- [x] codegraph: Add `CrossServiceEdge` to schema + serialization
- [x] codegraph: Read `http_calls` from tool outputs in builder
- [x] codegraph: Implement ordered segment URL → route matching in `cross_service.py`
- [x] codegraph: Generate `CrossServiceEdge` entries during build
- [x] codegraph: Add `get_cross_service_edges()` to `WorkspaceQuery`
- [x] codegraph: Add `codegraph cross-service` CLI command
- [x] codegraph: Add `cross_service_calls` MCP tool
- [x] codegraph: Tests for cross-service edge detection and matching
- [x] All: Run tests + lint, fix, commit, push

## Phase 5: Plugin System + README + OpenCode

- [x] Implement `plugin.py` — importlib-based plugin loader (mirrors pygraph pattern)
- [x] Update `config.py` — add `plugins: list[str]` field to Pydantic model
- [x] Update `builder.py` — call `run_plugins()` after merge, before write
- [x] Implement `commands/opencode_plugin.py` — generates `.opencode.json`
- [x] Update `cli.py` — add `add-opencode-plugin` command
- [x] Update `server.py` — add `add_opencode_plugin` MCP tool
- [x] Rewrite `README.md` — full documentation with quick start, MCP tools, architecture
- [x] Write plugin tests (7 tests: valid, missing, no-run, raises, no-op, multiple, partial failure)
- [x] Write opencode plugin tests
- [x] Run tests + lint, fix, commit, push

## Dogfooding results

- [x] Run `codegraph build` against the vibe workspace (gograph/tsgraph/pygraph as entries)
- [x] Verify all 3 tools build and merge correctly
- [x] Fix builder: gograph/tsgraph use positional path args, pygraph uses `--root`
- [x] Fix status: read manifest for real build statuses instead of re-discovering
- [x] Verify cross-entry queries (query, context, callers, callees, orphans)
- [x] Verify MCP server starts
- [x] Cross-service edges: 0 (expected — no routes in libraries)
- [x] HTTP calls: detected from gograph test code (field name format confirmed: camelCase)
