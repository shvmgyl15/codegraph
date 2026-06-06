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

- [x] Phase 1: Scaffold + Config + Auto-Discovery
- [x] Phase 2: Merge + Query Engine
- [x] Phase 3: MCP Server
- [x] Phase 4: Cross-Service Edges
- [x] Phase 5: Plugin System + README + OpenCode

## Phase 6: Performance + Install/Uninstall Scripts

### Batch A — Performance fixes

MCP was slow because the full graph was deserialized and indexed on every tool call.
Build was slow because entries were built sequentially with no output.

- [x] A1: Cache WorkspaceQuery in MCP server by root path (loaded once per session)
- [x] A2: Return duration_ms in every MCP tool response
- [x] A3: Parallelize builds with ThreadPoolExecutor (max_workers=4)
- [x] A4: Print per-entry build progress with timing
- [x] A5: Improve `--root` error message (suggest where graph was actually built)

### Batch B — Install/Uninstall scripts (from git source, never PyPI/npm)

- [x] B1: `scripts/install.sh` — clone/build all 4 tools from git source, install to ~/.local/bin
- [x] B2: `scripts/uninstall.sh` — remove all tool binaries, .*graph/ output dirs, venvs, caches

### Batch C — README rewrite

- [x] C1: Replace `pip install` with `git clone + scripts/install.sh`
- [x] C2: Document `--root` clearly (workspace root, not query scope)
- [x] C3: Add troubleshooting section for performance
- [x] C4: Add uninstall instructions
- [x] C5: Run tests + lint, commit, push
