# diagnose_cert.ps1 - Diagnose certificate properties for MSIX signing

$ErrorActionPreference = 'Stop'

$certName = "PythonPackageDownloader"

Write-Host "=== Certificate Diagnostic ===" -ForegroundColor Cyan

# Get certificate from Personal store
$certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }

if ($null -eq $certs) {
    Write-Host "✗ Certificate not found: $certName"
    exit 1
}

$cert = $certs | Sort-Object -Property NotAfter -Descending | Select-Object -First 1

Write-Host "`n[1] Basic Properties:"
Write-Host "  Subject: $($cert.Subject)"
Write-Host "  Thumbprint: $($cert.Thumbprint)"
Write-Host "  Issuer: $($cert.Issuer)"
Write-Host "  Valid From: $($cert.NotBefore)"
Write-Host "  Valid Until: $($cert.NotAfter)"
Write-Host "  Public Key Algorithm: $($cert.PublicKey.Oid.FriendlyName)"
Write-Host "  Signature Algorithm: $($cert.SignatureAlgorithm.FriendlyName)"

Write-Host "`n[2] Key Usage Extensions:"
$certExtensions = $cert.Extensions
foreach ($ext in $certExtensions) {
    if ($ext.Oid.FriendlyName -like "*Key Usage*") {
        Write-Host "  ✓ Found: $($ext.Oid.FriendlyName)"
        Write-Host "    Value: $ext"
    }
    if ($ext.Oid.FriendlyName -like "*Extended Key Usage*") {
        Write-Host "  ✓ Found: $($ext.Oid.FriendlyName)"
        $eku = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ext
        foreach ($oid in $eku.EnhancedKeyUsages) {
            Write-Host "    - $($oid.FriendlyName) ($($oid.Value))"
        }
    }
}

# Check for code signing capability
$hasCodeSigning = $false
$extKeyUsageExt = $cert.Extensions | Where-Object { $_.Oid.FriendlyName -eq "Enhanced Key Usage" }
if ($null -ne $extKeyUsageExt) {
    $eku = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$extKeyUsageExt
    $hasCodeSigning = $eku.EnhancedKeyUsages | Where-Object { $_.FriendlyName -eq "Code Signing" -or $_.Value -eq "1.3.6.1.5.5.7.3.3" }
}

Write-Host "`n[3] Signing Capability:"
if ($hasCodeSigning) {
    Write-Host "  ✓ Code Signing: Supported"
} else {
    Write-Host "  ✗ Code Signing: NOT FOUND"
    Write-Host "  WARNING: Certificate may not support code signing!"
}

Write-Host "`n[4] Testing Signature Verification:"
# Test with signtool to verify basic operation
Write-Host "  Running: signtool verify /c $($cert.Thumbprint)"
& signtool verify /c "$($cert.Thumbprint)" 2>&1 | ForEach-Object { Write-Host "    $_" }

if ($LASTEXITCODE -eq 0) {
    Write-Host "  ✓ Certificate is valid"
} else {
    Write-Host "  ✗ Certificate verification failed (exit code: $LASTEXITCODE)"
}

Write-Host "`n=== Diagnostic Complete ===" -ForegroundColor Cyan
