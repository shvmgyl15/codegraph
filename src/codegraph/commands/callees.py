from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, name: str) -> None:
    result = query.get_callees(name)
    items = result.get("items", [])
    if not items:
        print(f"No callees found for '{name}'")
        return

    print(f"Callees of '{name}':")
    print()
    header = f"{'Callee':<30} {'Entry':<16} {'File':<40} {'Line'}"
    print(header)
    print("-" * len(header))
    for item in items:
        callee_name = item.get("callee", "")
        entry = item.get("entry_name", "")
        file_path = item.get("file", "")
        line = item.get("line", 0)
        print(f"{callee_name:<30} {entry:<16} {file_path:<40} {line}")
