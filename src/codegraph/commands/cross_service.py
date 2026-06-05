from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(
    query: WorkspaceQuery,
    source_entry: str | None = None,
    target_entry: str | None = None,
) -> None:
    edges = query.get_cross_service_edges(
        source_entry=source_entry, target_entry=target_entry,
    )

    if not edges:
        msg = "No cross-service edges found"
        if source_entry:
            msg += f" from '{source_entry}'"
        if target_entry:
            msg += f" to '{target_entry}'"
        print(msg)
        return

    print(f"Cross-service edges ({len(edges)} total):")
    print()
    hdr = (
        f"{'Source Entry':<16} {'Source Symbol':<24} "
        f"{'Method':<8} {'Target Entry':<16} {'Target Route':<40} "
        f"{'Confidence':<10}"
    )
    print(hdr)
    print("-" * len(hdr))
    for e in edges:
        print(
            f"{e.get('source_entry', ''):<16} "
            f"{e.get('source_symbol', ''):<24} "
            f"{e.get('method', ''):<8} "
            f"{e.get('target_entry', ''):<16} "
            f"{e.get('target_route_path', ''):<40} "
            f"{e.get('confidence', ''):<10}"
        )
