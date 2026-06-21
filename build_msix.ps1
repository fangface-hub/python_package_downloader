# build_msix.ps1 - Build MSIX package for Python Package Downloader
#
# Usage:
#   .\build_msix.ps1

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Source the build_nuitka.ps1 to get the Ensure-LLVMInstalled function
. (Join-Path $root 'build_nuitka.ps1')

# Ensure LLVM is installed
Ensure-LLVMInstalled

$OutputDir = 'dist'
$OutputFileName = 'PythonPackageDownloader'
$EntryScript = 'python_package_downloader.py'
$AppVersion = '1.1.1.0'  # Update this for each release

# Certificate configuration
$certName = "PythonPackageDownloader"
$certDir = Join-Path $root "certificates"
$pfxPath = Join-Path $certDir "$certName.pfx"
$pfxPassword = "YourPassword123"

# MSIX configuration
$msixDir = Join-Path $root "msix_build"
$msixPackageDir = Join-Path $msixDir "Package"
$msixSource = Join-Path $msixDir "Package"
$msixOutput = Join-Path $OutputDir "$OutputFileName.msix"
$appxManifest = Join-Path $root "AppxManifest.xml"

Push-Location $root
try {
    Write-Host '[1/5] Installing dependencies with uv'
    & uv sync --group build
    if ($LASTEXITCODE -ne 0) {
        throw 'uv sync failed'
    }

    Write-Host '[2/5] Building executable with Nuitka'
    
    # Build options using array for clarity
    $nuitkaOptions = @(
        '--onefile',
        '--enable-plugin=tk-inter',
        '--windows-console-mode=disable',
        '--windows-icon-from-ico=app_icon.ico',
        '--clang',
        '--lto=auto',
        "--output-dir=$OutputDir",
        "--output-filename=$OutputFileName",
        '--include-data-dir=help=help',
        '--include-data-dir=locales=locales',
        '--include-data-files=config.json=config.json',
        '--include-data-files=loggingex_config.json=loggingex_config.json',
        '--include-data-files=pyproject.toml=pyproject.toml',
        '--include-data-files=Square44x44Logo.png=Square44x44Logo.png',
        '--include-data-files=Square150x150Logo.png=Square150x150Logo.png',
        $EntryScript
    )

    $nuitkaArgs = @('-m', 'nuitka') + $nuitkaOptions
    & uv run python @nuitkaArgs
    if ($LASTEXITCODE -ne 0) {
        throw 'Nuitka build failed'
    }

    Write-Host '[3/5] Preparing MSIX package structure'
    
    # Clean up previous MSIX build
    if (Test-Path $msixDir) {
        Remove-Item -Path $msixDir -Recurse -Force
    }
    
    # Create directory structure for MSIX
    New-Item -ItemType Directory -Path $msixPackageDir | Out-Null
    New-Item -ItemType Directory -Path (Join-Path $msixPackageDir $OutputFileName) | Out-Null
    
    # Copy executable to MSIX package
    $exePath = Join-Path $OutputDir "$OutputFileName.exe"
    if (-not (Test-Path $exePath)) {
        throw "Executable not found: $exePath"
    }
    Copy-Item -Path $exePath -Destination (Join-Path $msixPackageDir $OutputFileName)
    Write-Host "Copied executable to MSIX package"
    
    # Copy app icons
    Copy-Item -Path "Square44x44Logo.png" -Destination $msixPackageDir -ErrorAction SilentlyContinue
    Copy-Item -Path "Square150x150Logo.png" -Destination $msixPackageDir -ErrorAction SilentlyContinue
    
    # Copy and update AppxManifest.xml
    $manifest = Get-Content -Path $appxManifest -Raw
    
    # Update version in manifest
    $manifest = $manifest -replace 'Version="[^"]*"', "Version=`"$AppVersion`""
    
    # Save updated manifest to MSIX package
    $manifest | Out-File -FilePath (Join-Path $msixPackageDir "AppxManifest.xml") -Encoding UTF8
    Write-Host "Created AppxManifest.xml"
    
    Write-Host '[4/4] Creating MSIX package'
    
    # Check if MakeAppx is available
    $makeAppxPath = "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe"
    $makeAppx = Get-Item $makeAppxPath -ErrorAction SilentlyContinue | Select-Object -First 1
    
    if (-not $makeAppx) {
        throw "MakeAppx not found. Please install Windows App SDK or Windows 10/11 SDK."
    }
    
    Write-Host "Using MakeAppx: $($makeAppx.FullName)"
    
    # Create MSIX package
    & $makeAppx.FullName pack /d $msixSource /p $msixOutput
    if ($LASTEXITCODE -ne 0) {
        throw 'MakeAppx pack failed'
    }
    Write-Host "MSIX package created: $msixOutput"
    
    Write-Host "`nMSIX build completed successfully!"
    Write-Host "Output: $msixOutput"
    Write-Host "To sign the MSIX package, run: .\sign_msix.ps1"
    
} finally {
    Pop-Location
}
