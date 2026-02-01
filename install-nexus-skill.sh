#!/bin/bash
# ═══════════════════════════════════════════════════════════════════════════════
# Nexus CLI Interactive Installation Wizard (v4.0.4)
# ═══════════════════════════════════════════════════════════════════════════════
#
# This script provides an interactive wizard to:
# - Install Nexus CLI skill for Claude Code
# - Generate customized .nexus-config.yaml configuration
# - Configure quality gates, executors, and preferences
# - Auto-detect and install missing dependencies
#
# Usage:
#   ./install-nexus-skill.sh [options]
#
# Options:
#   --quick          Skip interactive configuration, use defaults
#   --config-only    Only generate config file, skip installation
#   --check-deps     Only check and install missing dependencies
#   --help           Show this help message
#
# Dependencies (auto-detected and installable):
#   - Node.js 20+ & npm (required for Gemini/Codex CLIs)
#   - Python 3 & uv/uvx (required for PAL MCP Server)
#   - jq               (recommended - JSON processor, for auto-config)
#   - PAL MCP Server   (required for Gemini/Codex via clink; optional otherwise)
#   - Gemini CLI       (optional - for Gemini executor)
#   - Codex CLI        (optional - for Codex executor)
#
# ═══════════════════════════════════════════════════════════════════════════════

set -e

# ─────────────────────────────────────────────────────────────────────────────
# Colors and Styling
# ─────────────────────────────────────────────────────────────────────────────

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
MAGENTA='\033[0;35m'
BOLD='\033[1m'
DIM='\033[2m'
NC='\033[0m'

# ─────────────────────────────────────────────────────────────────────────────
# Configuration Variables
# ─────────────────────────────────────────────────────────────────────────────

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMANDS_DIR="$HOME/.claude/commands"
CONFIG_OUTPUT=""

# OpenCode support
OPENCODE_SKILLS_DIR="$HOME/.config/opencode/skills/nexus-cli"
CLAUDE_SKILLS_DIR="$HOME/.claude/skills/nexus-cli"
INSTALL_TARGET="auto"  # auto, claude, opencode, both

# Read version
if [ -f "$PROJECT_DIR/VERSION" ]; then
    VERSION=$(cat "$PROJECT_DIR/VERSION" | tr -d '\n')
else
    VERSION="4.0.3"
fi

# Default configuration values
CFG_LANGUAGE="auto"
CFG_SPEC_DIR=".nexus-temp/specs"
CFG_CHECKPOINT_DIR=".nexus-temp/checkpoints"
CFG_DEFAULT_EXECUTOR="claude"
CFG_MAX_PARALLEL=5
CFG_TASK_TIMEOUT=10
CFG_BATCH_TIMEOUT=30
CFG_ERROR_STRATEGY="ask"
CFG_MAX_RETRIES=3

CFG_CLAUDE_ENABLED="true"
CFG_GEMINI_ENABLED="true"
CFG_CODEX_ENABLED="true"

CFG_QG_ENABLED="true"
CFG_QG_POLICY="on_complete"
CFG_QG_ASK_BEFORE="true"
CFG_QG_BUILD="true"
CFG_QG_BUILD_REQUIRED="true"
CFG_QG_LINT="true"
CFG_QG_LINT_REQUIRED="false"
CFG_QG_TYPECHECK="true"
CFG_QG_TYPECHECK_REQUIRED="true"
CFG_QG_TEST="false"
CFG_QG_TEST_REQUIRED="false"
CFG_QG_REVIEW="true"
CFG_QG_REVIEW_REQUIRED="false"

CFG_LOG_ENABLED="true"
CFG_LOG_LEVEL="info"
CFG_LOG_TO_FILE="true"

CFG_SKIP_CODE_REVIEW="false"
CFG_SKIP_DOCUMENTATION="false"
CFG_AUTO_CHECKPOINT="true"

# Command line options
QUICK_MODE=false
CONFIG_ONLY=false

# ─────────────────────────────────────────────────────────────────────────────
# Helper Functions
# ─────────────────────────────────────────────────────────────────────────────

ok() { echo -e "${GREEN}✓${NC} $1"; }
err() { echo -e "${RED}✗${NC} $1"; exit 1; }
warn() { echo -e "${YELLOW}⚠${NC} $1"; }
info() { echo -e "${BLUE}ℹ${NC} $1"; }
step() { echo -e "\n${CYAN}▸${NC} ${BOLD}$1${NC}"; }

# ─────────────────────────────────────────────────────────────────────────────
# Dependency Detection and Installation Functions
# ─────────────────────────────────────────────────────────────────────────────

# Track missing dependencies
MISSING_DEPS=()

# Check if a command exists
command_exists() {
    command -v "$1" >/dev/null 2>&1
}

# Check PAL MCP configuration
check_pal_mcp() {
    if [ -f "$HOME/.claude.json" ]; then
        if grep -q '"pal"' "$HOME/.claude.json" 2>/dev/null; then
            return 0
        fi
    fi
    return 1
}

# Check Gemini CLI
check_gemini() {
    command_exists gemini
}

# Check Codex CLI
check_codex() {
    command_exists codex
}

check_opencode() {
    command_exists opencode
}

check_claude_code() {
    [ -d "$HOME/.claude" ]
}

detect_install_target() {
    local has_claude=false
    local has_opencode=false
    
    check_claude_code && has_claude=true
    check_opencode && has_opencode=true
    
    if [ "$has_claude" = true ] && [ "$has_opencode" = true ]; then
        echo "both"
    elif [ "$has_opencode" = true ]; then
        echo "opencode"
    elif [ "$has_claude" = true ]; then
        echo "claude"
    else
        echo "none"
    fi
}

check_ralph() {
    command_exists ralph
}

# Check Python
check_python() {
    command_exists python3 || command_exists python
}

# Check uv (Python package manager)
check_uv() {
    command_exists uv
}

# Check npm
check_npm() {
    command_exists npm
}

# Check Node.js
check_node() {
    command_exists node
}

# Check curl
check_curl() {
    command_exists curl
}

# Check git
check_git() {
    command_exists git
}

# Check uvx (comes with uv)
check_uvx() {
    command_exists uvx
}

