#Requires -Version 5.1
<#
.SYNOPSIS
    Nexus CLI Uninstaller for Windows
.DESCRIPTION
    Uninstalls Nexus CLI skill from Claude Code on Windows.
.PARAMETER Force
    Skip confirmation prompts
.PARAMETER Help
    Show help message
.EXAMPLE
    .\uninstall-nexus.ps1
    .\uninstall-nexus.ps1 -Force
#>

param(
    [switch]$Force,
    [switch]$Help
)

# Colors and formatting
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
    Write-Host "       Nexus CLI Uninstaller for Windows        " -ForegroundColor Cyan
    Write-Host "================================================" -ForegroundColor Cyan
    Write-Host ""
}

function Show-Help {
    Write-Host @"
Nexus CLI Uninstaller for Windows

Usage: .\uninstall-nexus.ps1 [options]

Options:
    -Force       Skip confirmation prompts
    -Help        Show this help message

Examples:
    .\uninstall-nexus.ps1              # Interactive uninstallation
    .\uninstall-nexus.ps1 -Force       # Force uninstall without prompts
"@
}

function Remove-NexusSkill {
    $skillFile = Join-Path $HOME ".claude\commands\nexus.md"

    if (Test-Path $skillFile) {
        Remove-Item -Path $skillFile -Force
        Write-Status "Removed $skillFile" "ok"
        return $true
    } else {
        Write-Status "Skill file not found: $skillFile" "warn"
        return $false
    }
}

function Remove-NexusConfig {
    # Remove config from current directory if exists
    $configFile = Join-Path (Get-Location) ".nexus-config.yaml"

    if (Test-Path $configFile) {
        if (-not $Force) {
            $response = Read-Host "Remove local config file $configFile? (y/N)"
            if ($response -ne "y" -and $response -ne "Y") {
                Write-Status "Keeping local config file" "info"
                return $false
            }
        }
        Remove-Item -Path $configFile -Force
        Write-Status "Removed $configFile" "ok"
        return $true
    } else {
        Write-Status "No local config file found" "info"
        return $false
    }
}

function Remove-NexusSpecs {
    # Remove .claude/specs directory if exists
    $specsDir = Join-Path (Get-Location) ".claude\specs"

    if (Test-Path $specsDir) {
        if (-not $Force) {
            $response = Read-Host "Remove specs directory $specsDir? (y/N)"
            if ($response -ne "y" -and $response -ne "Y") {
                Write-Status "Keeping specs directory" "info"
                return $false
            }
        }
        Remove-Item -Path $specsDir -Recurse -Force
        Write-Status "Removed $specsDir" "ok"
        return $true
    } else {
        Write-Status "No specs directory found" "info"
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

    # Confirmation
    if (-not $Force) {
        Write-Host "This will uninstall Nexus CLI from your system." -ForegroundColor Yellow
        Write-Host ""
        $response = Read-Host "Continue? (y/N)"
        if ($response -ne "y" -and $response -ne "Y") {
            Write-Status "Uninstallation cancelled" "info"
            return
        }
        Write-Host ""
    }

    Write-Status "Uninstalling Nexus CLI..." "step"

    # Remove skill file
    $skillRemoved = Remove-NexusSkill

    # Remove config file (optional)
    Remove-NexusConfig | Out-Null

    # Remove specs directory (optional)
    Remove-NexusSpecs | Out-Null

    Write-Host ""
    if ($skillRemoved) {
        Write-Host "Uninstallation complete!" -ForegroundColor Green
        Write-Host "Restart Claude Code to apply changes." -ForegroundColor Cyan
    } else {
        Write-Host "Nexus CLI was not fully installed." -ForegroundColor Yellow
    }
    Write-Host ""
}

# Run main
Main
