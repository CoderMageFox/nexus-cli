#Requires -Version 5.1
<#
.SYNOPSIS
    Nexus CLI Updater for Windows
.DESCRIPTION
    Updates Nexus CLI skill to the latest version from GitHub.
.PARAMETER Force
    Skip confirmation prompts
.PARAMETER Help
    Show help message
.EXAMPLE
    .\update-nexus.ps1
    .\update-nexus.ps1 -Force
#>

param(
    [switch]$Force,
    [switch]$Help
)

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
    Write-Host "        Nexus CLI Updater for Windows           " -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Help {
    Write-Host @"
Nexus CLI Updater for Windows

Usage: .\update-nexus.ps1 [options]

Options:
    -Force       Skip confirmation prompts
    -Help        Show this help message

Examples:
    .\update-nexus.ps1              # Interactive update
    .\update-nexus.ps1 -Force       # Force update without prompts
"@
}

function Get-LocalVersion {
    $versionFile = Join-Path $PSScriptRoot "VERSION"
    if (Test-Path $versionFile) {
        return (Get-Content $versionFile -Raw).Trim()
    }
    return "unknown"
}

function Get-RemoteVersion {
    $url = "https://raw.githubusercontent.com/CoderMageFox/nexus-cli/main/VERSION"
    try {
        $response = Invoke-WebRequest -Uri $url -UseBasicParsing -TimeoutSec 10
        return $response.Content.Trim()
    } catch {
        return $null
    }
}

function Update-NexusSkill {
    $skillFile = Join-Path $HOME ".claude\commands\nexus.md"
    $url = "https://raw.githubusercontent.com/CoderMageFox/nexus-cli/main/commands/nexus.md"

    try {
        Invoke-WebRequest -Uri $url -OutFile $skillFile -UseBasicParsing
        Write-Status "Updated nexus.md" "ok"
        return $true
    } catch {
        Write-Status "Failed to download: $_" "error"
        return $false
    }
}

# Main execution
function Main {
    if ($Help) {
        Show-Help
        return
    }

    Show-Banner

    # Check versions
    Write-Status "Checking versions..." "step"

    $localVersion = Get-LocalVersion
    $remoteVersion = Get-RemoteVersion

    Write-Status "Local version: $localVersion" "info"

    if (-not $remoteVersion) {
        Write-Status "Could not fetch remote version" "error"
        return
    }

    Write-Status "Remote version: $remoteVersion" "info"

    if ($localVersion -eq $remoteVersion) {
        Write-Status "Already up to date!" "ok"
        return
    }

    Write-Host ""
    Write-Host "Update available: $localVersion -> $remoteVersion" -ForegroundColor Yellow

    # Confirmation
    if (-not $Force) {
        $response = Read-Host "Update now? (Y/n)"
        if ($response -eq "n" -or $response -eq "N") {
            Write-Status "Update cancelled" "info"
            return
        }
    }

    Write-Host ""
    Write-Status "Updating Nexus CLI..." "step"

    # Update skill file
    if (Update-NexusSkill) {
        Write-Host ""
        Write-Host "Update complete! ($localVersion -> $remoteVersion)" -ForegroundColor Green
        Write-Host "Restart Claude Code to apply changes." -ForegroundColor Cyan
    } else {
        Write-Status "Update failed" "error"
    }
    Write-Host ""
}

# Run main
Main