# Install PAL MCP Server
install_pal_mcp() {
    echo -e "\n${BOLD}Installing PAL MCP Server...${NC}"

    if ! check_uv; then
        warn "uv (uvx) not found. Please install uv first."
        echo -e "  ${DIM}brew install uv${NC}  (macOS)"
        echo -e "  ${DIM}curl -LsSf https://astral.sh/uv/install.sh | sh${NC}  (macOS/Linux)"
        return 1
    fi

    # Check if ~/.claude.json exists
    if [ ! -f "$HOME/.claude.json" ]; then
        info "Creating ~/.claude.json"
        echo '{"mcpServers":{}}' > "$HOME/.claude.json"
        ok "Created ~/.claude.json"
    fi

    # Add PAL MCP configuration
    if command_exists jq; then
        # Use jq if available for proper JSON manipulation
        info "Configuring PAL MCP Server in ~/.claude.json"
        local temp_file=$(mktemp)
        jq '.mcpServers.pal = {
            "command": "bash",
            "args": ["-c", "for p in $(which uvx 2>/dev/null) $HOME/.local/bin/uvx $HOME/.cargo/bin/uvx /opt/homebrew/bin/uvx /usr/local/bin/uvx uvx; do [ -x \"$p\" ] && exec \"$p\" --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server; done; echo '\''uvx not found'\'' >&2; exit 1"]
        }' "$HOME/.claude.json" > "$temp_file" && mv "$temp_file" "$HOME/.claude.json"
        ok "PAL MCP configured successfully in ~/.claude.json"
    else
        # Manual approach if jq not available
        warn "jq not found. Please manually add PAL MCP to ~/.claude.json:"
        echo -e "${DIM}"
        echo '  "pal": {'
        echo '    "command": "bash",'
        echo '    "args": ["-c", "for p in $(which uvx 2>/dev/null) $HOME/.local/bin/uvx $HOME/.cargo/bin/uvx /opt/homebrew/bin/uvx /usr/local/bin/uvx uvx; do [ -x \\"$p\\" ] && exec \\"$p\\" --from git+https://github.com/BeehiveInnovations/pal-mcp-server.git pal-mcp-server; done; echo \\"uvx not found\\" >&2; exit 1"]'
        echo '  }'
        echo -e "${NC}"
        return 1
    fi
    return 0
}

# Install Gemini CLI
install_gemini() {
    echo -e "\n${BOLD}Installing Gemini CLI...${NC}"

    if ! check_node; then
        warn "Node.js not found. Gemini CLI requires Node.js 20+."
        echo -e "  ${DIM}brew install node${NC}  (macOS)"
        echo -e "  ${DIM}sudo apt install nodejs npm${NC}  (Ubuntu/Debian)"
        return 1
    fi

    if ! check_npm; then
        warn "npm not found. Please install Node.js first."
        return 1
    fi

    local node_ver node_major
    node_ver=$(node --version 2>/dev/null | sed 's/^v//')
    node_major=${node_ver%%.*}
    if [[ "$node_major" =~ ^[0-9]+$ ]] && [ "$node_major" -lt 20 ]; then
        warn "Node.js v${node_ver} detected. Gemini CLI requires Node.js 20+."
        echo -e "  ${DIM}Upgrade Node.js and re-run this step:${NC}"
        echo -e "  ${DIM}  brew install node${NC}  (macOS)"
        echo -e "  ${DIM}  nvm install 20 && nvm use 20${NC}  (if using nvm)"
        return 1
    fi

    info "Running: npm install -g @google/gemini-cli@latest"
    npm install -g @google/gemini-cli@latest 2>/dev/null || npm install -g @google/gemini-cli 2>/dev/null || true

    # Ensure npm global bin is on PATH for this script session
    local npm_bin
    npm_bin=$(npm bin -g 2>/dev/null || true)
    [ -n "$npm_bin" ] && export PATH="$npm_bin:$PATH"
    if check_gemini; then
        ok "Gemini CLI installed successfully via npm"
        return 0
    else
        warn "Could not install Gemini CLI automatically"
        echo -e "  ${DIM}Manual installation:${NC}"
        echo -e "  ${DIM}  npm install -g @google/gemini-cli@latest${NC}"
        echo -e "  ${DIM}  brew install gemini-cli${NC}  (macOS/Linux, if Homebrew installed)"
        echo -e "  ${DIM}  npx https://github.com/google-gemini/gemini-cli${NC}  (run without install)"
        return 1
    fi
}

# Install Codex CLI
install_codex() {
    echo -e "\n${BOLD}Installing Codex CLI...${NC}"

    if check_npm; then
        info "Running: npm install -g @openai/codex"
        npm install -g @openai/codex 2>/dev/null || true

        # Ensure npm global bin is on PATH for this script session
        local npm_bin
        npm_bin=$(npm bin -g 2>/dev/null || true)
        [ -n "$npm_bin" ] && export PATH="$npm_bin:$PATH"

        if check_codex; then
            ok "Codex CLI installed successfully via npm"
            return 0
        fi
    fi

    if [[ "$OSTYPE" == "darwin"* ]] && command_exists brew; then
        brew install --cask codex 2>/dev/null || true
        if check_codex; then
            ok "Codex CLI installed via Homebrew"
            return 0
        fi
    fi

    warn "Could not install Codex CLI automatically"
    echo -e "  ${DIM}Manual installation:${NC}"
    echo -e "  ${DIM}  npm install -g @openai/codex${NC}"
    echo -e "  ${DIM}  brew install --cask codex${NC}  (macOS)"
    return 1
}

install_ralph() {
    echo -e "\n${BOLD}Installing Ralph Orchestrator...${NC}"

    if check_npm; then
        info "Running: npm install -g @ralph-orchestrator/ralph-cli"
        npm install -g @ralph-orchestrator/ralph-cli 2>/dev/null || true

        local npm_bin
        npm_bin=$(npm bin -g 2>/dev/null || true)
        [ -n "$npm_bin" ] && export PATH="$npm_bin:$PATH"

        if check_ralph; then
            ok "Ralph Orchestrator installed successfully via npm"
            return 0
        fi
    fi

    if command_exists cargo; then
        info "Running: cargo install ralph-cli"
        cargo install ralph-cli 2>/dev/null || true
        export PATH="$HOME/.cargo/bin:$PATH"

        if check_ralph; then
            ok "Ralph Orchestrator installed successfully via cargo"
            return 0
        fi
    fi

    warn "Could not install Ralph Orchestrator automatically"
    echo -e "  ${DIM}Manual installation:${NC}"
    echo -e "  ${DIM}  npm install -g @ralph-orchestrator/ralph-cli${NC}"
    echo -e "  ${DIM}  cargo install ralph-cli${NC}"
    return 1
}

