#!/usr/bin/env pwsh
# Version bump script for PythonPackageDownloader
# Updates version in AppxManifest.xml and pyproject.toml

param(
    [Parameter(Mandatory = $false)]
    [ValidateSet("major", "minor", "patch")]
    [string]$BumpType = "patch",
    
    [Parameter(Mandatory = $false)]
    [string]$SpecificVersion = $null
)

$ErrorActionPreference = "Stop"

# File paths
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$appxPath = Join-Path $scriptDir "AppxManifest.xml"
$pyprojectPath = Join-Path $scriptDir "pyproject.toml"

Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Version Bump Script" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host ""

# Validate files exist
if (-not (Test-Path $appxPath)) {
    Write-Host "Error: AppxManifest.xml not found at $appxPath" -ForegroundColor Red
    exit 1
}
if (-not (Test-Path $pyprojectPath)) {
    Write-Host "Error: pyproject.toml not found at $pyprojectPath" -ForegroundColor Red
    exit 1
}

# Extract current version from pyproject.toml
$pyprojectContent = Get-Content $pyprojectPath -Raw
$versionMatch = [regex]::Match($pyprojectContent, 'version\s*=\s*"(\d+\.\d+\.\d+)"')

if (-not $versionMatch.Success) {
    Write-Host "Error: Could not find version in pyproject.toml" -ForegroundColor Red
    exit 1
}

$currentVersion = $versionMatch.Groups[1].Value
Write-Host "Current version: $currentVersion" -ForegroundColor Yellow

# Parse version
$versionParts = $currentVersion -split '\.'
$major = [int]$versionParts[0]
$minor = [int]$versionParts[1]
$patch = [int]$versionParts[2]

# Calculate new version
if ($SpecificVersion) {
    # Validate specific version format
    if ($SpecificVersion -notmatch '^\d+\.\d+\.\d+$') {
        Write-Host "Error: Invalid version format. Use X.Y.Z format (e.g., 1.2.3)" -ForegroundColor Red
        exit 1
    }
    $newVersion = $SpecificVersion
    Write-Host "New version (manual): $newVersion" -ForegroundColor Green
} else {
    switch ($BumpType) {
        "major" {
            $major++
            $minor = 0
            $patch = 0
        }
        "minor" {
            $minor++
            $patch = 0
        }
        "patch" {
            $patch++
        }
    }
    $newVersion = "$major.$minor.$patch"
    Write-Host "New version ($BumpType): $newVersion" -ForegroundColor Green
}

Write-Host ""

# Update pyproject.toml
Write-Host "Updating pyproject.toml..." -ForegroundColor Yellow
try {
    $newPyprojectContent = $pyprojectContent -replace `
        "version\s*=\s*`"$([regex]::Escape($currentVersion))`"", `
        "version = `"$newVersion`""
    
    Set-Content -Path $pyprojectPath -Value $newPyprojectContent -Encoding UTF8
    Write-Host "✓ pyproject.toml updated" -ForegroundColor Green
} catch {
    Write-Host "Error updating pyproject.toml: $_" -ForegroundColor Red
    exit 1
}

# Update AppxManifest.xml (add .0 to version)
Write-Host "Updating AppxManifest.xml..." -ForegroundColor Yellow
try {
    $appxContent = Get-Content $appxPath -Raw
    $newAppxVersion = "$newVersion.0"
    
    # Find current AppX version
    $appxVersionMatch = [regex]::Match($appxContent, 'Version="(\d+\.\d+\.\d+\.\d+)"')
    if ($appxVersionMatch.Success) {
        $currentAppxVersion = $appxVersionMatch.Groups[1].Value
        $newAppxContent = $appxContent -replace `
            "Version=`"$([regex]::Escape($currentAppxVersion))`"", `
            "Version=`"$newAppxVersion`""
    } else {
        Write-Host "Warning: Could not find Version attribute in AppxManifest.xml" -ForegroundColor Yellow
        $newAppxContent = $appxContent
    }
    
    Set-Content -Path $appxPath -Value $newAppxContent -Encoding UTF8
    Write-Host "✓ AppxManifest.xml updated" -ForegroundColor Green
} catch {
    Write-Host "Error updating AppxManifest.xml: $_" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "=====================================" -ForegroundColor Cyan
Write-Host "Version bump completed!" -ForegroundColor Green
Write-Host "Version: $currentVersion -> $newVersion" -ForegroundColor Cyan
Write-Host "=====================================" -ForegroundColor Cyan
