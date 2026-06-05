from __future__ import annotations

import shutil
from pathlib import Path


def run(root: str) -> None:
    root_path = Path(root).resolve()
    out_dir = root_path / ".codegraph"

    if not out_dir.exists():
        print("Nothing to clean — .codegraph/ does not exist.")
        return

    shutil.rmtree(out_dir)
    print(f"Removed {out_dir}")