# Install uv
install_uv() {
    echo -e "\n${BOLD}Installing uv (Python package manager)...${NC}"

    local install_method=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS
        if command_exists brew; then
            info "Running: brew install uv"
            brew install uv
            install_method="brew"
        else
            info "Running: curl -LsSf https://astral.sh/uv/install.sh | sh"
            curl -LsSf https://astral.sh/uv/install.sh | sh
            install_method="install script"
        fi
    else
        # Linux
        info "Running: curl -LsSf https://astral.sh/uv/install.sh | sh"
        curl -LsSf https://astral.sh/uv/install.sh | sh
        install_method="install script"
    fi

    # Source the updated PATH
    export PATH="$HOME/.cargo/bin:$HOME/.local/bin:$PATH"

    if check_uv; then
        ok "uv installed successfully via $install_method"
        return 0
    else
        warn "Could not install uv automatically"
        echo -e "  ${DIM}Manual installation: curl -LsSf https://astral.sh/uv/install.sh | sh${NC}"
        return 1
    fi
}

# Install jq (for JSON manipulation)
install_jq() {
    echo -e "\n${BOLD}Installing jq (JSON processor)...${NC}"

    local install_method=""

    if [[ "$OSTYPE" == "darwin"* ]]; then
        if command_exists brew; then
            info "Running: brew install jq"
            brew install jq
            install_method="brew"
        fi
    else
        if command_exists apt-get; then
            info "Running: sudo apt-get install -y jq"
            sudo apt-get install -y jq
            install_method="apt-get"
        elif command_exists yum; then
            info "Running: sudo yum install -y jq"
            sudo yum install -y jq
            install_method="yum"
        fi
    fi

    if command_exists jq; then
        if [ -n "$install_method" ]; then
            ok "jq installed successfully via $install_method"
        else
            ok "jq is already installed"
        fi
        return 0
    else
        warn "Could not install jq automatically"
        return 1
    fi
}

# Run all dependency checks
run_dependency_checks() {
    MISSING_DEPS=()

    echo -e "\n${BOLD}Checking Dependencies${NC}"
    echo ""

    # Basic tools (always required)
    echo -e "${BOLD}Basic Tools${NC}"
    echo ""

    if check_curl; then
        ok "curl: Available"
    else
        warn "curl: Not found (required for downloads)"
        MISSING_DEPS+=("curl")
    fi

    if check_git; then
        ok "git: $(git --version 2>/dev/null | head -1)"
    else
        warn "git: Not found (required for PAL MCP)"
        MISSING_DEPS+=("git")
    fi

    echo ""

    local needs_node="false"
    local needs_pal="false"
    if [ "$CFG_GEMINI_ENABLED" = "true" ] || [ "$CFG_CODEX_ENABLED" = "true" ]; then
        needs_node="true"
        needs_pal="true"
    fi

    # Core dependencies
    if [ "$needs_node" = "true" ]; then
        if check_node; then
            ok "Node.js: $(node --version)"
        else
            warn "Node.js: Not found"
            MISSING_DEPS+=("nodejs")
        fi

        if check_npm; then
            ok "npm: $(npm --version 2>/dev/null)"
        else
            warn "npm: Not found"
            MISSING_DEPS+=("npm")
        fi
    else
        info "Node.js/npm: Skipped (Gemini/Codex disabled)"
    fi

    if [ "$needs_pal" = "true" ]; then
        if check_python; then
            local py_ver=$(python3 --version 2>/dev/null || python --version 2>/dev/null)
            ok "Python: $py_ver"
        else
            warn "Python: Not found"
            MISSING_DEPS+=("python")
        fi

        if check_uv; then
            ok "uv: $(uv --version 2>/dev/null | head -1)"
        else
            warn "uv: Not found (required for PAL MCP via uvx)"
            MISSING_DEPS+=("uv")
        fi

        if check_uvx; then
            ok "uvx: Available"
        else
            warn "uvx: Not found (required for PAL MCP)"
            MISSING_DEPS+=("uvx")
        fi

        if command_exists jq; then
            ok "jq: $(jq --version 2>/dev/null)"
        else
            warn "jq: Not found (recommended for auto-config)"
            MISSING_DEPS+=("jq")
        fi
    else
        info "Python/uv/jq: Skipped (PAL not required)"
    fi

    echo ""

    # Nexus-specific dependencies
    echo -e "${BOLD}Nexus CLI Dependencies${NC}"
    echo ""

    if [ "$needs_pal" = "true" ]; then
        if check_pal_mcp; then
            ok "PAL MCP: Configured"
        else
            warn "PAL MCP: Not configured (required for Gemini/Codex via clink)"
            MISSING_DEPS+=("pal-mcp")
        fi
    else
        info "PAL MCP: Skipped (Gemini/Codex disabled)"
    fi

    if [ "$CFG_GEMINI_ENABLED" = "true" ]; then
        if check_gemini; then
            ok "Gemini CLI: Available"
        else
            warn "Gemini CLI: Not found"
            MISSING_DEPS+=("gemini")
        fi
    else
        info "Gemini CLI: Skipped (disabled)"
    fi

    if [ "$CFG_CODEX_ENABLED" = "true" ]; then
        if check_codex; then
            ok "Codex CLI: Available"
        else
            warn "Codex CLI: Not found"
            MISSING_DEPS+=("codex")
        fi
    else
        info "Codex CLI: Skipped (disabled)"
    fi

    if check_ralph; then
        ok "Ralph Orchestrator: Available"
    else
        warn "Ralph Orchestrator: Not found (optional, for Ralph mode)"
        MISSING_DEPS+=("ralph")
    fi

    echo ""
}

