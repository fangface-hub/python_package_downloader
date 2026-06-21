# sign_code.ps1 - Sign code/package files with signtool
# Based on pandoc_gui implementation - proven to work with MSIX
#
# Usage examples:
#   ./sign_code.ps1 -FilePath ./PythonPackageDownloader.msix -Subject "CN=PythonPackageDownloader"
#   ./sign_code.ps1 -FilePath ./dist/main_window.dist/PythonPackageDownloader.exe -Thumbprint <THUMBPRINT>
#   ./sign_code.ps1 -FilePath ./PythonPackageDownloader.msix -PfxPath ./certificate.pfx -PfxPassword (Read-Host "PFX password" -AsSecureString)

[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)]
    [string]$FilePath,

    [string]$Subject,
    [string]$Thumbprint,
    [string]$CertStoreLocation = 'Cert:\CurrentUser\My',

    [string]$PfxPath,
    [securestring]$PfxPassword,

    [string]$ExportCerPath,

    [string]$TimestampServer = 'http://timestamp.digicert.com',
    [ValidateSet('SHA256', 'SHA384', 'SHA512')]
    [string]$HashAlgorithm = 'SHA256',
    [string]$SignToolPath
)

$ErrorActionPreference = 'Stop'

function Find-SignTool {
    $kits = Get-ChildItem 'C:\Program Files (x86)\Windows Kits\10\bin' -Directory -ErrorAction SilentlyContinue |
        Sort-Object Name -Descending

    # Prefer x64 signtool from the latest SDK first.
    foreach ($kit in $kits) {
        $candidate = Join-Path $kit.FullName 'x64\signtool.exe'
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    foreach ($kit in $kits) {
        $candidate = Join-Path $kit.FullName 'x86\signtool.exe'
        if (Test-Path -LiteralPath $candidate) {
            return $candidate
        }
    }

    $cmd = Get-Command signtool.exe -ErrorAction SilentlyContinue
    if ($cmd) {
        return $cmd.Source
    }

    return $null
}

function Ensure-ParentDirectory {
    param([Parameter(Mandatory = $true)][string]$Path)

    $parent = Split-Path -Parent $Path
    if ($parent -and -not (Test-Path -LiteralPath $parent)) {
        New-Item -ItemType Directory -Path $parent -Force | Out-Null
    }
}

if (-not (Test-Path -LiteralPath $FilePath)) {
    throw ('File not found: ' + $FilePath)
}

if ($PfxPath -and -not (Test-Path -LiteralPath $PfxPath)) {
    throw ('PFX file not found: ' + $PfxPath)
}

if ($PfxPath -and -not $PfxPassword) {
    throw 'PfxPassword is required when PfxPath is specified.'
}

if (-not $SignToolPath) {
    $SignToolPath = Find-SignTool
}

if (-not $SignToolPath) {
    throw 'signtool.exe was not found. Install Windows SDK or provide -SignToolPath.'
}

$sha1 = $null
$signingCert = $null
if (-not $PfxPath) {
    if ($Thumbprint) {
        $sha1 = ($Thumbprint -replace '\s+', '').ToUpperInvariant()

        $thumbprintCandidates = Get-ChildItem -Path $CertStoreLocation |
            Where-Object {
                $_.Thumbprint.ToUpperInvariant() -eq $sha1
            } |
            Sort-Object NotAfter -Descending

        if ($thumbprintCandidates) {
            $signingCert = $thumbprintCandidates[0]
        }
    } else {
        if (-not $Subject) {
            throw 'Specify either -PfxPath or (-Thumbprint / -Subject).'
        }

        $certCandidates = Get-ChildItem -Path $CertStoreLocation |
            Where-Object {
                $_.HasPrivateKey -and
                $_.NotAfter -gt (Get-Date) -and
                $_.Subject -eq $Subject
            } |
            Sort-Object NotAfter -Descending

        if (-not $certCandidates) {
            throw ('No valid certificate found in store for Subject: ' + $Subject)
        }

        $signingCert = $certCandidates[0]
        $sha1 = $signingCert.Thumbprint.ToUpperInvariant()
    }
}

$target = (Resolve-Path -LiteralPath $FilePath).Path
$args = @('sign', '/fd', $HashAlgorithm, '/td', $HashAlgorithm)
$bstr = $null

if ($TimestampServer) {
    $args += @('/tr', $TimestampServer)
}

if ($PfxPath) {
    $bstr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($PfxPassword)
    $pfxPasswordPlain = [Runtime.InteropServices.Marshal]::PtrToStringUni($bstr)
    $args += @('/f', (Resolve-Path -LiteralPath $PfxPath).Path, '/p', $pfxPasswordPlain)
} else {
    $args += @('/sha1', $sha1)
}

$args += $target

Write-Host ('Using signtool: ' + $SignToolPath)
Write-Host ('Signing file   : ' + $target)

& $SignToolPath @args
if ($LASTEXITCODE -ne 0) {
    $isAppPackage = ($target -match '\.(appx|msix|appxbundle|msixbundle)$')
    if ($isAppPackage -and $LASTEXITCODE -eq 1) {
        Write-Warning 'App package signing failed. If error 0x800700C1 appears, verify OS/SDK support for APPX/MSIX signing and try latest Windows SDK x64 signtool.'
        Write-Warning 'You can also try explicit signtool path via -SignToolPath, and test signing with /debug to inspect SIP/provider errors.'
    }
    throw ('signtool sign failed with exit code ' + $LASTEXITCODE)
}

$isAppPackage = ($target -match '\.(appx|msix|appxbundle|msixbundle)$')
$verifyStdOut = [System.IO.Path]::GetTempFileName()
$verifyStdErr = [System.IO.Path]::GetTempFileName()

try {
    $verifyProcess = Start-Process -FilePath $SignToolPath `
        -ArgumentList @('verify', '/pa', $target) `
        -NoNewWindow -Wait -PassThru `
        -RedirectStandardOutput $verifyStdOut `
        -RedirectStandardError $verifyStdErr

    $verifyOutput = @()
    if (Test-Path -LiteralPath $verifyStdOut) {
        $verifyOutput += Get-Content -LiteralPath $verifyStdOut
    }
    if (Test-Path -LiteralPath $verifyStdErr) {
        $verifyOutput += Get-Content -LiteralPath $verifyStdErr
    }

    $verifyExitCode = $verifyProcess.ExitCode
}
finally {
    Remove-Item -LiteralPath $verifyStdOut -Force -ErrorAction SilentlyContinue
    Remove-Item -LiteralPath $verifyStdErr -Force -ErrorAction SilentlyContinue
}

if ($verifyExitCode -ne 0) {
    $verifyText = ($verifyOutput | Out-String)
    $isUntrustedChainOnly = $verifyText -match '0x800B0109|not trusted by the trust provider|terminated in a root certificate which is not trusted'

    if ($isAppPackage -and $isUntrustedChainOnly) {
        Write-Warning 'signtool verify failed due to untrusted root (expected for self-signed test certificates not installed in Trusted Root).'
        Write-Warning 'Install the test certificate in Trusted Root Certification Authorities to make verify /pa pass strictly.'
    } else {
        throw ('signtool verify failed with exit code ' + $verifyExitCode)
    }
}

if ($bstr) {
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($bstr)
}

if ($ExportCerPath) {
    if (-not $signingCert) {
        Write-Warning 'Skipping CER export: signing certificate was provided by PFX path and cannot be exported from store context.'
    } else {
        Ensure-ParentDirectory -Path $ExportCerPath
        Export-Certificate -Cert $signingCert -FilePath $ExportCerPath -Force | Out-Null
        Write-Host ('Exported CER: ' + $ExportCerPath)
    }
}

Write-Host 'Done. File signed and verified.'
