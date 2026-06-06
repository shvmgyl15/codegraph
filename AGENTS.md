# codegraph — Project DNA

## Vision
A thin orchestration layer that sits at the root of a multi-language, multi-repository
workspace (monorepo or submodule-based). It auto-discovers every service, frontend,
gateway, and library, orchestrates builds using language-specific tools (gograph,
tsgraph, pygraph), merges all graph.json outputs into a single unified graph, and
exposes one MCP server for querying any symbol across any service.

## Design Philosophy (Orchestrator, not a parser)
codegraph is not an indexer — it orchestrates indexers. Key design points:
- **Language-agnostic** — no language is special. Every entry is equal in the schema.
- **Resilient** — one failed entry build doesn't block others. Partial results are useful.
- **Clean state** — single `.codegraph/` output directory. `codegraph clean` removes everything.
- **User-enriched** — auto-detection is best-effort; override via `codegraph.jsonc`.
- **Type classification** — entries get a `type` field (service, frontend, gateway, library,
  proto, etc.) detected by heuristics and overridable by the user. Used as a query filter only.
- **Unbuilt languages** — Rust, Java, and other languages are detected and listed but not
  indexed (no graph tool yet). The user sees them in `status` output.

### Boundaries
- **gograph/tsgraph/pygraph**: Own all per-language extraction (symbols, calls, routes,
  HTTP client calls, errors, env reads, test edges). One tool per language.
- **codegraph**: Owns workspace orchestration, cross-service analysis, and unified MCP.
  Does NOT duplicate per-language extraction that belongs in gograph/tsgraph/pygraph.
- If a capability is language-specific, it belongs in the per-language tool first.
  codegraph only combines, correlates, and queries outputs from those tools.

## Tech Stack
- Runtime: Python 3.11+
- Package manager: `uv`
- CLI: `typer`
- MCP: `mcp` Python SDK
- Config parsing: `pydantic` for schema validation
- File scanning: `pathspec` for gitignore support
- Testing: `pytest` + `pytest-cov`
- Linting: `ruff`
- Type checking: `mypy` (strict mode)

## Installation (for AI Agents)

Install all tools:

```bash
# Python tools
pip install workspace-graph pygraph-mcp

# TypeScript tool
npm install -g @shvmgyl15/tsgraph

# Go tool
git clone https://github.com/shvmgyl15/gograph
cd gograph && go build -o ~/.local/bin/gograph ./cmd/gograph

# Verify
codegraph status
```

Or install everything from git source in one step:

```bash
git clone https://github.com/shvmgyl15/codegraph
cd codegraph && ./scripts/install.sh
```

## Agent Rules

### Task Management
- READ TODOS.md at session start to know what's done and what's next
- UPDATE TODOS.md when you start/finish a task (`[.]` in-progress, `[x]` done)
- Work in phase order unless a task has no blockers
- After a phase completes (all items `[x]`), run `git init` if not yet done,
  then commit and push: `git add -A && git commit -m "phase N: <title>" && git push origin main`

### Orchestration
- This is a single-orchestrator project. When a task has multiple independent
  sub-tasks, delegate via the `task` tool (`subagent_type: general`) rather
  than doing them sequentially.
- For each delegated sub-task, specify:
  1. Exact files the sub-agent may modify
  2. Which phase from TODOS.md it belongs to
  3. What to return (never let sub-agents commit or merge)
- After all sub-tasks complete, run `uv run pytest && uv run mypy src && uv run ruff check`
  and fix any issues directly. Do NOT re-delegate broken builds.

### Quality
- Run `uv run pytest`, `uv run mypy src`, and `uv run ruff check` after every task completion
- Fix all failures before marking `[x]`
- If the project is already broken when you start, note it in TODOS.md and fix it first

### Research
- Use webfetch when unsure about an API — check Python `ast` docs, typer docs, mcp SDK docs
- Reference gograph, tsgraph, pygraph source for their graph.json output formats
- DO NOT guess API signatures

### Code Style
- No comments in source files unless logic is non-obvious
- Type annotations everywhere, avoid `Any`
- Follow patterns from adjacent files in the codebase
- No emojis in source code or commit messages
- Follow PEP 8 conventions (enforced by ruff)

### Communication
- Be concise. Use TODOS.md for status, respond with only what's needed.
- If stuck, explain the blocker clearly rather than overthinking.
