# Run the boot smoke test against a local build.
# Usage:  pwsh -File tools/run-smoke.ps1 [-Build dev|release] [-Port 4370]
param(
    [ValidateSet('dev', 'release')][string]$Build = 'dev',
    [int]$Port = 4370
)

. D:\RecompDev\dev-env.ps1

$repo = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $repo "build-$Build\MOH_Recompiled.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Error "no exe under build-$Build" -ErrorAction Continue
    exit 1
}

py -3 (Join-Path $repo 'tests\smoke\boot_smoke.py') --exe $exe --cue $env:MOH_CUE --port $Port
exit $LASTEXITCODE
