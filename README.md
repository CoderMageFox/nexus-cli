# Nexus CLI

<p align="center">
  <img src="assets/logo.jpg" alt="Nexus CLI Logo" width="200">
</p>

> *Smart Routing, Perfect Match.*

[中文文档](README_CN.md)

**Intelligent Task Router for Claude Code** - Automatically route development tasks to the most suitable AI executor (Claude, Gemini, or Codex) based on task characteristics.

## Features

- **Smart Task Routing**: AI-powered analysis to select the optimal executor for each task
- **Multi-Executor Support**: Seamlessly integrate Claude, Gemini CLI, and Codex CLI via PAL MCP
- **Structured Workflow**: Spec-first approach with requirements → design → implementation phases
- **Batch Execution**: Atomic task decomposition (≤5 min each) with parallel execution
- **Real-time Progress**: TodoWrite integration for live progress tracking
- **AI Code Review**: Intelligent code review powered by PAL MCP

## Platform Support

| Platform | Status |
|----------|--------|
| **macOS** | ✅ Fully Supported |
| **Windows** | 🚧 Coming This Week |
| **Linux** | 🔜 Planned |

## Requirements

- [Claude Code](https://claude.ai/code) installed and configured
- [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server) for Gemini/Codex CLI integration (optional, enables multi-executor routing)

## Installation

```bash
# Clone the repository
git clone https://github.com/CoderMageFox/nexus-cli.git
cd nexus-cli

# Run the installer
./install-nexus-skill.sh
```

The installer will:
1. Register Nexus as a Claude Code skill at `~/.claude/commands/nexus.md`
2. Create default configuration file `.nexus-config.yaml`
3. Check for optional dependencies (PAL MCP, Gemini CLI, Codex CLI)

### PAL MCP Configuration (Optional)

To enable multi-executor routing, add PAL MCP to `~/.claude.json`:

```json
{
  "mcpServers": {
    "pal": {
      "command": "uvx",
      "args": ["--from", "git+https://github.com/BeehiveInnovations/pal-mcp-server.git", "pal-mcp-server"],
      "env": {
        "GEMINI_API_KEY": "your-gemini-api-key"
      }
    }
  }
}
```

### Installation Guide for AI Assistants

> **Note**: This section is intended for AI coding assistants (Claude Code, Cursor, etc.) to help users install Nexus CLI.

#### Copy & Paste to Your AI Assistant

Simply copy the text below and send it to Claude Code, Codex, or any AI coding assistant:

**English:**
```
Help me install Nexus CLI.

For quick install, run:
mkdir -p ~/.claude/commands && curl -fsSL https://raw.githubusercontent.com/CoderMageFox/nexus-cli/main/commands/nexus.md -o ~/.claude/commands/nexus.md

For full install with dependency check, run:
cd ~/.claude && git clone https://github.com/CoderMageFox/nexus-cli.git skills/nexus-cli && ~/.claude/skills/nexus-cli/install-nexus-skill.sh

After installation, verify with: ls ~/.claude/commands/nexus.md
```

**中文:**
```
帮我安装 Nexus CLI。

快速安装，运行：
mkdir -p ~/.claude/commands && curl -fsSL https://raw.githubusercontent.com/CoderMageFox/nexus-cli/main/commands/nexus.md -o ~/.claude/commands/nexus.md

完整安装（包含依赖检查），运行：
cd ~/.claude && git clone https://github.com/CoderMageFox/nexus-cli.git skills/nexus-cli && ~/.claude/skills/nexus-cli/install-nexus-skill.sh

安装后验证：ls ~/.claude/commands/nexus.md
```

---

#### Method 1: One-Line Install (Fastest)

Download the skill file directly - no cloning required:

```bash
mkdir -p ~/.claude/commands && curl -fsSL https://raw.githubusercontent.com/CoderMageFox/nexus-cli/main/commands/nexus.md -o ~/.claude/commands/nexus.md
```

⚠️ **Note**: This method only installs the core skill file. Dependencies (PAL MCP, Gemini CLI, Codex CLI) must be installed separately if needed.

#### Method 2: Full Install with Configuration (Recommended)

Includes interactive configuration wizard and automatic dependency installation:

```bash
cd ~/.claude && git clone https://github.com/CoderMageFox/nexus-cli.git skills/nexus-cli && ~/.claude/skills/nexus-cli/install-nexus-skill.sh
```

✅ **This method will**:
- Install the Nexus skill
- Check and install missing dependencies (PAL MCP, Gemini CLI, Codex CLI, jq, uv)
- Generate customized `.nexus-config.yaml`
- Configure quality gates and executor preferences

#### Comparison

| Feature | One-Line Install | Full Install |
|---------|-----------------|--------------|
| Speed | ⚡ Fastest | 🐢 ~2 min |
| Dependencies | ❌ Manual | ✅ Auto-install |
| Configuration | ❌ Default only | ✅ Interactive wizard |
| Best for | Quick start, CI/CD | First-time setup |

#### Step-by-Step for AI Assistants

1. **Check Platform**: Verify user is on macOS (Windows support coming soon)
   ```bash
   uname -s  # Should return "Darwin" for macOS
   ```

2. **Choose Install Method**:
   - New users → Use **Full Install** (Method 2)
   - Experienced users / just need the skill → Use **One-Line Install** (Method 1)

3. **Verify Installation**:
   ```bash
   ls -la ~/.claude/commands/nexus.md  # Should exist after installation
   ```

4. **Check Dependencies** (if using One-Line Install):
   ```bash
   # Optional: Install PAL MCP for multi-executor support
   # Add to ~/.claude.json under mcpServers
   ```

**Post-Installation**: The `/nexus` command will be available in Claude Code after restarting the session.

## Usage

In Claude Code, invoke Nexus with:

```
/nexus <your task description>
```

### Examples

```bash
# Full workflow with spec generation
/nexus Create a user authentication system with JWT tokens

# Skip spec phase for simple tasks
/nexus Create a hello world function --skip-spec

# Frontend task (routes to Gemini)
/nexus Build a responsive login form component

# Backend task (routes to Codex)
/nexus Implement REST API endpoints for user management
```

## Workflow

```
┌─────────────────────────────────────────────────────────────┐
│              Phase 0: PAL MCP Availability Check            │
│         Available → Normal Mode | Unavailable → Claude-Only │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                    SPEC Flow (Phase 1-3)                    │
│  Phase 1: Requirements (EARS format)                        │
│  Phase 2: Design Document                                   │
│  Phase 3: Task Breakdown (Batch format)                     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│                 Execution Flow (Phase 4-5)                  │
│  Phase 4: TodoWrite Init + User Confirmation                │
│  Phase 5: Batch Execution Loop                              │
│           ├─ Execute tasks in parallel per batch            │
│           ├─ Update TodoWrite immediately after each batch  │
│           └─ Route: Claude→Task, Gemini/Codex→PAL clink     │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Quality Gates (Phase 6) - Optional             │
│                     AI Code Review                          │
└─────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────┐
│              Completion Options (Phase 7)                   │
│         Acceptance Confirmation → Documentation             │
└─────────────────────────────────────────────────────────────┘
```

## Executor Selection

| Executor | Best For | Icon |
|----------|----------|------|
| **Claude** | Architecture design, deep analysis, security review, complex reasoning | 🧠 |
| **Gemini** | Frontend UI, algorithms, web search, creative tasks | 💎 |
| **Codex** | Backend APIs, databases, server-side logic | 🔷 |

## Configuration

Edit `.nexus-config.yaml` in your project root:

```yaml
# Language: auto, zh-CN, en-US
language: auto

# Executor routing rules
routing:
  default_executor: claude
  rules:
    - pattern: "**/components/**"
      executor: gemini
      description: "React/Vue components"
    - pattern: "**/api/**"
      executor: codex
      description: "API endpoints"

# Execution settings
execution:
  max_parallel_tasks: 5
  task_timeout_minutes: 10
  batch_timeout_minutes: 30

# Quality gates (AI-powered)
quality_gates:
  enabled: true
  gates:
    review:
      enabled: true
      focus:
        - security
        - performance
        - quality
```

## Mandatory Constraints

| Constraint | Requirement |
|------------|-------------|
| `FORCE_PAL_CHECK` | Must check PAL MCP availability before routing to Gemini/Codex |
| `FORCE_SPEC_FIRST` | Must complete Spec flow before execution (unless `--skip-spec`) |
| `FORCE_ATOMIC_TASKS` | Each task must be ≤5 minutes |
| `FORCE_BATCH_GROUPING` | Tasks must be grouped by dependencies |
| `FORCE_BATCH_TODOWRITE` | Must update TodoWrite immediately after each batch |
| `FORCE_USER_CONFIRMATION` | Must get user confirmation before execution |

## Scripts

| Script | Description |
|--------|-------------|
| `./install-nexus-skill.sh` | Install Nexus CLI |
| `./uninstall-nexus.sh` | Uninstall Nexus CLI |
| `./update-nexus.sh` | Update to latest version |

### Install Options

```bash
./install-nexus-skill.sh [options]

Options:
  --quick         Skip dependency checks
  --check-deps    Only check dependencies, don't install
  --help          Show help message
```

## Project Structure

```
nexus-cli/
├── commands/
│   └── nexus.md           # Main skill definition
├── lib/                   # Library modules
├── locales/               # i18n translations (en-US, zh-CN)
├── templates/             # Document templates
├── tests/                 # Test files
├── install-nexus-skill.sh # Installer
├── uninstall-nexus.sh     # Uninstaller
├── update-nexus.sh        # Updater
├── .nexus-config.yaml     # Configuration template
└── VERSION                # Version file
```

## License

MIT License

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## Related Resources

- [Claude Code](https://claude.ai/code) - AI-powered coding assistant
- [PAL MCP Server](https://github.com/BeehiveInnovations/pal-mcp-server) - Multi-model orchestration
