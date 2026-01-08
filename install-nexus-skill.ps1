#Requires -Version 5.1
<#
.SYNOPSIS
    Nexus CLI Installer for Windows
.DESCRIPTION
    Installs Nexus CLI skill for Claude Code on Windows.
    Supports dependency checking and PAL MCP configuration.
.PARAMETER Quick
    Skip interactive configuration, use defaults
.PARAMETER CheckDeps
    Only check dependencies, don't install
.PARAMETER Help
    Show help message
.EXAMPLE
    .\install-nexus-skill.ps1
    .\install-nexus-skill.ps1 -Quick
    .\install-nexus-skill.ps1 -CheckDeps
#>

param(
    [switch]$Quick,
    [switch]$CheckDeps,
    [switch]$Help
)

# Colors and formatting
$script:Colors = @{
    Green = "Green"
    Yellow = "Yellow"
    Red = "Red"
    Cyan = "Cyan"
    White = "White"
}

function Write-Status {
    param([string]$Message, [string]$Type = "info")
    switch ($Type) {
        "ok"      { Write-Host "[OK] " -ForegroundColor Green -NoNewline; Write-Host $Message }
        "warn"    { Write-Host "[WARN] " -ForegroundColor Yellow -NoNewline; Write-Host $Message }
        "error"   { Write-Host "[ERROR] " -ForegroundColor Red -NoNewline; Write-Host $Message }
        "info"    { Write-Host "[INFO] " -ForegroundColor Cyan -NoNewline; Write-Host $Message }
        "step"    { Write-Host ">> " -ForegroundColor White -NoNewline; Write-Host $Message }
    }
}