# Offer to install missing dependencies
install_missing_deps() {
    if [ ${#MISSING_DEPS[@]} -eq 0 ]; then
        ok "All dependencies are installed!"
        return 0
    fi

    echo -e "${YELLOW}Missing dependencies: ${MISSING_DEPS[*]}${NC}"
    echo ""

    local install_all=$(ask_yes_no "Would you like to install missing dependencies?" "y")

    if [ "$install_all" = "true" ]; then
        local failed_deps=()
        for dep in "${MISSING_DEPS[@]}"; do
            case $dep in
                "jq")
                    if ! install_jq; then
                        failed_deps+=("jq")
                    fi
                    ;;
                "uv")
                    if ! install_uv; then
                        failed_deps+=("uv")
                    fi
                    ;;
                "pal-mcp")
                    if ! install_pal_mcp; then
                        failed_deps+=("pal-mcp")
                    fi
                    ;;
                "gemini")
                    if ! install_gemini; then
                        failed_deps+=("gemini")
                    fi
                    ;;
                "codex")
                    if ! install_codex; then
                        failed_deps+=("codex")
                    fi
                    ;;
                "ralph")
                    if ! install_ralph; then
                        failed_deps+=("ralph")
                    fi
                    ;;
                "nodejs"|"npm")
                    warn "Please install Node.js manually:"
                    echo -e "  ${DIM}brew install node${NC}  (macOS)"
                    echo -e "  ${DIM}sudo apt install nodejs npm${NC}  (Ubuntu/Debian)"
                    ;;
                "python")
                    warn "Please install Python manually:"
                    echo -e "  ${DIM}brew install python${NC}  (macOS)"
                    echo -e "  ${DIM}sudo apt install python3${NC}  (Ubuntu/Debian)"
                    ;;
            esac
        done
        echo ""
        if [ ${#failed_deps[@]} -gt 0 ]; then
            warn "Some dependencies could not be installed automatically: ${failed_deps[*]}"
            info "You can continue with Claude-only mode or install them manually later."
        else
            ok "Dependency installation complete"
        fi
    else
        info "Skipping dependency installation"
        echo -e "${DIM}You can install them manually later${NC}"
    fi
}

show_help() {
    head -25 "$0" | tail -20 | sed 's/^# //' | sed 's/^#//'
    exit 0
}

# Print a header box
print_header() {
    echo ""
    echo -e "${CYAN}╔════════════════════════════════════════════════════════════════╗${NC}"
    echo -e "${CYAN}║${NC}     ${BOLD}Nexus CLI Interactive Installation Wizard${NC}     ${CYAN}║${NC}"
    echo -e "${CYAN}║${NC}                      ${DIM}v${VERSION}${NC}                            ${CYAN}║${NC}"
    echo -e "${CYAN}╚════════════════════════════════════════════════════════════════╝${NC}"
    echo ""
}

# Print a section header
print_section() {
    echo ""
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
    echo -e "${BOLD}  $1${NC}"
    echo -e "${BLUE}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
}

# Ask a yes/no question
ask_yes_no() {
    local prompt="$1"
    local default="$2"
    local result

    if [ "$default" = "y" ]; then
        prompt="$prompt [Y/n]: "
    else
        prompt="$prompt [y/N]: "
    fi

    read -r -p "$prompt" response
    response=${response:-$default}

    case "$response" in
        [yY][eE][sS]|[yY]) echo "true" ;;
        *) echo "false" ;;
    esac
}

# Ask for a selection from options
ask_select() {
    local prompt="$1"
    shift
    local options=("$@")
    local count=${#options[@]}
    local selection

    echo -e "\n${prompt}" >&2
    for i in "${!options[@]}"; do
        echo -e "  ${CYAN}$((i+1))${NC}) ${options[$i]}" >&2
    done

    while true; do
        read -r -p "Enter choice [1-$count]: " selection
        if [[ "$selection" =~ ^[0-9]+$ ]] && [ "$selection" -ge 1 ] && [ "$selection" -le "$count" ]; then
            echo "$((selection-1))"
            return
        fi
        echo -e "${RED}Invalid selection. Please enter 1-$count.${NC}" >&2
    done
}

# Ask for a number within range
ask_number() {
    local prompt="$1"
    local default="$2"
    local min="$3"
    local max="$4"
    local value

    while true; do
        read -r -p "$prompt [$default]: " value
        value=${value:-$default}
        if [[ "$value" =~ ^[0-9]+$ ]] && [ "$value" -ge "$min" ] && [ "$value" -le "$max" ]; then
            echo "$value"
            return
        fi
        echo -e "${RED}Please enter a number between $min and $max.${NC}"
    done
}

# ─────────────────────────────────────────────────────────────────────────────
# Parse Arguments
# ─────────────────────────────────────────────────────────────────────────────

while [[ $# -gt 0 ]]; do
    case $1 in
        --quick)
            QUICK_MODE=true
            shift
            ;;
        --config-only)
            CONFIG_ONLY=true
            shift
            ;;
        --check-deps)
            print_header
            run_dependency_checks
            install_missing_deps
            exit 0
            ;;
        --help|-h)
            show_help
            ;;
        *)
            echo -e "${RED}Unknown option: $1${NC}"
            echo "Use --help for usage information"
            exit 1
            ;;
    esac
done

# ─────────────────────────────────────────────────────────────────────────────
# Main Installation Wizard
# ─────────────────────────────────────────────────────────────────────────────

print_header

if [ "$QUICK_MODE" = true ]; then
    info "Quick mode: Using default configuration"
    echo ""
