# Run smoke tests against a local build.
# Usage:  pwsh -File tools/run-smoke.ps1 [-Build dev|release] [-Test boot|intro|menu|coverage|level|save|sweep|coverage-long|mp|mouse|widescreen|pgxp|all] [-Port 4370]
# 'all' runs boot, intro, menu, coverage and level in that order and stops at the first failure.
# 'save' needs the local fixture card (a save made after Mission 1 Level 1); it is
# skipped with a hint when the fixture is missing and is not part of 'all'.
# 'sweep' jumps into every single-player level (~3 min each; -Mission N limits it,
# -Bonus sweeps the MSN12 folders instead, most likely the multiplayer arenas); it is not part of 'all'.
# 'coverage-long' measures ~10 min each of videos, menus and levels (~45 min); not part of 'all'.
# 'mp' plugs a second pad in over the debug port and plays the split screen (~4 min); not part of 'all'.
# 'mouse' switches the mouse package on (build-dir mods/state.toml, restored afterwards) and checks
# yaw, aim-mode pitch, pause, split screen and package off in three boots (~12 min); not part of 'all'.
# 'widescreen' switches the widescreen package on and checks 16:9 only in gameplay (film, menu,
# poster and pause stay 4:3), HUD anchors, edge culling in M1L1/M3L1/M7L1 and package off, in five boots (~20 min); not part of 'all'.
# 'pgxp' runs M1L1 at 4K with PGXP left at its default and checks the corrected-triangle share (~5 min); not part of 'all'.
param(
    [ValidateSet('dev', 'release')][string]$Build = 'dev',
    [ValidateSet('boot', 'intro', 'menu', 'coverage', 'level', 'save', 'sweep', 'coverage-long', 'mp', 'mouse', 'widescreen', 'pgxp', 'all')][string]$Test = 'boot',
    [int]$Port = 4370,
    [int]$Mission = 0,
    [switch]$Bonus
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

if ($Test -eq 'sweep') {
    $sweepArgs = @('--exe', $exe, '--cue', $env:MOH_CUE, '--port', $Port)
    if ($Mission -gt 0) { $sweepArgs += @('--mission', $Mission) }
    if ($Bonus) { $sweepArgs += '--bonus' }
    py -3 (Join-Path $repo 'tests\smoke\sweep_smoke.py') @sweepArgs
    exit $LASTEXITCODE
}

if ($Test -eq 'coverage-long') {
    py -3 (Join-Path $repo 'tests\smoke\coverage_long.py') --exe $exe --cue $env:MOH_CUE --port $Port
    exit $LASTEXITCODE
}

$tests = if ($Test -eq 'all') { @('boot', 'intro', 'menu', 'coverage', 'level') } else { @($Test) }
foreach ($t in $tests) {
    py -3 (Join-Path $repo "tests\smoke\${t}_smoke.py") --exe $exe --cue $env:MOH_CUE --port $Port
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}
exit 0
