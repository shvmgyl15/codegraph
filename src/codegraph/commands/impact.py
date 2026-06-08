from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(
    query: WorkspaceQuery, name: str, max_depth: int | None = None,
    filter_noise: bool = True,
) -> None:
    results = query.get_impact(name, max_depth=max_depth, filter_noise=filter_noise)
    if not results:
        print(f"No impact found for '{name}'")
        return

    print(f"Impact of '{name}' ({len(results)} downstream calls):")
    print()
    header = f"{'Caller':<30} {'Callee':<30} {'Entry':<16} {'File':<40} {'Line'}"
    print(header)
    print("-" * len(header))
    for r in results:
        caller = r.get("caller", "")
        callee = r.get("callee", "")
        entry = r.get("entry_name", "")
        file_path = r.get("file", "")
        line = r.get("line", 0)
        print(f"{caller:<30} {callee:<30} {entry:<16} {file_path:<40} {line}")
