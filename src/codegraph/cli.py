from __future__ import annotations

from pathlib import Path

import typer

from codegraph.commands.build import run as run_build
from codegraph.commands.callees import run as run_callees
from codegraph.commands.callers import run as run_callers
from codegraph.commands.clean import run as run_clean
from codegraph.commands.context import run as run_context
from codegraph.commands.cross_service import run as run_cross_service
from codegraph.commands.impact import run as run_impact
from codegraph.commands.orphans import run as run_orphans
from codegraph.commands.query_cmd import run as run_query
from codegraph.commands.routes import run as run_routes
from codegraph.commands.status import run as run_status
from codegraph.commands.trace import run as run_trace
from codegraph.graph.serialize import read_graph
from codegraph.query import WorkspaceQuery
from codegraph.server import run_server

app = typer.Typer()


def _load_query(root: str) -> WorkspaceQuery:
    graph_path = Path(root) / ".codegraph" / "workspace.graph.json"
    if not graph_path.exists():
        typer.echo(
            f"Error: no graph found at {graph_path}. Run `codegraph build` first."
        )
        raise typer.Exit(1)
    graph = read_graph(graph_path)
    return WorkspaceQuery(graph, root=root)


@app.command()
def status(
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Detect and display workspace entries"""
    run_status(root)


@app.command()
def build(
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
    entry: str | None = typer.Option(
        None, "--entry", help="Build only a specific entry by name"
    ),
) -> None:
    """Build graph for all (or one) workspace entries"""
    run_build(root, entry)


@app.command()
def clean(
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Remove .codegraph/ output directory"""
    run_clean(root)


@app.command()
def query(
    pattern: str,
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Search symbols by pattern (regex or substring)"""
    q = _load_query(root)
    run_query(q, pattern)


@app.command()
def callers(
    name: str,
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Show who calls the given symbol"""
    q = _load_query(root)
    run_callers(q, name)


@app.command()
def callees(
    name: str,
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Show what the given symbol calls"""
    q = _load_query(root)
    run_callees(q, name)


@app.command()
def routes(
    entry: str | None = typer.Option(
        None, "--entry", help="Filter by entry name"
    ),
    type: str | None = typer.Option(
        None, "--type", help="Filter by entry type (service, frontend, etc.)"
    ),
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """List all HTTP routes across the workspace"""
    q = _load_query(root)
    run_routes(q, entry_filter=entry, type_filter=type)


@app.command()
def impact(
    name: str,
    max_depth: int | None = typer.Option(
        None, "--max-depth", "-d", help="Maximum depth for BFS traversal"
    ),
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Show downstream impact (BFS from symbol)"""
    q = _load_query(root)
    run_impact(q, name, max_depth=max_depth)


@app.command()
def orphans(
    all: bool = typer.Option(
        False, "--all", help="Include public uncalled symbols"
    ),
    exclude_type: str | None = typer.Option(
        None, "--exclude-type", help="Exclude entries of a given type"
    ),
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """List unreachable symbols (dead code)"""
    q = _load_query(root)
    run_orphans(q, include_public=all, exclude_type=exclude_type)


@app.command()
def context(
    name: str,
    source: bool = typer.Option(
        False, "--source", help="Include full source code"
    ),
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Show symbol with callers, callees, tests"""
    q = _load_query(root)
    run_context(q, name, show_source=source)


@app.command()
def trace(
    message: str,
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Find error messages and trace their call paths"""
    q = _load_query(root)
    run_trace(q, message)


@app.command(name="cross-service")
def cross_service(
    source_entry: str | None = typer.Option(
        None, "--source-entry", "-s", help="Filter by source entry name"
    ),
    target_entry: str | None = typer.Option(
        None, "--target-entry", "-t", help="Filter by target entry name"
    ),
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Show cross-service HTTP call edges"""
    q = _load_query(root)
    run_cross_service(q, source_entry=source_entry, target_entry=target_entry)


@app.command()
def mcp(
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Start MCP stdio server for AI agent integration"""
    run_server(root)
