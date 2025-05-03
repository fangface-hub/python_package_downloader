# PyInstallerでビルドし、自己証明書で署名するPowerShellスクリプト
# 管理者権限で実行してください

$ErrorActionPreference = "Stop"

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "PyInstaller Build and Sign Start" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
Write-Host ""

# 設定 - 必要に応じて変更してください
$certName = "PythonPackageDownloader"
$orgName = "YourOrganization"
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$outDir = $scriptDir
$appPath = Join-Path $outDir "dist\PythonPackageDownloader\PythonPackageDownloader.exe"

# 証明書ディレクトリ
$certDir = Join-Path $outDir "certificates"
$pfxPath = Join-Path $certDir "$certName.pfx"
$pfxPassword = "YourPassword123"

# 証明書ディレクトリの作成
if (-not (Test-Path $certDir)) {
    New-Item -ItemType Directory -Path $certDir | Out-Null
}

# [1/4] PyInstallerでビルド
Write-Host "[1/4] Building with PyInstaller..." -ForegroundColor Yellow
try {
    & pyinstaller --noconfirm PythonPackageDownloader.spec
    if ($LASTEXITCODE -ne 0) {
        throw "PyInstaller build failed"
    }
    Write-Host "Build completed" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    pause
    exit 1
}

# [2/4] 証明書の作成または取得
if (-not (Test-Path $pfxPath)) {
    Write-Host "[2/4] Creating self-signed certificate..." -ForegroundColor Yellow
    
    try {
        # 自己署名証明書の作成
        $cert = New-SelfSignedCertificate `
            -Type CodeSigningCert `
            -Subject "CN=$certName, O=$orgName, C=JP" `
            -KeyExportPolicy Exportable `
            -CertStoreLocation "Cert:\CurrentUser\My" `
            -NotAfter (Get-Date).AddYears(5) `
            -HashAlgorithm SHA256
        
        # PFXファイルとしてエクスポート
        $securePassword = ConvertTo-SecureString -String $pfxPassword -Force -AsPlainText
        Export-PfxCertificate -Cert $cert -FilePath $pfxPath -Password $securePassword | Out-Null
        
        # 証明書ストアから削除
        Remove-Item -Path "Cert:\CurrentUser\My\$($cert.Thumbprint)" -Force
        
        Write-Host "Certificate created successfully" -ForegroundColor Green
        Write-Host ""
    } catch {
        Write-Host "Error: Certificate creation failed - $_" -ForegroundColor Red
        pause
        exit 1
    }
} else {
    Write-Host "[2/4] Using existing certificate" -ForegroundColor Yellow
    Write-Host ""
}

# [3/4] 実行ファイルに署名
Write-Host "[3/4] Signing executable..." -ForegroundColor Yellow
try {
    $signArgs = @(
        "sign",
        "/fd", "sha256",
        "/f", $pfxPath,
        "/p", $pfxPassword,
        "/t", "http://timestamp.digicert.com",
        $appPath
    )
    
    & signtool @signArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Signing failed"
    }
    Write-Host "Signing completed" -ForegroundColor Green
    Write-Host ""
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    pause
    exit 1
}

# [4/4] 署名の検証
Write-Host "[4/4] Verifying signature..." -ForegroundColor Yellow
& signtool verify /pa $appPath
if ($LASTEXITCODE -ne 0) {
    Write-Host "Warning: Signature verification failed (normal for self-signed certificate)" -ForegroundColor Yellow
} else {
    Write-Host "Verification completed" -ForegroundColor Green
}
Write-Host ""

Write-Host "====================================" -ForegroundColor Cyan
Write-Host "Build and signing completed!" -ForegroundColor Green
Write-Host "Executable: $appPath" -ForegroundColor Cyan
Write-Host "====================================" -ForegroundColor Cyan
pause
