from __future__ import annotations

import shutil
from pathlib import Path

from codegraph.builder import _clear_per_language_caches
from codegraph.config import load_config
from codegraph.discover import resolve_entries


def run(root: str) -> None:
    root_path = Path(root).resolve()

    # Clean per-language caches (graph.json, build cache)
    config = load_config(root)
    entries = resolve_entries(config, root)
    _clear_per_language_caches(entries, root_path)

    # Clean unified output
    out_dir = root_path / ".codegraph"
    if out_dir.exists():
        shutil.rmtree(out_dir)
        print(f"Removed {out_dir}")
    else:
        print("Nothing to clean — .codegraph/ does not exist.")
