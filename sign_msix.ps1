# sign_msix.ps1 - Sign MSIX package
#
# Usage:
#   .\sign_msix.ps1
#   .\sign_msix.ps1 -MsixPath "dist/custom.msix"

param(
    [string]$MsixPath = "dist/PythonPackageDownloader.msix"
)

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Certificate configuration
$certName = "PythonPackageDownloader"
$distDir = Join-Path $root "dist"
$distCerPath = Join-Path $distDir "$certName.cer"
$tempPfxPath = Join-Path $env:TEMP "$certName.pfx"
$pfxPassword = "YourPassword123"

# Resolve full path
$msixPath = Join-Path $root $MsixPath

# Helper function to ensure dist directory exists
function Ensure-DistDirectory {
    if (-not (Test-Path $distDir)) {
        New-Item -ItemType Directory -Path $distDir -Force | Out-Null
    }
}

Push-Location $root
try {
    # Check if MSIX file exists
    if (-not (Test-Path $msixPath)) {
        throw "MSIX file not found: $msixPath"
    }
    
    # Check if certificate exists in Personal store (use newest if multiple exist)
    $certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }
    if ($null -eq $certs) {
        throw "Certificate not found in Personal store. Run create_certificate.ps1 first."
    }
    
    $cert = $certs | Sort-Object -Property NotAfter -Descending | Select-Object -First 1
    Write-Host '[1/2] Signing MSIX package'
    Write-Host "MSIX file: $msixPath"
    Write-Host "Certificate: $($cert.Thumbprint)"
    Write-Host "  Subject: $($cert.Subject)"
    Write-Host "  Valid Until: $($cert.NotAfter)"
    
    # Verify MSIX file exists and is readable
    if (-not (Test-Path $msixPath)) {
        throw "MSIX file not found: $msixPath"
    }
    $fileInfo = Get-Item $msixPath
    Write-Host "  MSIX File Size: $($fileInfo.Length) bytes"
    
    # Export certificate to dist directory first
    Ensure-DistDirectory
    Write-Host 'Exporting certificate to dist directory...'
    Export-Certificate -Cert $cert -FilePath $distCerPath -Type CERT -Force | Out-Null
    Write-Host "✓ Certificate exported: $distCerPath"
    
    # Use pandoc_gui's proven sign_code.ps1 approach
    # Pass Thumbprint instead of Subject to avoid mismatch issues
    $signCodeScript = Join-Path $root 'sign_code.ps1'
    if (-not (Test-Path $signCodeScript)) {
        throw "sign_code.ps1 not found: $signCodeScript"
    }
    
    Write-Host ''
    & $signCodeScript `
        -FilePath $msixPath `
        -Thumbprint $cert.Thumbprint `
        -ExportCerPath $distCerPath `
        -TimestampServer 'http://timestamp.digicert.com' `
        -HashAlgorithm 'SHA256'
    
    Write-Host '[2/2] Summary'
    Write-Host "`nMSIX package signed successfully!"
    Write-Host "Output: $msixPath"
    if (Test-Path $cerPath) {
        Write-Host "Certificate: $cerPath"
    }
    
} finally {
    Pop-Location
}
