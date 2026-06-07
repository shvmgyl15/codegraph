from __future__ import annotations

import contextlib
import json
import shutil
from pathlib import Path
from typing import Any


def run(root: str) -> None:
    root_path = Path(root).resolve()
    out_dir = root_path / ".codegraph"

    if not out_dir.exists():
        print("Nothing to clean — .codegraph/ does not exist.")
        return

    # Preserve classification config (LLM-curated customizations)
    class_path = out_dir / "classification.json"
    classifications: dict[str, Any] | None = None
    if class_path.exists():
        with contextlib.suppress(OSError, json.JSONDecodeError):
            classifications = json.loads(class_path.read_text())

    shutil.rmtree(out_dir)

    # Restore classification config
    if classifications:
        out_dir.mkdir(parents=True, exist_ok=True)
        class_path.write_text(json.dumps(classifications, indent=2))

    print(f"Removed {out_dir}")
