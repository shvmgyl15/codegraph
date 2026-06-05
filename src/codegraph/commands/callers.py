from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, name: str) -> None:
    results = query.get_callers(name)
    if not results:
        print(f"No callers found for '{name}'")
        return

    print(f"Callers of '{name}':")
    print()
    header = f"{'Caller':<30} {'Entry':<16} {'File':<40} {'Line'}"
    print(header)
    print("-" * len(header))
    for caller_sym, edge in results:
        caller_name = caller_sym.get("name", "")
        entry = caller_sym.get("entry_name", "")
        file_path = caller_sym.get("file", "")
        line = edge.get("line", 0)
        print(f"{caller_name:<30} {entry:<16} {file_path:<40} {line}")
