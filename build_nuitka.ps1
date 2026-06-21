# build_nuitka.ps1 - Build with Nuitka using Clang compiler
#
# Usage:
#   .\build_nuitka.ps1
#
# This script uses uv to manage Python environment and build with Nuitka.
# The output will be: dist/PythonPackageDownloader.exe (single file executable)
#
# Resources (help, locales, config files) are embedded in the executable.

# Function to ensure LLVM/Clang is installed
function Ensure-LLVMInstalled {
    Write-Host 'Checking for LLVM/Clang...'
    $llvmPath = 'C:\Program Files\LLVM\bin'
    
    # Add LLVM to PATH if not already there
    if ($env:PATH -notlike "*$llvmPath*") {
        $env:PATH = "$llvmPath;$env:PATH"
        Write-Host "Added LLVM to PATH: $llvmPath"
    }
    
    $llvmInstalled = $null -ne (Get-Command clang -ErrorAction SilentlyContinue)

    if (-not $llvmInstalled) {
        Write-Host 'LLVM/Clang not found. Installing with Chocolatey...'
        
        # Check if running as administrator
        $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole] 'Administrator')
        
        if (-not $isAdmin) {
            Write-Host 'Requesting administrator privileges to install LLVM...'
            Start-Process PowerShell -ArgumentList "-NoProfile -ExecutionPolicy Bypass -Command `"choco install llvm -y`"" -Verb RunAs -Wait
        } else {
            choco install llvm -y
        }
        
        # Verify installation
        $llvmInstalled = $null -ne (Get-Command clang -ErrorAction SilentlyContinue)
        if (-not $llvmInstalled) {
            throw 'LLVM/Clang installation failed or clang not found in PATH'
        }
        Write-Host 'LLVM/Clang installed successfully'
    } else {
        Write-Host 'LLVM/Clang found: ' (clang --version)
    }
}

# Main script logic (only runs if script is executed directly, not when sourced)
if ($MyInvocation.InvocationName -ne '.') {
    $ErrorActionPreference = 'Stop'

    $root = Split-Path -Parent $MyInvocation.MyCommand.Path
    $OutputDir = 'dist'
    $OutputFileName = 'PythonPackageDownloader'
    $EntryScript = 'python_package_downloader.py'

    # Ensure LLVM is installed
    Ensure-LLVMInstalled

    Push-Location $root
    try {
        Write-Host '[1/2] Installing dependencies with uv'
    & uv sync --group build
    if ($LASTEXITCODE -ne 0) {
        throw 'uv sync failed'
    }

    Write-Host '[2/2] Building with Nuitka'
    
    # Build options using array for clarity
    $nuitkaOptions = @(
        '--onefile',
        '--enable-plugin=tk-inter',
        '--windows-console-mode=attach',
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

    Write-Host 'Build successful!'
    Write-Host "Output: $OutputDir/$OutputFileName.exe"
    } finally {
        Pop-Location
    }
}
