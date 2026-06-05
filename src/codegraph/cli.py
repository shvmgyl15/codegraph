from __future__ import annotations

import typer

from codegraph.commands.build import run as run_build
from codegraph.commands.clean import run as run_clean
from codegraph.commands.status import run as run_status

app = typer.Typer()


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
def mcp(
    root: str = typer.Option(".", "--root", help="Workspace root directory"),
) -> None:
    """Start MCP stdio server (Phase 3)"""
    typer.echo("MCP server not yet implemented (Phase 3)")
    raise typer.Exit(1)