else
    echo -e "This wizard will help you configure Nexus CLI for your preferences."
    echo -e "Press ${CYAN}Enter${NC} to accept default values shown in ${DIM}[brackets]${NC}."
    echo ""

    read -r -p "Press Enter to continue or Ctrl+C to cancel..."
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Section 1: Basic Settings
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$QUICK_MODE" = false ]; then
    print_section "1/6 Basic Settings"

    # Language selection
    echo -e "\n${BOLD}Language / 语言设置${NC}"
    lang_options=("Auto-detect (recommended)" "English (en-US)" "中文 (zh-CN)")
    lang_choice=$(ask_select "Select your preferred language:" "${lang_options[@]}")
    case $lang_choice in
        0) CFG_LANGUAGE="auto" ;;
        1) CFG_LANGUAGE="en-US" ;;
        2) CFG_LANGUAGE="zh-CN" ;;
    esac
    ok "Language: $CFG_LANGUAGE"

    # Default executor
    echo -e "\n${BOLD}Default Executor${NC}"
    echo -e "${DIM}Used when no routing rules match${NC}"
    exec_options=("Claude (architecture, analysis)" "Gemini (frontend, algorithms)" "Codex (backend, database)")
    exec_choice=$(ask_select "Select default executor:" "${exec_options[@]}")
    case $exec_choice in
        0) CFG_DEFAULT_EXECUTOR="claude" ;;
        1) CFG_DEFAULT_EXECUTOR="gemini" ;;
        2) CFG_DEFAULT_EXECUTOR="codex" ;;
    esac
    ok "Default executor: $CFG_DEFAULT_EXECUTOR"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Section 2: Execution Settings
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$QUICK_MODE" = false ]; then
    print_section "2/6 Execution Settings"

    # Max parallel tasks
    echo -e "\n${BOLD}Parallel Execution${NC}"
    echo -e "${DIM}Maximum tasks to run simultaneously within a batch${NC}"
    CFG_MAX_PARALLEL=$(ask_number "Max parallel tasks" "5" "1" "20")
    ok "Max parallel tasks: $CFG_MAX_PARALLEL"

    # Task timeout
    echo -e "\n${BOLD}Task Timeout${NC}"
    echo -e "${DIM}Maximum time for individual task execution (minutes)${NC}"
    CFG_TASK_TIMEOUT=$(ask_number "Task timeout (minutes)" "10" "1" "60")
    ok "Task timeout: ${CFG_TASK_TIMEOUT}min"

    # Error strategy
    echo -e "\n${BOLD}Error Handling Strategy${NC}"
    error_options=(
        "ask - Ask user how to handle (recommended)"
        "retry - Automatically retry failed tasks"
        "skip - Skip failed tasks and continue"
        "fail_fast - Stop immediately on failure"
    )
    error_choice=$(ask_select "Select error handling strategy:" "${error_options[@]}")
    case $error_choice in
        0) CFG_ERROR_STRATEGY="ask" ;;
        1) CFG_ERROR_STRATEGY="retry" ;;
        2) CFG_ERROR_STRATEGY="skip" ;;
        3) CFG_ERROR_STRATEGY="fail_fast" ;;
    esac
    ok "Error strategy: $CFG_ERROR_STRATEGY"

    # Max retries (if retry strategy)
    if [ "$CFG_ERROR_STRATEGY" = "retry" ]; then
        CFG_MAX_RETRIES=$(ask_number "Maximum retry attempts" "3" "1" "10")
        ok "Max retries: $CFG_MAX_RETRIES"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Section 3: Executor Configuration
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$QUICK_MODE" = false ]; then
    print_section "3/6 Executor Configuration"

    echo -e "\n${BOLD}Enable/Disable Executors${NC}"
    echo -e "${DIM}Select which AI executors to enable${NC}"

    echo -e "\n🧠 ${BOLD}Claude${NC} - Architecture, analysis, complex reasoning"
    CFG_CLAUDE_ENABLED=$(ask_yes_no "Enable Claude executor?" "y")
    [ "$CFG_CLAUDE_ENABLED" = "true" ] && ok "Claude: Enabled" || warn "Claude: Disabled"

    echo -e "\n💎 ${BOLD}Gemini${NC} - Frontend UI, algorithms, web search"
    CFG_GEMINI_ENABLED=$(ask_yes_no "Enable Gemini executor?" "y")
    [ "$CFG_GEMINI_ENABLED" = "true" ] && ok "Gemini: Enabled" || warn "Gemini: Disabled"

    echo -e "\n🔷 ${BOLD}Codex${NC} - Backend API, database, server logic"
    CFG_CODEX_ENABLED=$(ask_yes_no "Enable Codex executor?" "y")
    [ "$CFG_CODEX_ENABLED" = "true" ] && ok "Codex: Enabled" || warn "Codex: Disabled"

    # Check if at least one is enabled
    if [ "$CFG_CLAUDE_ENABLED" = "false" ] && [ "$CFG_GEMINI_ENABLED" = "false" ] && [ "$CFG_CODEX_ENABLED" = "false" ]; then
        warn "No executors enabled! Enabling Claude as fallback."
        CFG_CLAUDE_ENABLED="true"
    fi

    # Ensure default executor is enabled
    if { [ "$CFG_DEFAULT_EXECUTOR" = "claude" ] && [ "$CFG_CLAUDE_ENABLED" = "false" ]; } \
        || { [ "$CFG_DEFAULT_EXECUTOR" = "gemini" ] && [ "$CFG_GEMINI_ENABLED" = "false" ]; } \
        || { [ "$CFG_DEFAULT_EXECUTOR" = "codex" ] && [ "$CFG_CODEX_ENABLED" = "false" ]; }; then
        warn "Default executor '$CFG_DEFAULT_EXECUTOR' is disabled. Selecting a fallback..."
        if [ "$CFG_CLAUDE_ENABLED" = "true" ]; then
            CFG_DEFAULT_EXECUTOR="claude"
        elif [ "$CFG_GEMINI_ENABLED" = "true" ]; then
            CFG_DEFAULT_EXECUTOR="gemini"
        else
            CFG_DEFAULT_EXECUTOR="codex"
        fi
        ok "Default executor: $CFG_DEFAULT_EXECUTOR"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Section 4: Quality Gates Configuration
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$QUICK_MODE" = false ]; then
    print_section "4/6 Quality Gates Configuration"

    echo -e "\n${BOLD}Quality Gates${NC}"
    echo -e "${DIM}Automated checks to ensure code quality${NC}"

    CFG_QG_ENABLED=$(ask_yes_no "Enable quality gates?" "y")

    if [ "$CFG_QG_ENABLED" = "true" ]; then
        ok "Quality gates: Enabled"

        # Gate policy
        echo -e "\n${BOLD}Gate Execution Policy${NC}"
        policy_options=(
            "on_complete - Run after all batches complete (recommended)"
            "per_batch - Run after each batch"
            "manual - Only run when explicitly requested"
        )
        policy_choice=$(ask_select "When should quality gates run?" "${policy_options[@]}")
        case $policy_choice in
            0) CFG_QG_POLICY="on_complete" ;;
            1) CFG_QG_POLICY="per_batch" ;;
            2) CFG_QG_POLICY="manual" ;;
        esac
        ok "Gate policy: $CFG_QG_POLICY"

        # Ask before run
        CFG_QG_ASK_BEFORE=$(ask_yes_no "Ask user before running gates?" "y")
        [ "$CFG_QG_ASK_BEFORE" = "true" ] && ok "User confirmation: Required" || info "User confirmation: Automatic"

        # Individual gates
        echo -e "\n${BOLD}Configure Individual Gates${NC}"

        # Build gate
        echo -e "\n🔧 ${BOLD}Build Gate${NC} - Verify project compiles/builds"
        CFG_QG_BUILD=$(ask_yes_no "Enable build verification?" "y")
        if [ "$CFG_QG_BUILD" = "true" ]; then
            CFG_QG_BUILD_REQUIRED=$(ask_yes_no "Is build gate required (blocks on failure)?" "y")
            [ "$CFG_QG_BUILD_REQUIRED" = "true" ] && ok "Build: Enabled (required)" || ok "Build: Enabled (optional)"
        else
            warn "Build gate: Disabled"
        fi

        # Lint gate
        echo -e "\n📝 ${BOLD}Lint Gate${NC} - Code style and quality checks"
        CFG_QG_LINT=$(ask_yes_no "Enable lint checks?" "y")
        if [ "$CFG_QG_LINT" = "true" ]; then
            CFG_QG_LINT_REQUIRED=$(ask_yes_no "Is lint gate required (blocks on failure)?" "n")
            [ "$CFG_QG_LINT_REQUIRED" = "true" ] && ok "Lint: Enabled (required)" || ok "Lint: Enabled (optional)"
        else
            warn "Lint gate: Disabled"
        fi

        # Type check gate
        echo -e "\n🔍 ${BOLD}Type Check Gate${NC} - Static type verification"
        CFG_QG_TYPECHECK=$(ask_yes_no "Enable type checking?" "y")
        if [ "$CFG_QG_TYPECHECK" = "true" ]; then
            CFG_QG_TYPECHECK_REQUIRED=$(ask_yes_no "Is type check gate required (blocks on failure)?" "y")
            [ "$CFG_QG_TYPECHECK_REQUIRED" = "true" ] && ok "Type check: Enabled (required)" || ok "Type check: Enabled (optional)"
        else
            warn "Type check gate: Disabled"
        fi

        # Test gate
        echo -e "\n🧪 ${BOLD}Test Gate${NC} - Run test suite"
        CFG_QG_TEST=$(ask_yes_no "Enable test execution?" "n")
        if [ "$CFG_QG_TEST" = "true" ]; then
            CFG_QG_TEST_REQUIRED=$(ask_yes_no "Is test gate required (blocks on failure)?" "n")
            [ "$CFG_QG_TEST_REQUIRED" = "true" ] && ok "Tests: Enabled (required)" || ok "Tests: Enabled (optional)"
        else
            info "Test gate: Disabled (can be slow)"
        fi

        # Code review gate
        echo -e "\n👁️ ${BOLD}Code Review Gate${NC} - AI-assisted code review"
        CFG_QG_REVIEW=$(ask_yes_no "Enable AI code review?" "y")
        if [ "$CFG_QG_REVIEW" = "true" ]; then
            CFG_QG_REVIEW_REQUIRED=$(ask_yes_no "Is code review required (blocks on failure)?" "n")
            [ "$CFG_QG_REVIEW_REQUIRED" = "true" ] && ok "Code review: Enabled (required)" || ok "Code review: Enabled (optional)"
        else
            warn "Code review gate: Disabled"
        fi
    else
        warn "Quality gates: Disabled"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Section 5: Logging Configuration
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$QUICK_MODE" = false ]; then
    print_section "5/6 Logging Configuration"

    CFG_LOG_ENABLED=$(ask_yes_no "Enable execution logging?" "y")

    if [ "$CFG_LOG_ENABLED" = "true" ]; then
        ok "Logging: Enabled"

        # Log level
        level_options=("info (recommended)" "debug (verbose)" "warn (minimal)" "error (errors only)")
        level_choice=$(ask_select "Select log level:" "${level_options[@]}")
        case $level_choice in
            0) CFG_LOG_LEVEL="info" ;;
            1) CFG_LOG_LEVEL="debug" ;;
            2) CFG_LOG_LEVEL="warn" ;;
            3) CFG_LOG_LEVEL="error" ;;
        esac
        ok "Log level: $CFG_LOG_LEVEL"

        CFG_LOG_TO_FILE=$(ask_yes_no "Save logs to file?" "y")
        [ "$CFG_LOG_TO_FILE" = "true" ] && ok "Log to file: Yes (.nexus-temp/logs/)" || info "Log to file: No"
    else
        warn "Logging: Disabled"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Section 6: Feature Flags
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$QUICK_MODE" = false ]; then
    print_section "6/6 Additional Features"

    echo -e "\n${BOLD}Post-Completion Options${NC}"

    CFG_SKIP_CODE_REVIEW=$(ask_yes_no "Skip code review prompt after completion?" "n")
    [ "$CFG_SKIP_CODE_REVIEW" = "true" ] && info "Code review prompt: Skipped" || ok "Code review prompt: Enabled"

    CFG_SKIP_DOCUMENTATION=$(ask_yes_no "Skip documentation prompt after completion?" "n")
    [ "$CFG_SKIP_DOCUMENTATION" = "true" ] && info "Documentation prompt: Skipped" || ok "Documentation prompt: Enabled"

    CFG_AUTO_CHECKPOINT=$(ask_yes_no "Enable automatic checkpoints (for resume capability)?" "y")
    [ "$CFG_AUTO_CHECKPOINT" = "true" ] && ok "Auto-checkpoint: Enabled" || warn "Auto-checkpoint: Disabled"
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Generate Configuration File
# ═══════════════════════════════════════════════════════════════════════════════

