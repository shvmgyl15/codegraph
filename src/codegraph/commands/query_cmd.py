from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, pattern: str) -> None:
    results = query.find_symbols(pattern)
    if not results:
        print(f"No symbols matching '{pattern}'")
        return

    print(f"Symbols matching '{pattern}':")
    print()
    header = f"{'Name':<30} {'Kind':<12} {'Entry':<16} {'Language':<12} {'Type':<12} {'File'}"
    print(header)
    print("-" * len(header))
    for sym in results:
        name = sym.get("name", "")
        kind = sym.get("kind", "")
        entry = sym.get("entry_name", "")
        lang = sym.get("language", "")
        typ = sym.get("type", "")
        file_path = sym.get("file", "")
        print(f"{name:<30} {kind:<12} {entry:<16} {lang:<12} {typ:<12} {file_path}")
    print(f"\n{len(results)} symbol(s) found")
