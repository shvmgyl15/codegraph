from __future__ import annotations

import json
from pathlib import Path

from codegraph.config import find_config, load_config
from codegraph.discover import BUILT_LANGUAGES, UNBUILT_LANGUAGES, resolve_entries


def _load_build_statuses(root_path: Path) -> dict[str, str]:
    manifest_path = root_path / ".codegraph" / "manifest.json"
    if not manifest_path.exists():
        return {}
    try:
        data = json.loads(manifest_path.read_text())
        return {e["name"]: e.get("build_status", "unbuilt") for e in data.get("entries", [])}
    except (OSError, json.JSONDecodeError, ValueError):
        return {}


def run(root: str) -> None:
    root_path = Path(root).resolve()
    config = load_config(root)
    entries = resolve_entries(config, root)
    build_statuses = _load_build_statuses(root_path)

    cfg_path = find_config(root)
    if cfg_path is None and not config.auto_discover:
        print("No codegraph.jsonc found and auto_discover is disabled. Nothing to show.")
        return

    for entry in entries:
        if entry.name in build_statuses:
            entry.build_status = build_statuses[entry.name]

    print(f"Workspace: {root_path}")
    print()

    if cfg_path:
        print(f"Config: {cfg_path}")
    else:
        print("Config: auto-discover (no codegraph.jsonc found)")
    print()

    if not entries:
        print("No entries detected.")
        return

    print(f"{'Name':<20} {'Language':<12} {'Type':<12} {'Build Status':<14} {'Path'}")
    print(f"{'':-<20} {'':-<12} {'':-<12} {'':-<14} {'':-<20}")

    for entry in entries:
        print(
            f"{entry.name:<20} {entry.language:<12} {entry.type:<12} "
            f"{entry.build_status:<14} {entry.path}"
        )

    print()

    built = [e for e in entries if e.language in BUILT_LANGUAGES]
    unbuilt = [e for e in entries if e.language in UNBUILT_LANGUAGES]
    unsupported = [
        e for e in entries
        if e.language not in BUILT_LANGUAGES and e.language not in UNBUILT_LANGUAGES
    ]

    statuses = {e.build_status for e in built}
    has_failed = "failed" in statuses

    print(
        f"Total: {len(entries)} entries "
        f"({len(built)} buildable, {len(unbuilt)} unbuilt-only, "
        f"{len(unsupported)} unknown)"
    )
    if has_failed:
        failed_names = [e.name for e in built if e.build_status == "failed"]
        print(f"Warnings: {len(failed_names)} build(s) failed ({', '.join(failed_names)})")

    # Show plugins
    plugins = list(config.plugins)
    auto_dir = root_path / "codegraph.d" / "plugins"
    if auto_dir.is_dir():
        for pf in sorted(auto_dir.glob("*.py")):
            rel = str(pf.relative_to(root_path))
            if rel not in plugins:
                plugins.append(f"{rel} (auto)")
    if plugins:
        print(f"\nPlugins: {len(plugins)}")
        for pl in plugins:
            print(f"  - {pl}")
