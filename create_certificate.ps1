# create_certificate.ps1 - Create a self-signed certificate for code signing and export as .cer
#
# Usage:
#   .\create_certificate.ps1

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path

# Certificate configuration
$certName = "PythonPackageDownloader"
$orgName = "YourOrganization"
$country = "JP"
$distDir = Join-Path $root "dist"
$cerPath = Join-Path $distDir "$certName.cer"
$pfxPassword = "YourPassword123"

# Create dist directory
if (-not (Test-Path $distDir)) {
    New-Item -ItemType Directory -Path $distDir | Out-Null
    Write-Host "Created directory: $distDir"
}

Push-Location $root
try {
    # Check if certificate already exists in Personal store
    $existingCerts = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }
    
    if ($null -ne $existingCerts) {
        # Sort by NotAfter to get the newest one
        $existingCert = $existingCerts | Sort-Object -Property NotAfter -Descending | Select-Object -First 1
        Write-Host "Certificate already exists:"
        Write-Host "  Subject: $($existingCert.Subject)"
        Write-Host "  Thumbprint: $($existingCert.Thumbprint)"
        Write-Host "  Valid Until: $($existingCert.NotAfter)"
        
        # Check if .cer file exists, if not export it
        if (-not (Test-Path $cerPath)) {
            Write-Host "`nExporting certificate to .cer format..."
            Export-Certificate -Cert $existingCert -FilePath $cerPath -Type CERT | Out-Null
            Write-Host "Certificate exported: $cerPath"
        } else {
            Write-Host "Certificate .cer file already exists: $cerPath"
        }
    } else {
        Write-Host 'Creating self-signed certificate...'
        
        # Create certificate with explicit TextExtensions (matching pandoc_gui approach)
        # This ensures proper certificate structure for MSIX
        $cert = New-SelfSignedCertificate `
            -Type Custom `
            -Subject "CN=$certName" `
            -KeyAlgorithm RSA `
            -KeyLength 2048 `
            -KeyExportPolicy Exportable `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -NotAfter (Get-Date).AddYears(5) `
            -HashAlgorithm SHA256 `
            -KeyUsage DigitalSignature `
            -TextExtension @(
                '2.5.29.37={text}1.3.6.1.5.5.7.3.3',  # Enhanced Key Usage: Code Signing
                '2.5.29.19={text}'                      # Basic Constraints: CA=FALSE
            )
        
        Write-Host "Certificate created:"
        Write-Host "  Subject: $($cert.Subject)"
        Write-Host "  Thumbprint: $($cert.Thumbprint)"
        Write-Host "  Valid Until: $($cert.NotAfter)"
        
        # Add to TrustedPeople store (for MSIX installation)
        # Note: Root store requires admin rights and is not strictly needed for MSIX
        Write-Host "`nAdding certificate to TrustedPeople store..."
        
        try {
            $trustedStore = New-Object System.Security.Cryptography.X509Certificates.X509Store("TrustedPeople", "CurrentUser")
            $trustedStore.Open([System.Security.Cryptography.X509Certificates.OpenFlags]::ReadWrite)
            $trustedStore.Add($cert)
            $trustedStore.Close()
            Write-Host "  ✓ Added to TrustedPeople"
        } catch {
            Write-Host "  ⚠ Failed to add to TrustedPeople: $_"
        }
        
        # Export to CER
        Write-Host "`nExporting certificate to CER format..."
        Export-Certificate -Cert $cert -FilePath $cerPath -Type CERT | Out-Null
        Write-Host "Certificate exported: $cerPath"
    }
    
    Write-Host "`nCertificate setup completed successfully!"
    Write-Host "CER file: $cerPath"
    Write-Host "`nNote: Certificate is stored in Personal store and will be used for signing."
    
} finally {
    Pop-Location
}
