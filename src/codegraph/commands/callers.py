from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, name: str) -> None:
    result = query.get_callers(name)
    items = result.get("items", [])
    if not items:
        print(f"No callers found for '{name}'")
        return

    print(f"Callers of '{name}':")
    print()
    header = f"{'Caller':<30} {'Entry':<16} {'File':<40} {'Line'}"
    print(header)
    print("-" * len(header))
    for item in items:
        caller_name = item.get("caller", "")
        entry = item.get("entry_name", "")
        file_path = item.get("file", "")
        line = item.get("line", 0)
        print(f"{caller_name:<30} {entry:<16} {file_path:<40} {line}")
