#!/usr/bin/env bash
set -euo pipefail

# ─────────────────────────────────────────────────────────
# codegraph — Install all 4 tools from local git source
# Looks for sibling repos: ../gograph, ../tsgraph, ../pygraph
# Builds and installs each to ~/.local/bin/
# Never touches PyPI, npm registry, or Go module proxy.
# ─────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CODEGRAPH_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
WORKSPACE_DIR="$(cd "$CODEGRAPH_DIR/.." && pwd)"
BIN_DIR="${HOME}/.local/bin"

mkdir -p "$BIN_DIR"
export PATH="$BIN_DIR:$PATH"

echo "codegraph install — building all tools from source"
echo "  workspace: $WORKSPACE_DIR"
echo "  install to: $BIN_DIR"
echo ""

# ── Detect a tool repo ──────────────────────────────────
find_repo() {
    local name="$1"
    local candidate="$WORKSPACE_DIR/$name"
    if [ -d "$candidate" ]; then
        echo "$candidate"
        return 0
    fi
    return 1
}

# ── Install gograph (Go) ─────────────────────────────────
install_gograph() {
    local repo
    repo=$(find_repo "gograph") || true
    if [ -z "$repo" ]; then
        echo -e "${YELLOW}[gograph] not found — skipping. Set GOPATH or clone to ../gograph${NC}"
        return
    fi
    echo -e "${GREEN}[gograph]${NC} building from $repo"
    (cd "$repo" && go build -o "$BIN_DIR/gograph" ./cmd/gograph)
    echo -e "${GREEN}[gograph]${NC} installed $BIN_DIR/gograph ($(gograph version 2>&1 || true))"
}

# ── Install tsgraph (TypeScript) ─────────────────────────
install_tsgraph() {
    local repo
    repo=$(find_repo "tsgraph") || true
    if [ -z "$repo" ]; then
        echo -e "${YELLOW}[tsgraph] not found — skipping. Clone to ../tsgraph${NC}"
        return
    fi
    echo -e "${GREEN}[tsgraph]${NC} building from $repo"
    (cd "$repo" && npm install --silent && npm run build --silent)
    # Create wrapper script instead of npm link (avoids permissions issues)
    cat > "$BIN_DIR/tsgraph" << WRAPPER
#!/usr/bin/env node
require('$repo/dist/cli/index.js');
WRAPPER
    chmod +x "$BIN_DIR/tsgraph"
    echo -e "${GREEN}[tsgraph]${NC} installed $BIN_DIR/tsgraph"
}

# ── Install pygraph (Python) ─────────────────────────────
install_pygraph() {
    local repo
    repo=$(find_repo "pygraph") || true
    if [ -z "$repo" ]; then
        echo -e "${YELLOW}[pygraph] not found — skipping. Clone to ../pygraph${NC}"
        return
    fi
    echo -e "${GREEN}[pygraph]${NC} installing from $repo"
    (cd "$repo" && uv sync --quiet && uv pip install --quiet -e .)
    local venv_bin
    venv_bin=$(cd "$repo" && uv run which pygraph 2>/dev/null || echo "")
    if [ -n "$venv_bin" ]; then
        ln -sf "$venv_bin" "$BIN_DIR/pygraph"
    fi
    echo -e "${GREEN}[pygraph]${NC} installed $BIN_DIR/pygraph"
}

# ── Install codegraph (Python) ──────────────────────────
install_codegraph() {
    echo -e "${GREEN}[codegraph]${NC} installing from $CODEGRAPH_DIR"
    (cd "$CODEGRAPH_DIR" && uv sync --quiet && uv pip install --quiet -e .)
    local venv_bin
    venv_bin=$(cd "$CODEGRAPH_DIR" && uv run which codegraph 2>/dev/null || echo "")
    if [ -n "$venv_bin" ]; then
        ln -sf "$venv_bin" "$BIN_DIR/codegraph"
    fi
    echo -e "${GREEN}[codegraph]${NC} installed $BIN_DIR/codegraph"
}

# ── Verify tools ─────────────────────────────────────────
verify() {
    echo ""
    echo "── Verification ──"
    for cmd in gograph tsgraph pygraph codegraph; do
        if command -v "$cmd" &>/dev/null; then
            echo -e "  ${GREEN}✓${NC} $cmd found at $(which $cmd)"
        else
            echo -e "  ${RED}✗${NC} $cmd not found on PATH"
        fi
    done
}

# ── Main ─────────────────────────────────────────────────
install_gograph
install_tsgraph
install_pygraph
install_codegraph
verify

echo ""
echo "Done. Run 'codegraph status' to verify the install."
