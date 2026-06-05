from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, name: str, show_source: bool = False) -> None:
    ctx = query.get_context(name, include_source=show_source)
    symbol = ctx.get("symbol")

    if not symbol:
        print(f"Symbol '{name}' not found")
        return

    print(f"Symbol: {symbol.get('name', '')}")
    print(f"  Kind:      {symbol.get('kind', '')}")
    print(f"  Entry:     {symbol.get('entry_name', '')}")
    print(f"  Language:  {symbol.get('language', '')}")
    print(f"  Type:      {symbol.get('type', '')}")
    print(f"  File:      {symbol.get('file', '')}")
    print(f"  Line:      {symbol.get('line', 0)}")
    print(f"  Exported:  {symbol.get('is_exported', False)}")
    print()

    callers = ctx.get("callers", [])
    print(f"Callers ({len(callers)}):")
    if callers:
        for c in callers[:10]:
            entry = c.get("entry_name", "")
            print(f"  {c.get('caller', '')} — {c.get('file', '')}:{c.get('line', '')} [{entry}]")
    print()

    callees = ctx.get("callees", [])
    print(f"Callees ({len(callees)}):")
    if callees:
        for c in callees[:10]:
            entry = c.get("entry_name", "")
            print(f"  {c.get('callee', '')} — {c.get('file', '')}:{c.get('line', '')} [{entry}]")
    print()

    tests = ctx.get("tests", [])
    print(f"Tests ({len(tests)}):")
    if tests:
        for t in tests[:10]:
            entry = t.get("entry_name", "")
            print(f"  {t.get('test_func', '')} — {t.get('file', '')}:{t.get('line', '')} [{entry}]")

    source = ctx.get("source")
    if source:
        print()
        print("Source:")
        print(source)
