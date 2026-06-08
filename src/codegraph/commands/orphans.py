from __future__ import annotations

from codegraph.query import WorkspaceQuery


def run(
    query: WorkspaceQuery,
    include_public: bool = False,
    exclude_type: str | None = None,
    filter_noise: bool = True,
) -> None:
    orphans = query.get_orphans(include_public=include_public, filter_noise=filter_noise)
    if exclude_type:
        orphans = [o for o in orphans if o.get("type") != exclude_type]

    if not orphans:
        print("No orphan symbols found")
        return

    print(f"Orphan symbols ({len(orphans)} total):")
    if exclude_type:
        print(f"(excluding type '{exclude_type}')")
    print()
    header = f"{'Name':<30} {'Kind':<12} {'Entry':<16} {'Language':<12} {'Type':<12} {'File'}"
    print(header)
    print("-" * len(header))
    for sym in orphans:
        name = sym.get("name", "")
        kind = sym.get("kind", "")
        entry = sym.get("entry_name", "")
        lang = sym.get("language", "")
        typ = sym.get("type", "")
        file_path = sym.get("file", "")
        print(f"{name:<30} {kind:<12} {entry:<16} {lang:<12} {typ:<12} {file_path}")
