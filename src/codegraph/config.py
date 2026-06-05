from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field, field_validator


class EntryConfig(BaseModel):
    name: str
    path: str
    language: str
    type: str = "library"


class CodegraphConfig(BaseModel):
    version: int = 1
    auto_discover: bool = True
    entries: list[EntryConfig] = Field(default_factory=list)
    plugins: list[str] = Field(default_factory=list)

    @field_validator("version")
    @classmethod
    def _check_version(cls, v: int) -> int:
        if v != 1:
            msg = f"Unsupported config version: {v}. Only version 1 is supported."
            raise ValueError(msg)
        return v


def find_config(root: str) -> Path | None:
    root_path = Path(root).resolve()
    candidates = [
        root_path / "codegraph.jsonc",
        root_path / "codegraph.json",
    ]
    for p in candidates:
        if p.exists():
            return p
    return None


def _strip_jsonc_comments(text: str) -> str:
    lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("//"):
            continue
        if "//" in line:
            in_string = False
            chars: list[str] = []
            i = 0
            while i < len(line):
                c = line[i]
                if c == '"' and (i == 0 or line[i - 1] != "\\"):
                    in_string = not in_string
                if c == "/" and i + 1 < len(line) and line[i + 1] == "/" and not in_string:
                    break
                chars.append(c)
                i += 1
            lines.append("".join(chars))
        else:
            lines.append(line)
    return "\n".join(lines)


def load_config(root: str) -> CodegraphConfig:
    config_path = find_config(root)
    if config_path is None:
        return CodegraphConfig()

    raw = config_path.read_text()
    stripped = _strip_jsonc_comments(raw)
    try:
        data: dict[str, Any] = json.loads(stripped)
    except json.JSONDecodeError as e:
        msg = f"Invalid config file {config_path}: {e}"
        raise ValueError(msg) from e

    return CodegraphConfig(**data)
