[CmdletBinding()]
param(
    [switch]$ReuseExisting
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$SecretRoot = Join-Path $env:LOCALAPPDATA "vn-quant-system\secrets"
$ApiKeyPath = Join-Path $SecretRoot "dnse_api_key.dpapi"
$ApiSecretPath = Join-Path $SecretRoot "dnse_api_secret.dpapi"
$MetadataPath = Join-Path $SecretRoot "dnse_credentials_metadata.json"

function Set-PrivateAcl {
    param([Parameter(Mandatory = $true)][string]$Path)

    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    $acl = Get-Acl -LiteralPath $Path
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($existing in @($acl.Access)) {
        [void]$acl.RemoveAccessRuleAll($existing)
    }
    $rule = New-Object System.Security.AccessControl.FileSystemAccessRule(
        $identity,
        "FullControl",
        "Allow"
    )
    [void]$acl.AddAccessRule($rule)
    Set-Acl -LiteralPath $Path -AclObject $acl
}

function Test-SecureStringNotEmpty {
    param([Parameter(Mandatory = $true)][System.Security.SecureString]$Value)

    $pointer = [IntPtr]::Zero
    try {
        $pointer = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Value)
        $plain = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($pointer)
        return -not [string]::IsNullOrWhiteSpace($plain)
    }
    finally {
        if ($pointer -ne [IntPtr]::Zero) {
            [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($pointer)
        }
        $plain = $null
    }
}

function Read-RequiredSecret {
    param([Parameter(Mandatory = $true)][string]$Prompt)

    while ($true) {
        $value = Read-Host $Prompt -AsSecureString
        if (Test-SecureStringNotEmpty -Value $value) {
            return $value
        }
        Write-Host "Gia tri khong duoc de trong. Hay nhap lai." -ForegroundColor Yellow
    }
}

if ($ReuseExisting -and (Test-Path -LiteralPath $ApiKeyPath) -and (Test-Path -LiteralPath $ApiSecretPath)) {
    Write-Host "Da tim thay DNSE credentials duoc ma hoa bang Windows DPAPI."
    exit 0
}

Write-Host "===== NHAP DNSE OPENAPI CREDENTIALS ====="
Write-Host "Ky tu se bi an. Khong dan hai khoa vao chat, file .env hoac Git."
Write-Host "Du lieu se duoc ma hoa bang Windows DPAPI cho tai khoan Windows hien tai."

$apiKey = Read-RequiredSecret -Prompt "Nhap DNSE_API_KEY"
$apiSecret = Read-RequiredSecret -Prompt "Nhap DNSE_API_SECRET"

New-Item -ItemType Directory -Path $SecretRoot -Force | Out-Null
Set-PrivateAcl -Path $SecretRoot

$apiKey | ConvertFrom-SecureString | Set-Content -LiteralPath $ApiKeyPath -Encoding ASCII -NoNewline
$apiSecret | ConvertFrom-SecureString | Set-Content -LiteralPath $ApiSecretPath -Encoding ASCII -NoNewline

$metadata = [ordered]@{
    schema_version = "vn_quant_dnse_credentials_dpapi_v1"
    created_utc = [DateTime]::UtcNow.ToString("o")
    windows_principal = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
    protection = "WINDOWS_DPAPI_CURRENT_USER"
    plaintext_persisted = $false
    repository_persisted = $false
}
$metadata | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $MetadataPath -Encoding UTF8

Set-PrivateAcl -Path $ApiKeyPath
Set-PrivateAcl -Path $ApiSecretPath
Set-PrivateAcl -Path $MetadataPath

# Verify that both encrypted files can be decrypted by the current Windows user.
foreach ($path in @($ApiKeyPath, $ApiSecretPath)) {
    $encrypted = Get-Content -LiteralPath $path -Raw
    $secure = ConvertTo-SecureString -String $encrypted
    if (-not (Test-SecureStringNotEmpty -Value $secure)) {
        throw "DNSE_DPAPI_VERIFY_FAILED:$path"
    }
}

$apiKey.Dispose()
$apiSecret.Dispose()
$apiKey = $null
$apiSecret = $null

Write-Host "DNSE credentials da duoc luu ma hoa cuc bo."
Write-Host "Secret store: $SecretRoot"
Write-Host "Khong co plaintext credential nao duoc ghi vao repository."
