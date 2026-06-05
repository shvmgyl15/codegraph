from __future__ import annotations

import json
from pathlib import Path

from codegraph.query import WorkspaceQuery


def run(query: WorkspaceQuery, root: str = ".") -> None:
    root_path = Path(root).resolve()
    config_path = root_path / ".opencode.json"

    config = {
        "$schema": "https://opencode.ai/config.json",
        "mcp_servers": {
            "codegraph": {
                "command": "uv",
                "args": [
                    "run", "codegraph", "mcp", "--root", str(root_path),
                ],
                "env": {},
            },
        },
        "agents": {
            "architect": {
                "model": "opencode-go/deepseek-v4-flash",
                "instructions": [
                    "Use codegraph MCP tools to query the workspace code graph.",
                    "Search symbols, find callers/callees, list routes, "
                    "detect dead code, trace errors, and discover "
                    "cross-service HTTP call edges.",
                ],
            },
        },
    }

    config_path.write_text(json.dumps(config, indent=2))
    print(f"Created {config_path}")
