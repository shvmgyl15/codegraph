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
- **Non-invasive** — zero changes to gograph/tsgraph/pygraph. They are consumed as
  black-box CLIs.
- **Resilient** — one entry failing to build doesn't block others. Partial results
  are still useful.
- **Clean state** — single `.codegraph/` output directory. `codegraph clean` removes
  everything.
- **User-enriched** — auto-detection is a best-effort default. The user overrides
  via `codegraph.jsonc`.

### Auto-detection probes

| File | Language | Type heuristic |
|---|---|---|
| `go.mod` | Go | `main.go` / `cmd/` → `service`, else `library` |
| `package.json` | TypeScript | Next.js config → `frontend`, else `library` |
| `pyproject.toml` / `setup.py` / `requirements.txt` | Python | Flask/FastAPI/Django patterns → `service`/`gateway`, else `library` |
| `Cargo.toml` | Rust | (detected, type: `library` — no graph tool yet) |
| `pom.xml` / `build.gradle` | Java | (detected, type: `library` — no graph tool yet) |
| (no match) | — | Skipped with warning |

Languages with no graph tool are detected and listed in `status` but marked as
`unbuilt` — the user knows they exist, they just aren't indexed.

### Config: `codegraph.jsonc` at workspace root

```jsonc
{
  "version": 1,
  "auto_discover": true,
  "entries": [
    { "name": "frontend",    "path": "./frontend",   "language": "typescript", "type": "frontend" },
    { "name": "api-gateway", "path": "./api-gateway","language": "python",     "type": "gateway" },
    { "name": "user-svc",    "path": "./user-svc",   "language": "go",         "type": "service" },
    { "name": "py-common",   "path": "./libs/py-common", "language": "python",  "type": "library" }
  ]
}
```

---

## Phase 1: Scaffold + Config + Auto-Discovery

- [x] Initialize `pyproject.toml` with typer, pathspec, pydantic, mcp
- [x] Create `src/codegraph/` package skeleton (`__init__.py`, `__main__.py`)
- [x] Configure mypy (strict) and ruff
- [x] Define `WorkspaceEntry` dataclass (name, path, language, type, build_status, …)
- [x] Define `UnifiedGraph` dataclass (merged schema with entry_name/language/type stamps on every node/edge)
- [x] Implement `config.py` — load/validate `codegraph.jsonc`, merge with defaults
- [x] Implement `discover.py` — probe subdirectories for known files, detect language + type
- [x] Support languages without graph tools (Rust, Java, etc.) as detected + listed but unbuilt
- [x] Implement `cli.py` — typer app with `status`, `build`, `build --entry=`, `clean`
- [x] Implement `commands/status.py` — detect + display entries table (name, language, type, build_status)
- [x] Implement `commands/build.py` — orchestrate tool builds per entry, handle failures gracefully
- [x] Implement `commands/clean.py` — rm -rf .codegraph/
- [x] Write serialization (`graph/types.py` + `graph/serialize.py`)
- [x] Write tests for config, discover, and build orchestration

## Phase 2: Merge + Query Engine

- [x] Implement graph merging logic (ID prefixing with `{entry_name}::`, field stamping, deduplication)
- [x] Generate `.codegraph/manifest.json` with entry metadata, timestamps, tool versions
- [x] Implement `WorkspaceQuery` — wraps the merged graph with entry-aware lookups
- [x] Implement `commands/query_cmd.py` — search symbols across all entries
- [x] Implement `commands/callers.py` — find callers tagged with entry
- [x] Implement `commands/callees.py` — find callees tagged with entry
- [x] Implement `commands/routes.py` — all HTTP routes with language/type/entry
- [x] Implement `commands/impact.py` — blast radius across entry boundaries
- [x] Implement `commands/orphans.py` — dead code with `--exclude-type` filter
- [x] Implement `commands/context.py` — bundle: source + callers + callees + tests
- [x] Implement `commands/trace.py` — error flow across all entries
- [x] Write tests for merged query engine

## Phase 3: MCP Server

- [x] Implement `server.py` — MCP stdio server wrapping `WorkspaceQuery`
- [x] Tool: `status` — list entries with language/type/build_status
- [x] Tool: `query` — search symbols
- [x] Tool: `callers` / `callees` / `context`
- [x] Tool: `routes` — with entry/type/language filter params
- [x] Tool: `impact` — with `--max-depth` and cross-entry visibility
- [x] Tool: `orphans` — with `--exclude-type` param
- [x] Tool: `trace` — error flow search
- [x] Write MCP server tests

## Phase 4: Cross-Service Edges (future)

Detect HTTP/gRPC client calls and link them to server-side route definitions
across different entries.

- [ ] Detect HTTP client calls: `requests.get`, `httpx`, `fetch`, `axios`, `net/http`
- [ ] Parse URL patterns and match to known routes from other services
- [ ] Add `CrossServiceEdge` to the unified schema
- [ ] Add `codegraph trace --cross-service` — follows calls across entry boundaries
- [ ] Add MCP tool: `cross_service_calls` — show inter-service call graph

## Phase 5: Plugin System (future)

- [ ] Support user-provided Python scripts that run post-merge to enrich the graph
- [ ] Default plugins: Pydantic model ↔ route linker, SQLAlchemy model ↔ table linker