function Show-Banner {
    Write-Host ""
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host "       Nexus CLI Installer for Windows          " -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Help {
    Write-Host @"
Nexus CLI Installer for Windows

Usage: .\install-nexus-skill.ps1 [options]

Options:
    -Quick       Skip interactive configuration (use defaults)
    -CheckDeps   Only check dependencies, don't install
    -Help        Show this help message

Examples:
    .\install-nexus-skill.ps1              # Interactive installation
    .\install-nexus-skill.ps1 -Quick       # Quick installation with defaults
    .\install-nexus-skill.ps1 -CheckDeps   # Check dependencies only

Requirements:
    - Windows 10/11
    - PowerShell 5.1 or later
    - Claude Code installed

Optional (for multi-executor support):
    - Node.js 20+ (for Gemini CLI)
    - Node.js 22+ (for Codex CLI)
    - uv/uvx (for PAL MCP)
    - Git (for PAL MCP)
"@
}

# Dependency checking functions
function Test-ClaudeCode {
    $claudeDir = Join-Path $HOME ".claude"
    return Test-Path $claudeDir
}

function Test-Git {
    try {
        $null = Get-Command git -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-Node {
    param([int]$MinVersion = 20)
    try {
        $nodeVersion = node -v 2>$null
        if ($nodeVersion -match 'v(\d+)') {
            return [int]$Matches[1] -ge $MinVersion
        }
        return $false
    } catch {
        return $false
    }
}

function Test-Uv {
    try {
        $null = Get-Command uv -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-Uvx {
    try {
        $null = Get-Command uvx -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-GeminiCli {
    try {
        $null = Get-Command gemini -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Test-CodexCli {
    try {
        $null = Get-Command codex -ErrorAction Stop
        return $true
    } catch {
        return $false
    }
}

function Show-DependencyStatus {
    Write-Host ""
    Write-Host "Dependency Status:" -ForegroundColor Cyan
    Write-Host "==================" -ForegroundColor Cyan

    # Required
    if (Test-ClaudeCode) {
        Write-Status "Claude Code (~/.claude)" "ok"
    } else {
        Write-Status "Claude Code (~/.claude) - NOT FOUND" "error"
    }

    # Optional
    Write-Host ""
    Write-Host "Optional Dependencies:" -ForegroundColor Yellow

    if (Test-Git) {
        Write-Status "Git" "ok"
    } else {
        Write-Status "Git - not installed (needed for PAL MCP)" "warn"
    }

    if (Test-Node -MinVersion 20) {
        $ver = node -v
        Write-Status "Node.js $ver" "ok"
    } else {
        Write-Status "Node.js 20+ - not found (needed for Gemini/Codex CLI)" "warn"
    }

    if (Test-Uv) {
        Write-Status "uv" "ok"
    } else {
        Write-Status "uv - not installed (needed for PAL MCP)" "warn"
    }

    if (Test-Uvx) {
        Write-Status "uvx" "ok"
    } else {
        Write-Status "uvx - not installed (needed for PAL MCP)" "warn"
    }

    if (Test-GeminiCli) {
        Write-Status "Gemini CLI" "ok"
    } else {
        Write-Status "Gemini CLI - not installed (optional)" "info"
    }

    if (Test-CodexCli) {
        Write-Status "Codex CLI" "ok"
    } else {
        Write-Status "Codex CLI - not installed (optional)" "info"
    }

    Write-Host ""
}

# Installation functions
function Install-NexusSkill {
    $commandsDir = Join-Path $HOME ".claude\commands"
    $skillFile = Join-Path $commandsDir "nexus.md"

    # Create commands directory
    if (-not (Test-Path $commandsDir)) {
        New-Item -ItemType Directory -Force -Path $commandsDir | Out-Null
        Write-Status "Created $commandsDir" "ok"
    }

    # Get script directory
    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    if (-not $scriptDir) {
        $scriptDir = Get-Location
    }

    $sourceFile = Join-Path $scriptDir "commands\nexus.md"

    if (Test-Path $sourceFile) {
        Copy-Item -Path $sourceFile -Destination $skillFile -Force
        Write-Status "Installed nexus.md to $skillFile" "ok"
        return $true
    } else {
        # Try downloading from GitHub
        Write-Status "Local file not found, downloading from GitHub..." "info"
        $url = "https://raw.githubusercontent.com/CoderMageFox/nexus-cli/main/commands/nexus.md"
        try {
            Invoke-WebRequest -Uri $url -OutFile $skillFile -UseBasicParsing
            Write-Status "Downloaded and installed nexus.md" "ok"
            return $true
        } catch {
            Write-Status "Failed to download: $_" "error"
            return $false
        }
    }
}

function Install-DefaultConfig {
    $configFile = Join-Path (Get-Location) ".nexus-config.yaml"

    if (Test-Path $configFile) {
        Write-Status "Config file already exists: $configFile" "info"
        return $true
    }

    $scriptDir = Split-Path -Parent $MyInvocation.ScriptName
    if (-not $scriptDir) { $scriptDir = Get-Location }

    $sourceConfig = Join-Path $scriptDir ".nexus-config.yaml"

    if (Test-Path $sourceConfig) {
        Copy-Item -Path $sourceConfig -Destination $configFile -Force
        Write-Status "Created config: $configFile" "ok"
        return $true
    }

    Write-Status "No template config found, skipping" "info"
    return $true
}

function Install-PalMcp {
    Write-Status "Configuring PAL MCP..." "step"

    if (-not (Test-Uvx)) {
        Write-Status "uvx not found. Install uv first:" "warn"
        Write-Host "  winget install --id=astral-sh.uv -e"
        Write-Host "  # or: irm https://astral.sh/uv/install.ps1 | iex"
        return $false
    }

    # Use claude mcp add command (recommended for Windows)
    Write-Host ""
    Write-Host "To configure PAL MCP, run:" -ForegroundColor Yellow
    Write-Host '  claude mcp add pal --scope user --transport stdio --command uvx --args "--from" "git+https://github.com/BeehiveInnovations/pal-mcp-server.git" "pal-mcp-server"'
    Write-Host ""
    return $true
}

function Show-InstallInstructions {
    Write-Host ""
    Write-Host "Optional: Install dependencies" -ForegroundColor Yellow
    Write-Host "==============================" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "# Install uv (for PAL MCP):"
    Write-Host "  winget install --id=astral-sh.uv -e"
    Write-Host ""
    Write-Host "# Install Node.js (for Gemini/Codex CLI):"
    Write-Host "  winget install --id=OpenJS.NodeJS.LTS -e"
    Write-Host ""
    Write-Host "# Install Gemini CLI:"
    Write-Host "  npm install -g @google/gemini-cli"
    Write-Host ""
    Write-Host "# Install Codex CLI (requires Node 22+):"
    Write-Host "  npm install -g @openai/codex"
    Write-Host ""
}

# Main execution
function Main {
    if ($Help) {
        Show-Help
        return
    }

    Show-Banner

    if ($CheckDeps) {
        Show-DependencyStatus
        return
    }

    # Check Claude Code
    if (-not (Test-ClaudeCode)) {
        Write-Status "Claude Code not found. Please install Claude Code first." "error"
        return
    }

    Write-Status "Installing Nexus CLI..." "step"

    # Install skill file
    if (-not (Install-NexusSkill)) {
        Write-Status "Failed to install Nexus skill" "error"
        return
    }

    # Install config (optional)
    Install-DefaultConfig | Out-Null

    # Show dependency status
    Show-DependencyStatus

    # Show PAL MCP instructions
    if (-not $Quick) {
        Install-PalMcp | Out-Null
        Show-InstallInstructions
    }

    Write-Host ""
    Write-Host "Installation complete!" -ForegroundColor Green
    Write-Host "Restart Claude Code to use /nexus command." -ForegroundColor Cyan
    Write-Host ""
}

# Run main
Main