print_section "Generating Configuration"

CONFIG_OUTPUT="# ═══════════════════════════════════════════════════════════════════════════════
# Nexus CLI Configuration File
# ═══════════════════════════════════════════════════════════════════════════════
# Generated by install-nexus-skill.sh on $(date '+%Y-%m-%d %H:%M:%S')
# Version: ${VERSION}
# ═══════════════════════════════════════════════════════════════════════════════

version: \"1.0.0\"

# Language setting: auto, zh-CN, en-US
language: ${CFG_LANGUAGE}

# Spec and checkpoint directories (relative to project root)
spec_dir: \"${CFG_SPEC_DIR}\"
checkpoint_dir: \"${CFG_CHECKPOINT_DIR}\"

# ─────────────────────────────────────────────────────────────────────────────
# Executor Routing Configuration
# ─────────────────────────────────────────────────────────────────────────────
routing:
  default_executor: ${CFG_DEFAULT_EXECUTOR}

  rules:
    # Frontend - Gemini excels at UI components
    - pattern: \"**/components/**\"
      executor: gemini
      priority: 10
      description: \"React/Vue components\"

    - pattern: \"*.tsx\"
      executor: gemini
      priority: 5
      description: \"TypeScript React files\"

    - pattern: \"*.vue\"
      executor: gemini
      priority: 5
      description: \"Vue single-file components\"

    - pattern: \"**/ui/**\"
      executor: gemini
      priority: 8
      description: \"UI related files\"

    # Backend - Codex excels at APIs and databases
    - pattern: \"**/api/**\"
      executor: codex
      priority: 10
      description: \"API endpoints\"

    - pattern: \"**/models/**\"
      executor: codex
      priority: 8
      description: \"Data models\"

    - pattern: \"**/services/**\"
      executor: codex
      priority: 8
      description: \"Service layer\"

    - pattern: \"**/db/**\"
      executor: codex
      priority: 10
      description: \"Database related\"

    - pattern: \"*.sql\"
      executor: codex
      priority: 10
      description: \"SQL files\"

    # Architecture - Claude excels at complex reasoning
    - pattern: \"**/architecture/**\"
      executor: claude
      priority: 15
      description: \"Architecture documents\"

  executors:
    claude:
      enabled: ${CFG_CLAUDE_ENABLED}
      timeout_minutes: 15
      max_retries: 2

    gemini:
      enabled: ${CFG_GEMINI_ENABLED}
      timeout_minutes: 10
      max_retries: 3
      role: default

    codex:
      enabled: ${CFG_CODEX_ENABLED}
      timeout_minutes: 10
      max_retries: 3
      role: default

