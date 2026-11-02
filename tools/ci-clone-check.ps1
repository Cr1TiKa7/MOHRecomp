# Release check like CI, from a fresh clone of the local HEAD: the gates of
# .github/workflows/release.yml, the emitters, a public-channel build with the
# CI flags and the release packager. Commit first: only committed files count.
# Usage:  pwsh -File tools/ci-clone-check.ps1 [-Version 0.1.0] [-Out D:\RecompDev\Temp\moh-ci-clone]
# Writes: <Out>\dist\moh-pal-<Version>-windows-x64.zip; prints CI-CLONE-OK at the end.
param(
    [string]$Version = '0.1.0',
    [string]$Out = 'D:\RecompDev\Temp\moh-ci-clone'
)
$ErrorActionPreference = 'Stop'
. D:\RecompDev\dev-env.ps1
$src = Split-Path -Parent $PSScriptRoot
if (Test-Path $Out) { Remove-Item -Recurse -Force $Out }

function Step($name, [scriptblock]$body) {
    Write-Host "=== $name"
    & $body
    if ($LASTEXITCODE -ne 0) { throw "$name failed (exit $LASTEXITCODE)" }
}

Step 'clone' { git clone -q $src $Out }
Set-Location $Out
# Submodules from the local checkouts, so no network and exactly the pinned commits.
Step 'submodules' {
    git config submodule.psxrecomp.url "$src\psxrecomp"
    git config submodule.recomp-ui.url "$src\recomp-ui"
    git -c protocol.file.allow=always submodule update --init
    git -C psxrecomp config submodule.lib/recomp-net.url "$src\psxrecomp\lib\recomp-net"
    git -C psxrecomp config submodule.lib/retcomm-rbengine.url "$src\psxrecomp\lib\retcomm-rbengine"
    git -C psxrecomp -c protocol.file.allow=always submodule update --init --recursive
}
Step 'pin VERSION' { Set-Content -NoNewline -Path VERSION -Value "$Version`n"; $global:LASTEXITCODE = 0 }
Step 'record pins' { bash psxrecomp/tools/ci/record_pins.sh }
Step 'check_boot_exe' { bash psxrecomp/tools/ci/check_boot_exe.sh . }
Step 'check_generated' { bash psxrecomp/tools/ci/check_generated.sh --root . }
Step 'check_bios_stamps' { bash psxrecomp/tools/ci/check_bios_stamps.sh --framework psxrecomp }
Step 'build emitters' { bash psxrecomp/tools/ci/build_emitters.sh --framework psxrecomp --build-dir build-recompiler }
Step 'build runtime (public)' {
    py -3 psxrecomp\psxrecomp_cli.py rebuild --config game.toml --project-root . --build-dir build-ci --no-pgo --no-toolchain-download `
        --cmake-extra=-DPSX_RELEASE_CHANNEL=public `
        --cmake-extra=-DPSXRECOMP_REQUIRE_GAME_C=ON `
        --cmake-extra=-DPSXRECOMP_BIOS_STALE_FATAL=ON `
        --cmake-extra=-DPSXRECOMP_FORCE_SETUP_HOST=OFF `
        --cmake-extra=-DPSXRECOMP_ALLOW_NO_BIOS=OFF `
        --cmake-extra=-DPSX_SETUP_WIZARD=ON `
        --cmake-extra=-DPSX_GAME_VERSION=$Version
}
$env:RELEASE_VERSION = $Version
$env:CI = 'true'
Step 'package' { bash scripts/package_release.sh build-ci windows-x64 build-recompiler }
Get-ChildItem dist -Filter *.zip | Format-Table Name, Length
Write-Host 'CI-CLONE-OK'
