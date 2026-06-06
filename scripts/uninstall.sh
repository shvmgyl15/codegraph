#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# codegraph — Uninstall all 4 tools
# Removes binaries, output directories, virtual envs,
# and cached files from all sibling repos.
# ─────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEGRAPH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_DIR="$(cd "$CODEGRAPH_DIR/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"

echo "codegraph uninstall"
echo ""

clean_repo() {
    local name="$1"
    local dir="$WORKSPACE_DIR/$name"
    if [ ! -d "$dir" ]; then
        return
    fi
    echo -e "${YELLOW}[$name]${NC} found at $dir"

    # Remove tool-specific output directories
    for outdir in ".gograph" ".tsgraph" ".pygraph" ".codegraph" ".venv" "venv" "node_modules" "dist" "__pycache__" ".pytest_cache" ".mypy_cache" ".ruff_cache"; do
        target="$dir/$outdir"
        if [ -e "$target" ]; then
            rm -rf "$target"
            echo "  removed $target"
        fi
    done

    # Remove uv.lock / package-lock.json caches
    for lock in "$dir/uv.lock" "$dir/package-lock.json"; do
        if [ -f "$lock" ]; then
            rm -f "$lock"
            echo "  removed $lock"
        fi
    done
}

# Remove binaries
echo "── Removing binaries from $BIN_DIR ──"
for bin in gograph tsgraph pygraph codegraph; do
    target="$BIN_DIR/$bin"
    if [ -f "$target" ] || [ -L "$target" ]; then
        rm -f "$target"
        echo -e "${GREEN}  removed${NC} $target"
    fi
done

# Remove per-repo caches and build artifacts
echo ""
echo "── Cleaning repo artifacts ──"
clean_repo "gograph"
clean_repo "tsgraph"
clean_repo "pygraph"
clean_repo "codegraph"

# Clean workspace-level .codegraph output (if any)
if [ -d "$WORKSPACE_DIR/.codegraph" ]; then
    rm -rf "$WORKSPACE_DIR/.codegraph"
    echo -e "${GREEN}  removed${NC} $WORKSPACE_DIR/.codegraph"
fi

echo ""
echo "Done. All codegraph-related binaries, caches, and build artifacts removed."