# ─────────────────────────────────────────────────────────────────────────────
# Execution Configuration
# ─────────────────────────────────────────────────────────────────────────────
execution:
  max_parallel_tasks: ${CFG_MAX_PARALLEL}
  task_timeout_minutes: ${CFG_TASK_TIMEOUT}
  batch_timeout_minutes: ${CFG_BATCH_TIMEOUT}
  error_strategy: ${CFG_ERROR_STRATEGY}
  max_retries: ${CFG_MAX_RETRIES}
  retry_delay_seconds: 5

# ─────────────────────────────────────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────────────────────────────────────
logging:
  enabled: ${CFG_LOG_ENABLED}
  level: ${CFG_LOG_LEVEL}
  log_to_file: ${CFG_LOG_TO_FILE}
  log_dir: \".nexus-temp/logs\"
  max_log_files: 10
  max_log_size_mb: 10

# ─────────────────────────────────────────────────────────────────────────────
# Progress Display Configuration
# ─────────────────────────────────────────────────────────────────────────────
progress:
  show_task_progress: true
  show_batch_progress: true
  show_time_estimates: true
  show_executor_stats: true
  update_interval_seconds: 1.0

# ─────────────────────────────────────────────────────────────────────────────
# Feature Flags
# ─────────────────────────────────────────────────────────────────────────────
skip_code_review: ${CFG_SKIP_CODE_REVIEW}
skip_documentation: ${CFG_SKIP_DOCUMENTATION}
auto_checkpoint: ${CFG_AUTO_CHECKPOINT}

# ─────────────────────────────────────────────────────────────────────────────
# Quality Gates Configuration
# ─────────────────────────────────────────────────────────────────────────────
quality_gates:
  enabled: ${CFG_QG_ENABLED}
  policy: ${CFG_QG_POLICY}
  ask_before_run: ${CFG_QG_ASK_BEFORE}

  gates:
    build:
      enabled: ${CFG_QG_BUILD}
      required: ${CFG_QG_BUILD_REQUIRED}

    lint:
      enabled: ${CFG_QG_LINT}
      required: ${CFG_QG_LINT_REQUIRED}

    typecheck:
      enabled: ${CFG_QG_TYPECHECK}
      required: ${CFG_QG_TYPECHECK_REQUIRED}

    test:
      enabled: ${CFG_QG_TEST}
      required: ${CFG_QG_TEST_REQUIRED}

    review:
      enabled: ${CFG_QG_REVIEW}
      required: ${CFG_QG_REVIEW_REQUIRED}
      focus:
        - security
        - performance
        - quality
      thinking_mode: medium

  gate_timeout_seconds: 300
  continue_on_optional_failure: true
  log_gate_results: true
"

# Ask where to save config
if [ "$QUICK_MODE" = false ]; then
    echo -e "\n${BOLD}Save Configuration${NC}"
    save_options=(
        "Current directory (.nexus-config.yaml)"
        "Home directory (~/.nexus/config.yaml)"
        "Both locations"
        "Show only (don't save)"
    )
    save_choice=$(ask_select "Where to save configuration?" "${save_options[@]}")
else
    save_choice=0
fi

# Save configuration
case $save_choice in
    0)
        echo "$CONFIG_OUTPUT" > ".nexus-config.yaml"
        ok "Saved to .nexus-config.yaml"
        ;;
    1)
        mkdir -p "$HOME/.nexus"
        echo "$CONFIG_OUTPUT" > "$HOME/.nexus/config.yaml"
        ok "Saved to ~/.nexus/config.yaml"
        ;;
    2)
        echo "$CONFIG_OUTPUT" > ".nexus-config.yaml"
        ok "Saved to .nexus-config.yaml"
        mkdir -p "$HOME/.nexus"
        echo "$CONFIG_OUTPUT" > "$HOME/.nexus/config.yaml"
        ok "Saved to ~/.nexus/config.yaml"
        ;;
    3)
        echo ""
        echo -e "${DIM}$CONFIG_OUTPUT${NC}"
        ;;
esac

# ═══════════════════════════════════════════════════════════════════════════════
# Install Skill (unless --config-only)
# ═══════════════════════════════════════════════════════════════════════════════

