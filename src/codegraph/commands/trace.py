from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, message: str) -> None:
    results = query.get_trace(message)
    if not results:
        print(f"No error messages matching '{message}'")
        return

    print(f"Error flow for '{message}':")
    print()
    for r in results:
        entry = r.get("entry_name", "")
        print(f"  {r.get('function', '')} — {r.get('file', '')}:{r.get('line', '')} [{entry}]")
        print(f"    Message: {r.get('message', '')}")
        print()
    print(f"{len(results)} error(s) found")
