# build_and_package.ps1 - Build EXE and MSIX packages with Nuitka and sign both
#
# Usage:
#   .\build_and_package.ps1
#   .\build_and_package.ps1 -ExeOnly          # Build and sign EXE only
#   .\build_and_package.ps1 -MsixOnly         # Build and sign MSIX only

param(
    [switch]$ExeOnly,
    [switch]$MsixOnly
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Source the build_nuitka.ps1 to get the Ensure-LLVMInstalled function
. (Join-Path $root 'build_nuitka.ps1')

# Ensure LLVM is installed
Ensure-LLVMInstalled

# Configuration
$OutputDir = 'dist'
$OutputFileName = 'PythonPackageDownloader'
$EntryScript = 'python_package_downloader.py'
$AppVersion = '1.1.1.0'  # Update this for each release

# Certificate configuration
$certName = "PythonPackageDownloader"
$certDir = Join-Path $root "dist"
$cerPath = Join-Path $certDir "$certName.cer"
$tempPfxPath = Join-Path $env:TEMP "$certName.pfx"
$pfxPassword = "YourPassword123"

# EXE configuration
$appPath = Join-Path $root "$OutputDir\$OutputFileName.exe"

# MSIX configuration
$msixDir = Join-Path $root "msix_build"
$msixPackageDir = Join-Path $msixDir "Package"
$msixSource = Join-Path $msixDir "Package"
$msixOutput = Join-Path $OutputDir "$OutputFileName.msix"
$appxManifest = Join-Path $root "AppxManifest.xml"

# Create certificate directory
if (-not (Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

Push-Location $root
try {
    # Clean up previous builds
    Write-Host 'Cleaning up previous build artifacts...'
    if (Test-Path $OutputDir) {
        Remove-Item -Path $OutputDir -Recurse -Force
    }
    if (Test-Path $msixDir) {
        Remove-Item -Path $msixDir -Recurse -Force
    }
    
    # Determine build mode
    $buildExe = -not $MsixOnly
    $buildMsix = -not $ExeOnly
    
    if ($buildExe) {
        Write-Host '========== EXE BUILD & SIGN =========='
        
        Write-Host '[1/4] Installing dependencies with uv'
        & uv sync --group build
        if ($LASTEXITCODE -ne 0) {
            throw 'uv sync failed'
        }

        Write-Host '[2/4] Building with Nuitka'
        
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

        Write-Host '[3/4] Code signing EXE'
        
        # Get certificate from Personal store (use newest if multiple exist)
        $certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }
        if ($null -eq $certs) {
            Write-Host 'Certificate not found. Creating self-signed certificate...'
            & (Join-Path $root 'create_certificate.ps1')
            $certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }
        }
        
        $cert = $certs | Sort-Object -Property NotAfter -Descending | Select-Object -First 1
        Write-Host "Using certificate: $($cert.Thumbprint)"
        Write-Host "  Subject: $($cert.Subject)"
        Write-Host "  Valid Until: $($cert.NotAfter)"

        # Export certificate to temporary PFX for signing
        $tempDir = [System.IO.Path]::GetTempPath()
        $tempPfxFile = Join-Path $tempDir "exe_sign_temp_$(Get-Random).pfx"
        
        Write-Host '[3/4] Code signing executable'
        Write-Host 'Exporting certificate to temporary PFX...'
        $securePassword = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
        
        try {
            Export-PfxCertificate -Cert $cert -FilePath $tempPfxFile -Password $securePassword -Force -ErrorAction Stop | Out-Null
            Write-Host "  ✓ PFX exported: $tempPfxFile"
        } catch {
            Write-Host "  ✗ PFX export failed: $_"
            throw 'Certificate export failed'
        }
        
        # Sign EXE with PFX file
        & signtool sign /f $tempPfxFile /p $pfxPassword /fd sha256 /d "Python Package Downloader" $appPath 2>&1
        if ($LASTEXITCODE -ne 0) {
            if (Test-Path $tempPfxFile) {
                Remove-Item -Path $tempPfxFile -Force -ErrorAction SilentlyContinue
            }
            throw 'EXE signing failed'
        }
        
        # Clean up temporary PFX
        if (Test-Path $tempPfxFile) {
            Remove-Item -Path $tempPfxFile -Force -ErrorAction SilentlyContinue
        }

        Write-Host '[4/4] Verifying EXE signature'
        & signtool verify /pa $appPath
        if ($LASTEXITCODE -eq 0) {
            Write-Host 'EXE verification successful'
        } else {
            Write-Host 'Warning: EXE signature verification failed (normal for self-signed certificate)'
        }
        
        # Export certificate to dist directory
        Write-Host 'Exporting certificate to dist directory...'
        Export-Certificate -Cert $cert -FilePath $cerPath -Type CERT -Force | Out-Null
        Write-Host "✓ Certificate exported: $cerPath"

        Write-Host "EXE build completed: $appPath`n"
    }
    
    if ($buildMsix) {
        Write-Host '========== MSIX BUILD & SIGN =========='
        
        Write-Host '[1/6] Preparing MSIX package structure'
        
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
        
        # Copy required data directories
        Copy-Item -Path "help" -Destination $msixPackageDir -Recurse -ErrorAction SilentlyContinue
        Copy-Item -Path "locales" -Destination $msixPackageDir -Recurse -ErrorAction SilentlyContinue
        Write-Host "Copied data directories (help, locales)"
        
        # Copy required data files
        Copy-Item -Path "config.json" -Destination $msixPackageDir -ErrorAction SilentlyContinue
        Copy-Item -Path "loggingex_config.json" -Destination $msixPackageDir -ErrorAction SilentlyContinue
        Copy-Item -Path "pyproject.toml" -Destination $msixPackageDir -ErrorAction SilentlyContinue
        Write-Host "Copied data files (config.json, loggingex_config.json, pyproject.toml)"
        
        # Copy and update AppxManifest.xml
        $manifest = Get-Content -Path $appxManifest -Raw -Encoding UTF8
        # Remove BOM if present
        $manifest = $manifest -replace '^\uFEFF', ''
        
        # Update version in manifest - only in the <Identity> tag
        $manifest = $manifest -replace '(<Identity[^>]*Version=")[^"]*(")', "`${1}$AppVersion`${2}"
        
        # Replace PLACEHOLDER values
        $manifest = $manifest -replace 'PLACEHOLDER_IDENTITY_NAME', 'python.package.downloader'
        $manifest = $manifest -replace 'PLACEHOLDER_PUBLISHER_CN', 'PythonPackageDownloader'
        $manifest = $manifest -replace 'PLACEHOLDER_PUBLISHER_NAME', 'PythonPackageDownloader'
        
        # Save updated manifest to MSIX package (use UTF-8 without BOM)
        $manifestPath = Join-Path $msixPackageDir "AppxManifest.xml"
        $utf8NoBOM = [System.Text.UTF8Encoding]::new($false)
        [System.IO.File]::WriteAllText($manifestPath, $manifest, $utf8NoBOM)
        Write-Host "Created AppxManifest.xml"
        
        Write-Host '[2/6] Verifying certificate for MSIX signing'
        
        # Get certificate from Personal store (use newest if multiple exist)
        $certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }
        if ($null -eq $certs) {
            throw "Certificate not found. Run create_certificate.ps1 first."
        }
        
        $cert = $certs | Sort-Object -Property NotAfter -Descending | Select-Object -First 1
        Write-Host "Using certificate: $($cert.Thumbprint)"
        Write-Host "  Subject: $($cert.Subject)"
        Write-Host "  Valid Until: $($cert.NotAfter)"
        
        Write-Host '[3/6] Creating MSIX package'
        
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
        
        Write-Host '[4/6] Code signing MSIX'
        
        Write-Host 'Preparing certificate for signing...'
        Write-Host "  Certificate Thumbprint: $($cert.Thumbprint)"
        Write-Host "  Certificate Subject: $($cert.Subject)"
        
        # Export certificate to dist directory first
        Write-Host 'Exporting certificate to dist directory...'
        Export-Certificate -Cert $cert -FilePath $cerPath -Type CERT -Force | Out-Null
        Write-Host "✓ Certificate exported: $cerPath"
        
        # Use pandoc_gui's proven sign_code.ps1 approach
        # Pass Thumbprint instead of Subject to avoid mismatch issues
        $signCodeScript = Join-Path $root 'sign_code.ps1'
        if (-not (Test-Path $signCodeScript)) {
            throw "sign_code.ps1 not found: $signCodeScript"
        }
        
        Write-Host ''
        & $signCodeScript `
            -FilePath $msixOutput `
            -Thumbprint $cert.Thumbprint `
            -ExportCerPath $cerPath `
            -TimestampServer 'http://timestamp.digicert.com' `
            -HashAlgorithm 'SHA256'
        
        if ($LASTEXITCODE -ne 0) {
            Write-Host "⚠ MSIX signing completed with warnings"
        }
        
        Write-Host '[5/6] Summary'
        
        Write-Host "`nMSIX package created successfully!"
        Write-Host "Output: $msixOutput"
    }
    
    Write-Host "`n========== BUILD COMPLETED =========="
    
    # Ensure dist directory exists
    if (-not (Test-Path $OutputDir)) {
        New-Item -ItemType Directory -Path $OutputDir | Out-Null
    }
    
    if ($buildExe) {
        Write-Host "✓ EXE: $appPath"
    }
    if ($buildMsix) {
        Write-Host "✓ MSIX: $msixOutput"
    }
    if (Test-Path $cerPath) {
        Write-Host "✓ Certificate: $cerPath"
    }
    
} finally {
    Pop-Location
}
