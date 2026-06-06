# codegraph

Multi-language workspace code graph orchestrator.

Auto-discovers services, frontends, gateways, and libraries in a workspace,
orchestrates builds using language-specific tools ([gograph](https://github.com/shvmgyl15/gograph),
[tsgraph](https://github.com/shvmgyl15/tsgraph), [pygraph](https://github.com/shvmgyl15/pygraph)),
merges their graph.json outputs into a unified graph, and exposes a single MCP
server for querying any symbol across any service.

**Install from git source only.** Do not use PyPI or npm — there are unrelated
packages with the same names. All 4 repos must be installed together from
source to stay in sync.

## Quick Start

```bash
# 1. Clone all 4 repos as siblings
git clone https://github.com/shvmgyl15/gograph
git clone https://github.com/shvmgyl15/tsgraph
git clone https://github.com/shvmgyl15/pygraph
git clone https://github.com/shvmgyl15/codegraph

# 2. Run the install script (builds all tools from source)
cd codegraph && ./scripts/install.sh

# 3. Create workspace config
#    (or run from a directory with go.mod/package.json/pyproject.toml subdirectories)
echo '{"version":1,"entries":[{"name":"frontend","path":"./frontend","language":"typescript","type":"frontend"},{"name":"api","path":"./api","language":"python","type":"service"}]}' > ../codegraph.json

# 4. Build the unified graph
codegraph build

# 5. Query across all services
codegraph query "getUser"
codegraph callers "get_user"
codegraph routes
codegraph orphans

# 6. Start MCP server for AI agents
codegraph mcp

# 7. Generate .opencode.json for AI agent integration
codegraph add-opencode-plugin

# 8. Clean up
codegraph clean
```

## Requirements

- Python 3.11+
- Go 1.22+ (for gograph)
- Node.js 20+ (for tsgraph)
- [uv](https://docs.astral.sh/uv/) (Python package manager)

## Install

```bash
# Install all tools from local git source:
./scripts/install.sh

# This builds:
#   gograph  → ~/.local/bin/gograph   (from ../gograph)
#   tsgraph  → ~/.local/bin/tsgraph   (from ../tsgraph)
#   pygraph  → ~/.local/bin/pygraph   (from ../pygraph)
#   codegraph → ~/.local/bin/codegraph (from current dir)
```

The script looks for sibling repos (`../gograph`, `../tsgraph`, `../pygraph`).
It builds each from source and installs binaries to `~/.local/bin/`.

## Uninstall

```bash
./scripts/uninstall.sh
```

Removes all binaries from `~/.local/bin/`, all `.gograph`/`.tsgraph`/`.pygraph`/`.codegraph`
output directories, virtual envs, `node_modules`, caches, and lock files from all 4 repos.

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

When `auto_discover: true`, codegraph probes subdirectories for `go.mod`,
`package.json`, `pyproject.toml`, `Cargo.toml`, `pom.xml` etc.

### The `--root` parameter

`--root` specifies the **workspace root directory** — the same directory where
you ran `codegraph build`. It tells codegraph where to find the `.codegraph/`
output folder. It is NOT a query scope filter.

```bash
# Build in /home/user/myproject
codegraph build --root /home/user/myproject

# Query the same workspace
codegraph context get_user --root /home/user/myproject
```

If you pass the wrong `--root`, codegraph suggests the correct one.

## CLI Commands

| Command | Description |
|---|---|
| `status` | List discovered entries with build status |
| `build` | Build graph for all entries (`--entry` for one) |
| `clean` | Remove `.codegraph/` output directory |
| `query <pattern>` | Search symbols by regex or substring |
| `callers <name>` | Who calls a given symbol |
| `callees <name>` | What a symbol calls |
| `routes` | List all HTTP routes (`--entry`, `--type`) |
| `impact <name>` | BFS downstream blast radius (`--max-depth`) |
| `orphans` | Dead code detection (`--all`, `--exclude-type`) |
| `context <name>` | Full bundle: symbol + callers + callees + tests |
| `trace <message>` | Error flow search with reverse call chain |
| `cross-service` | Cross-service HTTP call edges |
| `add-opencode-plugin` | Generate `.opencode.json` for AI agent config |
| `mcp` | Start MCP stdio server |

## MCP Tools (for AI Agents)

All MCP tool responses include a `duration_ms` field showing how long the query
took. List responses are wrapped in `{"items": [...], "duration_ms": N}`.

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

## Performance

- **Build**: Entries are built in parallel (4 workers). Per-entry timing shown.
- **MCP queries**: The graph is loaded and indexed once, then cached in memory
  for subsequent queries within the same MCP session. Each response includes
  `duration_ms` so you can monitor performance.

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
    # Mutate graph in-place
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

## Troubleshooting

| Problem | Solution |
|---|---|
| `codegraph: command not found` | Run `./scripts/install.sh` — make sure `~/.local/bin` is on PATH |
| `Graph not found at ...` | You passed a wrong `--root`. Run `codegraph build` in your workspace root first, then use the same root for queries. |
| MCP queries are slow | First call loads and indexes the graph (takes a few seconds for large workspaces). Subsequent calls use the in-memory cache and are fast. |
| `pip install codegraph` installs wrong package | codegraph is NOT on PyPI. Use `./scripts/install.sh` from the git repo. |
| `npm install tsgraph` installs wrong package | tsgraph is NOT on npm. Use `./scripts/install.sh` from the git repo. |

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
- WorkspaceQuery is cached in memory across MCP calls

## Related

- [gograph](https://github.com/shvmgyl15/gograph) — Go codebase indexer
- [tsgraph](https://github.com/shvmgyl15/tsgraph) — TypeScript/React/Next.js indexer
- [pygraph](https://github.com/shvmgyl15/pygraph) — Python/Flask codebase indexer
