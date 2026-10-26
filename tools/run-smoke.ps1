# Run smoke tests against a local build.
# Usage:  pwsh -File tools/run-smoke.ps1 [-Build dev|release] [-Test boot|intro|menu|coverage|level|save|all] [-Port 4370]
# 'all' runs boot, intro, menu, coverage and level in that order and stops at the first failure.
# 'save' needs the local fixture card (a save made after Mission 1 Level 1); it is
# skipped with a hint when the fixture is missing and is not part of 'all'.
param(
    [ValidateSet('dev', 'release')][string]$Build = 'dev',
    [ValidateSet('boot', 'intro', 'menu', 'coverage', 'level', 'save', 'all')][string]$Test = 'boot',
    [int]$Port = 4370
)

. D:\RecompDev\dev-env.ps1

$repo = Split-Path -Parent $PSScriptRoot
$exe = Join-Path $repo "build-$Build\MOH_Recompiled.exe"
if (-not (Test-Path -LiteralPath $exe)) {
    Write-Error "no exe under build-$Build" -ErrorAction Continue
    exit 1
}

$fixture = 'D:\RecompDev\fixtures\moh-m1l1-complete.mcd'
if ($Test -eq 'save') {
    if (-not (Test-Path -LiteralPath $fixture)) {
        Write-Host "save: skipped - fixture card missing ($fixture). Play Mission 1 Level 1, save, copy saves\card1.mcd there."
        exit 0
    }
    py -3 (Join-Path $repo 'tests\smoke\save_smoke.py') --exe $exe --cue $env:MOH_CUE --card $fixture --port $Port
    exit $LASTEXITCODE
}

$tests = if ($Test -eq 'all') { @('boot', 'intro', 'menu', 'coverage', 'level') } else { @($Test) }
foreach ($t in $tests) {
    py -3 (Join-Path $repo "tests\smoke\${t}_smoke.py") --exe $exe --cue $env:MOH_CUE --port $Port
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
