# diagnose_signing.ps1 - Comprehensive signing diagnostic

$ErrorActionPreference = 'Stop'

$root = Split-Path -Parent $MyInvocation.MyCommand.Path
$certName = "PythonPackageDownloader"
$pfxPassword = "YourPassword123"

Write-Host "=== MSIX Signing Diagnostic ===" -ForegroundColor Cyan

# 1. Check certificate
Write-Host "`n[1] Certificate Check:" -ForegroundColor Yellow
$certs = Get-ChildItem Cert:\CurrentUser\My | Where-Object { $_.Subject -like "*CN=$certName*" }
if ($null -eq $certs) {
    Write-Host "✗ Certificate not found"
    exit 1
}

$cert = $certs | Sort-Object -Property NotAfter -Descending | Select-Object -First 1
Write-Host "  Subject: $($cert.Subject)"
Write-Host "  Thumbprint: $($cert.Thumbprint)"
Write-Host "  NotBefore: $($cert.NotBefore)"
Write-Host "  NotAfter: $($cert.NotAfter)"
Write-Host "  HasPrivateKey: $($cert.HasPrivateKey)"

if (-not $cert.HasPrivateKey) {
    Write-Host "✗ Certificate does not have private key!"
    exit 1
}

# 2. Export PFX with different methods
Write-Host "`n[2] PFX Export Test:" -ForegroundColor Yellow
$tempDir = [System.IO.Path]::GetTempPath()

$methods = @(
    @{ Name = "Method 1: Basic export"; Params = @() },
    @{ Name = "Method 2: ChainOption BuildChain"; Params = @{ ChainOption = 'BuildChain' } },
    @{ Name = "Method 3: ChainOption EndEntityCertOnly"; Params = @{ ChainOption = 'EndEntityCertOnly' } }
)

$securePassword = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
$pfxFiles = @()

foreach ($method in $methods) {
    $tempPfxFile = Join-Path $tempDir "test_$(Get-Random).pfx"
    try {
        $params = @{
            Cert = $cert
            FilePath = $tempPfxFile
            Password = $securePassword
            Force = $true
            ErrorAction = 'Stop'
        } + $method.Params
        
        Export-PfxCertificate @params | Out-Null
        $fileInfo = Get-Item $tempPfxFile
        Write-Host "  ✓ $($method.Name): $($fileInfo.Length) bytes"
        $pfxFiles += $tempPfxFile
    } catch {
        Write-Host "  ✗ $($method.Name): $_"
    }
}

# 3. Test signing a simple file
Write-Host "`n[3] Test Signing:" -ForegroundColor Yellow

# Create a test file
$testFile = Join-Path $tempDir "test_$(Get-Random).txt"
"Test content" | Out-File -FilePath $testFile -Encoding UTF8

$attempts = @(
    @{ Name = "signtool with basic PFX"; Cmd = "signtool sign /f `"$($pfxFiles[0])`" /p $pfxPassword /fd sha256 `"$testFile`"" },
    @{ Name = "signtool with verbose"; Cmd = "signtool sign /v /f `"$($pfxFiles[0])`" /p $pfxPassword /fd sha256 `"$testFile`"" },
    @{ Name = "signtool with /a"; Cmd = "signtool sign /a /f `"$($pfxFiles[0])`" /p $pfxPassword /fd sha256 `"$testFile`"" }
)

foreach ($attempt in $attempts) {
    Write-Host "  Testing: $($attempt.Name)"
    $output = Invoke-Expression $attempt.Cmd 2>&1
    if ($LASTEXITCODE -eq 0) {
        Write-Host "    ✓ Success!"
        $output | ForEach-Object { Write-Host "      $_" }
        break
    } else {
        Write-Host "    ✗ Failed (exit code: $LASTEXITCODE)"
        $output | Select-Object -First 3 | ForEach-Object { Write-Host "      $_" }
    }
}

# 4. Check cert extensions
Write-Host "`n[4] Certificate Extensions:" -ForegroundColor Yellow
foreach ($ext in $cert.Extensions) {
    $line = "  $($ext.Oid.FriendlyName)"
    if ($ext.Oid.FriendlyName -eq "Enhanced Key Usage") {
        $eku = [System.Security.Cryptography.X509Certificates.X509EnhancedKeyUsageExtension]$ext
        $line += ": "
        $line += ($eku.EnhancedKeyUsages | ForEach-Object { $_.FriendlyName }) -join ", "
    }
    Write-Host $line
}

# 5. Cleanup
Write-Host "`n[5] Cleanup:" -ForegroundColor Yellow
$pfxFiles | ForEach-Object {
    if (Test-Path $_) {
        Remove-Item -Path $_ -Force -ErrorAction SilentlyContinue
        Write-Host "  Deleted: $_"
    }
}
if (Test-Path $testFile) {
    Remove-Item -Path $testFile -Force -ErrorAction SilentlyContinue
}

Write-Host "`n=== Diagnostic Complete ===" -ForegroundColor Cyan
