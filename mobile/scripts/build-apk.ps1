param(
    [switch]$Release
)

$ErrorActionPreference = 'Stop'
$mobileRoot = Split-Path -Parent $PSScriptRoot
$configPath = Join-Path $mobileRoot 'config\supabase.local.json'

if (-not (Test-Path -LiteralPath $configPath)) {
    throw "Missing $configPath. Copy config/supabase.example.json to config/supabase.local.json and fill in the client-safe Supabase values."
}

$config = Get-Content -Raw -LiteralPath $configPath | ConvertFrom-Json
if ([string]::IsNullOrWhiteSpace($config.SUPABASE_URL) -or
    [string]::IsNullOrWhiteSpace($config.SUPABASE_ANON_KEY) -or
    $config.SUPABASE_URL -notmatch '^https://') {
    throw 'config/supabase.local.json must contain a valid SUPABASE_URL and SUPABASE_ANON_KEY.'
}

$mode = if ($Release) { '--release' } else { '--debug' }
Push-Location $mobileRoot
try {
    & flutter build apk $mode --dart-define-from-file=config/supabase.local.json
    if ($LASTEXITCODE -ne 0) {
        throw "Flutter APK build failed with exit code $LASTEXITCODE."
    }
}
finally {
    Pop-Location
}
