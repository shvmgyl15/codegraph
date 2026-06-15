from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(
    query: WorkspaceQuery,
    entry_filter: str | None = None,
    type_filter: str | None = None,
    source: str | None = None,
) -> None:
    routes = query.get_routes()
    if entry_filter:
        routes = [r for r in routes if r.get("entry_name") == entry_filter]
    if type_filter:
        routes = [r for r in routes if r.get("type") == type_filter]
    if source:
        routes = [r for r in routes if r.get("source") == source]

    if not routes:
        msg = "No routes found"
        if entry_filter:
            msg += f" for entry '{entry_filter}'"
        if type_filter:
            msg += f" of type '{type_filter}'"
        if source:
            msg += f" with source '{source}'"
        print(msg)
        return

    print(f"Routes ({len(routes)} total):")
    print()
    hdr = (
        f"{'Method':<8} {'Path':<50} {'Handler':<30} "
        f"{'Entry':<16} {'Language':<12} {'Type':<12} {'Source':<8} {'File'}"
    )
    print(hdr)
    print("-" * len(hdr))
    for r in routes:
        method = r.get("method", "")
        path = r.get("path", "")
        handler = r.get("handler", "")
        entry = r.get("entry_name", "")
        lang = r.get("language", "")
        typ = r.get("type", "")
        src = r.get("source", "")
        file_path = r.get("file", "")
        print(f"{method:<8} {path:<50} {handler:<30} {entry:<16} {lang:<12} {typ:<12} {src:<8} {file_path}")
