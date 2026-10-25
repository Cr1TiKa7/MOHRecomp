# Run smoke tests against a local build.
# Usage:  pwsh -File tools/run-smoke.ps1 [-Build dev|release] [-Test boot|intro|menu|coverage|level|all] [-Port 4370]
# 'all' runs boot, intro, menu, coverage and level in that order and stops at the first failure.
param(
    [ValidateSet('dev', 'release')][string]$Build = 'dev',
    [ValidateSet('boot', 'intro', 'menu', 'coverage', 'level', 'all')][string]$Test = 'boot',
    [int]$Port = 4370
)

. D:\RecompDev\dev-env.ps1

$repo = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $repo "build-$Build\MOH_Recompiled.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Error "no exe under build-$Build" -ErrorAction Continue
    exit 1
}

$tests = if ($Test -eq 'all') { @('boot', 'intro', 'menu', 'coverage', 'level') } else { @($Test) }
foreach ($t in $tests) {
    py -3 (Join-Path $repo "tests\smoke\${t}_smoke.py") --exe $exe --cue $env:MOH_CUE --port $Port
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
