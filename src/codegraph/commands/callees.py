from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, name: str) -> None:
    results = query.get_callees(name)
    if not results:
        print(f"No callees found for '{name}'")
        return

    print(f"Callees of '{name}':")
    print()
    header = f"{'Callee':<30} {'Entry':<16} {'File':<40} {'Line'}"
    print(header)
    print("-" * len(header))
    for callee_sym, edge in results:
        callee_name = callee_sym.get("name", "") if callee_sym else edge.get("callee_raw", "")
        entry = edge.get("entry_name", "")
        file_path = edge.get("file", "")
        line = edge.get("line", 0)
        print(f"{callee_name:<30} {entry:<16} {file_path:<40} {line}")
