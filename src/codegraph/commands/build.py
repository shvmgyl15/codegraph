from __future__ import annotations

from codegraph.builder import build_and_write


def run(root: str, entry_name: str | None = None) -> None:
    try:
        out_path = build_and_write(root, entry_name=entry_name)
        print(f"Built {out_path}")
    except FileNotFoundError as e:
        print(f"Error: {e}")
    except Exception as e:
        print(f"Build failed: {e}")
