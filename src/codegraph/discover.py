from __future__ import annotations

from pathlib import Path
from typing import Any

from codegraph.config import CodegraphConfig, EntryConfig
from codegraph.graph.types import WorkspaceEntry

BUILT_LANGUAGES = {"go", "python", "typescript"}
UNBUILT_LANGUAGES = {"rust", "java"}


def _detect_language_and_type(dir_path: Path) -> tuple[str, str] | None:
    has_go_mod = (dir_path / "go.mod").exists()
    has_package_json = (dir_path / "package.json").exists()
    has_pyproject = (dir_path / "pyproject.toml").exists()
    has_setup = (dir_path / "setup.py").exists()
    has_requirements = (dir_path / "requirements.txt").exists()
    has_cargo = (dir_path / "Cargo.toml").exists()
    has_pom = (dir_path / "pom.xml").exists()
    has_gradle = (dir_path / "build.gradle").exists()

    if has_go_mod:
        has_main = (dir_path / "main.go").exists() or (dir_path / "cmd").is_dir()
        return ("go", "service" if has_main else "library")

    if has_package_json:
        content = _try_read_json(dir_path / "package.json")
        has_next = False
        if content and isinstance(content, dict):
            deps = {**(content.get("dependencies") or {}), **(content.get("devDependencies") or {})}
            has_next = "next" in deps or any("next" in str(k) for k in deps)
        return ("typescript", "frontend" if has_next else "library")

    if has_pyproject or has_setup or has_requirements:
        return ("python", "library")

    if has_cargo:
        return ("rust", "library")

    if has_pom or has_gradle:
        return ("java", "library")

    return None


def _try_read_json(path: Path) -> Any | None:
    try:
        import json
        return json.loads(path.read_text())
    except (OSError, json.JSONDecodeError, ValueError):
        return None


def _detect_type_override(dir_path: Path, language: str) -> str:
    if language != "python":
        return "library"

    try:
        source_files = list(dir_path.rglob("*.py"))
        content = ""
        for f in source_files[:50]:
            try:
                content += f.read_text(errors="replace") + "\n"
            except OSError:
                continue

        has_flask = "@app.route" in content or "Flask(" in content
        has_fastapi = "@app.get" in content or "@app.post" in content or "FastAPI(" in content
        has_django = "django" in content.lower() and ("urlpatterns" in content or "wsgi" in content)
        has_manage = (dir_path / "manage.py").exists()

        if has_fastapi or has_flask or has_django or has_manage:
            return "service"

        if (dir_path / "wsgi.py").exists() or (dir_path / "asgi.py").exists():
            return "service"
    except (OSError, UnicodeDecodeError):
        pass

    return "library"


def auto_discover(root: str) -> list[WorkspaceEntry]:
    root_path = Path(root).resolve()
    entries: list[WorkspaceEntry] = []
    skip_dirs = {
        ".git", ".codegraph", ".gograph", ".tsgraph", ".pygraph",
        "__pycache__", "node_modules", "venv", ".venv", ".env",
        "target", "build", "dist", ".egg-info",
    }

    try:
        items = sorted(root_path.iterdir())
    except OSError:
        return entries

    for item in items:
        if not item.is_dir():
            continue
        if item.name.startswith("."):
            continue
        if item.name in skip_dirs:
            continue

        detected = _detect_language_and_type(item)
        if detected is None:
            continue

        language, detected_type = detected

        if language == "python" and detected_type == "library":
            detected_type = _detect_type_override(item, language)

        is_built = language in BUILT_LANGUAGES

        entries.append(WorkspaceEntry(
            name=item.name,
            language=language,
            type=detected_type,
            path=str(item.relative_to(root_path)),
            build_status="unbuilt" if is_built else "unsupported",
        ))

    return entries


def resolve_entries(config: CodegraphConfig, root: str) -> list[WorkspaceEntry]:
    if not config.auto_discover and not config.entries:
        return []

    if config.auto_discover:
        discovered = auto_discover(root)
        explicit_map: dict[str, EntryConfig] = {}
        for e in config.entries:
            explicit_map[e.name] = e

        merged: dict[str, WorkspaceEntry] = {}
        for d in discovered:
            merged[d.name] = d

        for name, ec in explicit_map.items():
            if name in merged:
                merged[name].type = ec.type
            else:
                is_built = ec.language in BUILT_LANGUAGES
                merged[name] = WorkspaceEntry(
                    name=ec.name,
                    language=ec.language,
                    type=ec.type,
                    path=ec.path,
                    build_status="unbuilt" if is_built else "unsupported",
                )

        entries = list(merged.values())

    else:
        entries = []
        for ec in config.entries:
            is_built = ec.language in BUILT_LANGUAGES
            entries.append(WorkspaceEntry(
                name=ec.name,
                language=ec.language,
                type=ec.type,
                path=ec.path,
                build_status="unbuilt" if is_built else "unsupported",
            ))

    path_map: dict[str, list[str]] = {}
    for ent in entries:
        path_map.setdefault(ent.path, []).append(ent.name)
    for path, entry_names in path_map.items():
        if len(entry_names) > 1:
            print(f"  Warning: entries {entry_names} share the same path '{path}'")

    return entries