if [ "$CONFIG_ONLY" = false ]; then
    print_section "Installing Nexus Skill"

    # Check prerequisites
    step "Checking prerequisites"

    # Detect available platforms
    DETECTED_TARGET=$(detect_install_target)
    
    if [ "$DETECTED_TARGET" = "none" ]; then
        err "Neither Claude Code nor OpenCode found. Install one of them first."
    fi
    
    if [ "$DETECTED_TARGET" = "both" ]; then
        ok "Both Claude Code and OpenCode detected"
    elif [ "$DETECTED_TARGET" = "opencode" ]; then
        ok "OpenCode detected"
    else
        ok "Claude Code detected"
    fi

    # Run comprehensive dependency checks
    run_dependency_checks

    # Offer to install missing dependencies
    if [ ${#MISSING_DEPS[@]} -gt 0 ]; then
        install_missing_deps
    fi

    # Install skill
    step "Installing skill files"

    # Install for Claude Code (commands directory)
    if [ "$DETECTED_TARGET" = "claude" ] || [ "$DETECTED_TARGET" = "both" ]; then
        mkdir -p "$COMMANDS_DIR"
        if [ -f "$PROJECT_DIR/commands/nexus.md" ]; then
            cp "$PROJECT_DIR/commands/nexus.md" "$COMMANDS_DIR/"
            ok "Installed nexus.md to ~/.claude/commands/"
        fi
        
        # Also install SKILL.md to ~/.claude/skills/ for OpenCode compatibility
        mkdir -p "$CLAUDE_SKILLS_DIR"
        if [ -f "$PROJECT_DIR/skills/nexus-cli/SKILL.md" ]; then
            cp "$PROJECT_DIR/skills/nexus-cli/SKILL.md" "$CLAUDE_SKILLS_DIR/"
            ok "Installed SKILL.md to ~/.claude/skills/nexus-cli/"
        fi
    fi
    
    # Install for OpenCode (XDG config directory)
    if [ "$DETECTED_TARGET" = "opencode" ] || [ "$DETECTED_TARGET" = "both" ]; then
        mkdir -p "$OPENCODE_SKILLS_DIR"
        if [ -f "$PROJECT_DIR/skills/nexus-cli/SKILL.md" ]; then
            cp "$PROJECT_DIR/skills/nexus-cli/SKILL.md" "$OPENCODE_SKILLS_DIR/"
            ok "Installed SKILL.md to ~/.config/opencode/skills/nexus-cli/"
        fi
    fi

    # Verify
    step "Verifying installation"

    install_success=false
    if [ -f "$COMMANDS_DIR/nexus.md" ]; then
        ok "Claude Code: nexus.md installed"
        install_success=true
    fi
    if [ -f "$CLAUDE_SKILLS_DIR/SKILL.md" ]; then
        ok "Claude Code (OpenCode compat): SKILL.md installed"
        install_success=true
    fi
    if [ -f "$OPENCODE_SKILLS_DIR/SKILL.md" ]; then
        ok "OpenCode: SKILL.md installed"
        install_success=true
    fi
    
    if [ "$install_success" = false ]; then
        err "Installation failed"
    fi
fi

# ═══════════════════════════════════════════════════════════════════════════════
# Installation Summary
# ═══════════════════════════════════════════════════════════════════════════════

echo ""
echo -e "${GREEN}╔════════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}║              Installation Complete! (v${VERSION})                ║${NC}"
echo -e "${GREEN}╚════════════════════════════════════════════════════════════════╝${NC}"
echo ""

if [ "$CONFIG_ONLY" = false ]; then
    echo -e "${BOLD}Installed Files:${NC}"
    [ -f "$COMMANDS_DIR/nexus.md" ] && echo -e "  ${GREEN}~/.claude/commands/nexus.md${NC} - Claude Code skill"
    [ -f "$CLAUDE_SKILLS_DIR/SKILL.md" ] && echo -e "  ${GREEN}~/.claude/skills/nexus-cli/SKILL.md${NC} - OpenCode compatible"
    [ -f "$OPENCODE_SKILLS_DIR/SKILL.md" ] && echo -e "  ${GREEN}~/.config/opencode/skills/nexus-cli/SKILL.md${NC} - OpenCode skill"
    if [ -f ".nexus-config.yaml" ]; then
        echo -e "  ${GREEN}./.nexus-config.yaml${NC} - Project configuration"
    fi
    if [ -f "$HOME/.nexus/config.yaml" ]; then
        echo -e "  ${GREEN}~/.nexus/config.yaml${NC} - User configuration"
    fi
    echo ""
fi

echo -e "${BOLD}Your Configuration:${NC}"
echo -e "  Language:         ${CYAN}${CFG_LANGUAGE}${NC}"
echo -e "  Default Executor: ${CYAN}${CFG_DEFAULT_EXECUTOR}${NC}"
echo -e "  Parallel Tasks:   ${CYAN}${CFG_MAX_PARALLEL}${NC}"
echo -e "  Error Strategy:   ${CYAN}${CFG_ERROR_STRATEGY}${NC}"
echo -e "  Quality Gates:    ${CYAN}${CFG_QG_ENABLED}${NC} (policy: ${CFG_QG_POLICY})"
echo ""

echo -e "${BOLD}Executors:${NC}"
[ "$CFG_CLAUDE_ENABLED" = "true" ] && echo -e "  🧠 Claude:  ${GREEN}Enabled${NC}" || echo -e "  🧠 Claude:  ${RED}Disabled${NC}"
[ "$CFG_GEMINI_ENABLED" = "true" ] && echo -e "  💎 Gemini:  ${GREEN}Enabled${NC}" || echo -e "  💎 Gemini:  ${RED}Disabled${NC}"
[ "$CFG_CODEX_ENABLED" = "true" ] && echo -e "  🔷 Codex:   ${GREEN}Enabled${NC}" || echo -e "  🔷 Codex:   ${RED}Disabled${NC}"
echo ""

if [ "$CFG_QG_ENABLED" = "true" ]; then
    echo -e "${BOLD}Quality Gates:${NC}"
    [ "$CFG_QG_BUILD" = "true" ] && echo -e "  🔧 Build:      ${GREEN}Enabled${NC}" || echo -e "  🔧 Build:      ${DIM}Disabled${NC}"
    [ "$CFG_QG_LINT" = "true" ] && echo -e "  📝 Lint:       ${GREEN}Enabled${NC}" || echo -e "  📝 Lint:       ${DIM}Disabled${NC}"
    [ "$CFG_QG_TYPECHECK" = "true" ] && echo -e "  🔍 TypeCheck:  ${GREEN}Enabled${NC}" || echo -e "  🔍 TypeCheck:  ${DIM}Disabled${NC}"
    [ "$CFG_QG_TEST" = "true" ] && echo -e "  🧪 Tests:      ${GREEN}Enabled${NC}" || echo -e "  🧪 Tests:      ${DIM}Disabled${NC}"
    [ "$CFG_QG_REVIEW" = "true" ] && echo -e "  👁️ Review:     ${GREEN}Enabled${NC}" || echo -e "  👁️ Review:     ${DIM}Disabled${NC}"
    echo ""
fi

echo -e "${BOLD}Usage:${NC}"
echo -e "  ${GREEN}/nexus${NC} Create user login feature"
echo -e "  ${GREEN}/nexus --skip-spec${NC} Quick create button component"
echo ""

if [ "$CONFIG_ONLY" = false ]; then
    echo -e "${YELLOW}Restart Claude Code / OpenCode to activate the changes.${NC}"
else
    echo -e "${YELLOW}Run without --config-only to install the skill.${NC}"
fi
echo ""
