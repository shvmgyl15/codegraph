# codegraph

Multi-language workspace code graph orchestrator.

Auto-discovers services, frontends, gateways, and libraries in a workspace,
orchestrates builds using language-specific tools ([gograph](https://github.com/shvmgyl15/gograph),
[tsgraph](https://github.com/shvmgyl15/tsgraph), [pygraph](https://github.com/shvmgyl15/pygraph)),
merges their graph.json outputs into a unified graph, and exposes a single MCP
server for querying any symbol across any service.

## Quick Start

```bash
# 1. Create workspace config
echo '{"version":1,"entries":[{"name":"frontend","path":"./frontend","language":"typescript","type":"frontend"},{"name":"api","path":"./api","language":"python","type":"service"}]}' > codegraph.json

# 2. Build the unified graph
codegraph build

# 3. Query across all services
codegraph query "getUser"
codegraph callers "get_user"
codegraph routes
codegraph orphans

# 4. Start MCP server for AI agents
codegraph mcp

# 5. Clean up
codegraph clean
```

## Installation

```bash
pip install codegraph
```

Requires Python 3.11+ and the per-language tools installed:
- `gograph` for Go projects
- `tsgraph` for TypeScript/Next.js projects
- `pygraph` for Python/Flask projects

## Configuration

Create `codegraph.jsonc` or `codegraph.json` at your workspace root:

```jsonc
{
  "version": 1,
  "auto_discover": true,
  "entries": [
    { "name": "frontend",     "path": "./frontend",    "language": "typescript", "type": "frontend" },
    { "name": "api-gateway",  "path": "./api-gateway", "language": "python",     "type": "gateway" },
    { "name": "user-svc",     "path": "./user-svc",    "language": "go",         "type": "service" },
    { "name": "py-common",    "path": "./libs/py-common", "language": "python",  "type": "library" }
  ],
  "plugins": ["./scripts/custom_enrichment.py"]
}
```

`auto_discover: true` probes for `go.mod`, `package.json`, `pyproject.toml`,
`Cargo.toml`, `pom.xml` etc. in subdirectories.

## CLI Commands

| Command | Description |
|---|---|
| `status` | List discovered entries with build status |
| `build` | Build graph for all or one entry (`--entry`) |
| `clean` | Remove `.codegraph/` output directory |
| `query <pattern>` | Search symbols by regex or substring |
| `callers <name>` | Who calls a given symbol |
| `callees <name>` | What a symbol calls |
| `routes` | List all HTTP routes (`--entry`, `--type` filters) |
| `impact <name>` | BFS downstream blast radius (`--max-depth`) |
| `orphans` | Dead code detection (`--all`, `--exclude-type`) |
| `context <name>` | Full bundle: symbol + callers + callees + tests |
| `trace <message>` | Error flow search with reverse call chain |
| `cross-service` | Cross-service HTTP call edges (`--source-entry`, `--target-entry`) |
| `add-opencode-plugin` | Generate `.opencode.json` for AI agent integration |
| `mcp` | Start MCP stdio server |

## MCP Tools (for AI Agents)

| Tool | Description |
|---|---|
| `entry_status` | List entries with language, type, build status |
| `query_symbols` | Search symbols across all entries |
| `callers` / `callees` | Who calls / what a symbol calls |
| `context` | Symbol + callers + callees + tests |
| `routes` | HTTP routes with entry/type filters |
| `impact` | Blast radius with max depth |
| `orphans` | Dead code with include-public and exclude-type |
| `trace` | Error message search with backtrace |
| `cross_service_calls` | Cross-service HTTP call edges |
| `add_opencode_plugin` | Generate AI agent config |

## Plugin System

User-provided Python scripts that run post-merge to enrich the graph. Configured
in `codegraph.jsonc`:

```jsonc
{ "plugins": ["./scripts/enrich.py"] }
```

Plugin script interface:

```python
from codegraph.graph.types import UnifiedGraph

def run(graph: UnifiedGraph) -> None:
    graph.cross_service_edges.append({
        "source_entry": "frontend",
        "source_file": "src/api.ts",
        "source_line": 10,
        "source_symbol": "loadUsers",
        "method": "GET",
        "url_pattern": "/api/users",
        "target_entry": "api",
        "target_route_path": "/api/users",
        "target_route_handler": "get_users",
        "confidence": "high",
    })
```

Plugins run after all standard extraction. Failures are isolated — one failing
plugin doesn't block others.

## Architecture

```
codegraph (orchestrator)
  ├── gograph  ─── indexes Go codebases
  ├── tsgraph  ─── indexes TypeScript/Next.js codebases
  └── pygraph  ─── indexes Python/Flask codebases

Output: .codegraph/workspace.graph.json  (merged)
        .codegraph/manifest.json          (entry metadata)
```

- Each per-language tool produces its own `graph.json`
- codegraph merges them, stamps entries with metadata
- Cross-service edges are detected via URL → route matching
- Plugins can enrich the graph post-merge
- Single MCP server exposes all query tools

## Related

- [gograph](https://github.com/shvmgyl15/gograph) — Go codebase indexer
- [tsgraph](https://github.com/shvmgyl15/tsgraph) — TypeScript/React/Next.js indexer
- [pygraph](https://github.com/shvmgyl15/pygraph) — Python/Flask codebase indexer
