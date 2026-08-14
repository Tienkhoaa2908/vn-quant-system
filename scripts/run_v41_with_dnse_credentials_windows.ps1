[CmdletBinding()]
param(
    [string]$RepositoryRoot = ""
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SecretRoot = Join-Path $env:LOCALAPPDATA "vn-quant-system\secrets"
$ApiKeyPath = Join-Path $SecretRoot "dnse_api_key.dpapi"
$ApiSecretPath = Join-Path $SecretRoot "dnse_api_secret.dpapi"

function Convert-SecureStringToPlainText {
    param([Parameter(Mandatory = $true)][System.Security.SecureString]$Value)

    $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
    try {
        return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
    }
    finally {
        [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
    }
}

if (-not (Test-Path -LiteralPath $ApiKeyPath) -or -not (Test-Path -LiteralPath $ApiSecretPath)) {
    throw "DNSE_DPAPI_CREDENTIALS_NOT_FOUND: run scripts/setup_dnse_credentials_windows.ps1 first"
}

if ([string]::IsNullOrWhiteSpace($RepositoryRoot)) {
    $RepositoryRoot = Split-Path -Parent $PSScriptRoot
}
$RepositoryRoot = (Resolve-Path -LiteralPath $RepositoryRoot).Path
$RunnerPath = Join-Path $RepositoryRoot "scripts\run_v41_hnx_cross_market_gitbash.sh"
if (-not (Test-Path -LiteralPath $RunnerPath)) {
    throw "V41_RUNNER_NOT_FOUND:$RunnerPath"
}

$bashCommand = Get-Command bash.exe -ErrorAction SilentlyContinue
if ($null -eq $bashCommand) {
    $candidates = @(
        "C:\Program Files\Git\bin\bash.exe",
        "C:\Program Files\Git\usr\bin\bash.exe"
    )
    $bashPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
else {
    $bashPath = $bashCommand.Source
}
if ([string]::IsNullOrWhiteSpace($bashPath)) {
    throw "GIT_BASH_NOT_FOUND"
}

$apiKeySecure = ConvertTo-SecureString -String (Get-Content -LiteralPath $ApiKeyPath -Raw)
$apiSecretSecure = ConvertTo-SecureString -String (Get-Content -LiteralPath $ApiSecretPath -Raw)
$apiKeyPlain = Convert-SecureStringToPlainText -Value $apiKeySecure
$apiSecretPlain = Convert-SecureStringToPlainText -Value $apiSecretSecure

if ([string]::IsNullOrWhiteSpace($apiKeyPlain) -or [string]::IsNullOrWhiteSpace($apiSecretPlain)) {
    throw "DNSE_DPAPI_CREDENTIALS_EMPTY"
}

$previousKey = $env:DNSE_API_KEY
$previousSecret = $env:DNSE_API_SECRET
$previousSource = $env:VN_QUANT_CREDENTIAL_SOURCE
$exitCode = 2

try {
    # Plaintext exists only in this PowerShell process and the V41 child process.
    $env:DNSE_API_KEY = $apiKeyPlain
    $env:DNSE_API_SECRET = $apiSecretPlain
    $env:VN_QUANT_CREDENTIAL_SOURCE = "WINDOWS_DPAPI_CURRENT_USER"

    Write-Host "DNSE credentials loaded from Windows DPAPI for this process only."
    Write-Host "Starting V41 with DNSE OpenAPI. Credentials will not be printed."

    Push-Location $RepositoryRoot
    try {
        & $bashPath $RunnerPath
        $exitCode = $LASTEXITCODE
    }
    finally {
        Pop-Location
    }
}
finally {
    if ($null -eq $previousKey) { Remove-Item Env:DNSE_API_KEY -ErrorAction SilentlyContinue }
    else { $env:DNSE_API_KEY = $previousKey }

    if ($null -eq $previousSecret) { Remove-Item Env:DNSE_API_SECRET -ErrorAction SilentlyContinue }
    else { $env:DNSE_API_SECRET = $previousSecret }

    if ($null -eq $previousSource) { Remove-Item Env:VN_QUANT_CREDENTIAL_SOURCE -ErrorAction SilentlyContinue }
    else { $env:VN_QUANT_CREDENTIAL_SOURCE = $previousSource }

    $apiKeyPlain = $null
    $apiSecretPlain = $null
    $apiKeySecure.Dispose()
    $apiSecretSecure.Dispose()
}

exit $exitCode
