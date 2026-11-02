# Medal of Honor PAL Recompiled

<!-- retcomm-readme-metrics -->
[![GitHub downloads (all assets, all releases)](https://img.shields.io/github/downloads/cr1tika7/MOHRecomp/total)](https://github.com/cr1tika7/MOHRecomp/releases)
[![GitHub downloads (latest release)](https://img.shields.io/github/downloads/cr1tika7/MOHRecomp/latest/total)](https://github.com/cr1tika7/MOHRecomp/releases/latest)
[![GitHub release](https://img.shields.io/github/v/release/cr1tika7/MOHRecomp)](https://github.com/cr1tika7/MOHRecomp/releases/latest)
<!-- /retcomm-readme-metrics -->

A native PC port of **Medal of Honor** (PlayStation, 1999), made by static
recompilation: the game's MIPS code is translated to C and compiled into a
real Windows/Linux/macOS executable, linked against the
[psxrecomp](https://github.com/RetroPortingToolKit/psxrecomp) PS1 hardware
runtime and the [recomp-ui](https://github.com/RetroPortingToolKit/recomp-ui)
launcher. It is not an emulator image and contains no game data: you need your
own disc.

On top of the original it adds optional mouse look, native 16:9 widescreen and
internal resolutions up to 4K, all switched off until you turn them on.

"PAL" in the name marks the disc it is built for: the European release. Other
PS1 ports of this game exist, for example
[FractalEngineer's VR port](https://github.com/FractalEngineer/Medal-Of-Honor-PSX-Recomp)
for the USA disc; they are separate projects with their own releases.

| | |
|---|---|
| Game | Medal of Honor (Europe) |
| Serial | SLES-02470 |
| Players | 1, or 2 in the split-screen multiplayer |
| Developer / publisher | DreamWorks Interactive / Electronic Arts |
| Year | 1999 |
| Status | **Playable** — all 24 campaign levels load and run natively |

## Play

1. Download the zip for your platform from
   [Releases](https://github.com/cr1tika7/MOHRecomp/releases) and extract it
   anywhere.
2. Start `Medal_of_Honor_PAL_Recompiled.exe`.
3. On first start, select the `.cue` of your own **European** disc dump
   (SLES-02470, the Redump set *Medal of Honor (Europe)*). The USA, French and
   German discs have different contents and are not supported. `DISC.md` in the
   zip lists the checksums.

No BIOS dump is needed: the bundled open-source
[OpenBIOS](https://github.com/grumpycoders/pcsx-redux) (MIT) is used. Saves go
to memory-card files beside the executable and survive updates.

### Controls

Keyboard defaults, laid out around WASD (rebind in the launcher under
**Controls**, or edit `keybinds.ini`). Gamepads work out of the box.

| In game | PlayStation | Keyboard / mouse |
|---|---|---|
| Walk forward / back | D-pad up / down | W / S, Up / Down |
| Turn | D-pad left / right | Left / Right (and the mouse, see below) |
| Strafe | L1 / R1 | A / D |
| Fire | Cross | E, left mouse button |
| Aim mode (hold) | R2 | O, right mouse button |
| Crouch | L2 | Y (the key labelled Z on a German keyboard) |
| Change weapon | Circle | R |
| Look up (hold) / back in menus | Triangle | F, Esc |
| Pause | Start | Return |

### Mods (launcher → Mods)

- **Mouse Look** (Input): the mouse turns the view and tilts it up and down
  like the right stick of a DualShock; shots go where the view points. Holding
  the right mouse button enters the game's aim mode, where the mouse moves the
  crosshair. Click into the window to capture the mouse, Esc releases it.
  Options: sensitivity, invert Y, free vertical look. While it is on, player 1
  is an analog pad, so a gamepad then behaves like a DualShock on the original.
- **Widescreen 16:9** (Visual): levels are rendered wider, nothing is
  stretched. The compass moves to the left edge, the ammo counter to the
  right. Menus, films, loading screens and the split screen stay 4:3.
- **Internal Resolution** (up to 4K) and **PGXP Precision** come from the
  framework. PGXP is off by default because it makes the compass jitter on
  this runtime.

### Split screen

MULTIPLAYER → START GAME needs a second controller: assign a gamepad to
player 2 in the launcher under **Controls**. Player 1 plays the top half.

## What works

Checked with the automated smoke tests in `tests/smoke` (see
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)):

- Boot, the intro films with sound, all menus, memory-card save and load.
- All 24 single-player levels: each is entered and played for 30 s (walking,
  turning, shooting) with its own level data and fully native code. The menu,
  single-player and split-screen overlays (`SHELL.BIN`, `LEVEL.BIN`,
  `LEVEL2P.BIN`) are compiled ahead of time.
- Mission 1 (three levels) played through by hand in the release build.
- Split screen with two pads, each steering its own half (tested with a
  virtual second pad).
- Full speed: 50 vblanks per second (PAL) in menus and levels; the game itself
  draws at its original ~25 fps.

Not done yet:

- Missions 2 to 7 have not been played through to the end by hand.
- Split screen with two physical pads is untested.
- Linux and macOS packages are built by CI but untested by hand.

Please report problems with your platform, GPU, mission/level and the steps
that lead to them; a memory card from before the problem helps most.

<!-- retcomm-readme-launcher -->
## Retro Launcher

You can run this title **standalone** (download the release zip, point it at
your disc, play), or manage installs, updates, and disc/BIOS wiring with
**[Retro Launcher](https://github.com/RetroPortingToolKit/Retro-Launcher)** —
the Retro Compilation Manager hub for self-compiling recomps.

[Downloads](https://github.com/RetroPortingToolKit/Retro-Launcher/releases) ·
[Full README & features](https://github.com/RetroPortingToolKit/Retro-Launcher#readme)

<p align="center">
  <img src="https://raw.githubusercontent.com/RetroPortingToolKit/Retro-Launcher/main/docs/screenshots/hub-and-game-launcher.png" alt="Retro hub with a background build, next to a title’s recomp-ui launcher" width="720">
</p>

<p align="center">
  <img src="https://raw.githubusercontent.com/RetroPortingToolKit/Retro-Launcher/main/docs/screenshots/queue-and-background-build.png" alt="Background cmake build with titles queued" width="720">
</p>

Retro checks for updates, installs the prebuilt release zips, and automates
BIOS/ROM/save plumbing so you are not stuck repeating each game’s first run by hand.
<!-- /retcomm-readme-launcher -->

## Legal

You must own the original game. Disc images are never part of this repository
or its releases. Retail BIOS dumps are not redistributed and no C derived from
one is committed; releases run on the bundled MIT OpenBIOS.

`generated/` holds the recompiled game C and **is committed**: release CI
builds the shipped executable from it. Regenerate and commit it whenever seeds,
`aot/overlays.json`, the mod hook sites in `game.toml` or the framework pin
change.

The psxrecomp framework is licensed under PolyForm Noncommercial 1.0.0, so
this port must not be sold or used commercially.

Medal of Honor is a trademark of Electronic Arts. This project is not
affiliated with or endorsed by Electronic Arts or DreamWorks Interactive.

Default app icon: `assets/psxrecomp.ico` (and `.png` / `.svg`) — Retro-themed
controller mark from `psxrecomp/assets/`. Windows builds embed it via `APP_ICON`.

## Building from source

Full workflow, tests, game internals and debugging notes:
[docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) (German).

```bash
git clone --recurse-submodules https://github.com/cr1tika7/MOHRecomp.git
cd MOHRecomp
./psxrecomp/tools/ci/build_emitters.sh
# Only needed after changing seeds, aot/overlays.json, game.toml hook sites or the framework pin:
python3 psxrecomp/psxrecomp_cli.py generate \
  --config game.toml --project-root . --disc "/path/to/Medal of Honor (Europe).cue"
python3 psxrecomp/psxrecomp_cli.py rebuild \
  --config game.toml --project-root . --build-dir build-release --no-pgo
```

Releases: run the *Release builds* workflow on GitHub (or push a `vX.Y.Z`
tag). CI builds the committed `generated/` C on Linux, Windows and macOS and
attaches `moh-pal-<version>-<platform>.zip`. Locally (the build must be configured
with `-DPSX_RELEASE_CHANNEL=public`):
`scripts/package_release.sh build-release windows-x64`.

## Framework pins

Submodule gitlinks (`psxrecomp`, `recomp-ui`, nested `recomp-net`) are
authoritative and point at upstream RetroPortingToolKit commits.
`framework_pins.txt` is an optional scaffold snapshot; release CI logs SHAs
with `record_pins.sh` but builds whatever the gitlinks resolve to. Bump
submodules deliberately and regenerate `generated/` afterwards.

<!-- retcomm-readme-raid -->
---

<p align="center">
  <sub><b>R.A.I.D. — Retro AI Development</b> · a Discord for AI-assisted retro reverse-engineering, decomp &amp; recomp</sub>
</p>

<p align="center">
  <a href="https://discord.gg/Ad9BwSzctP"><img src=".github/raid-discord.png" alt="Join the Retro AI Development (R.A.I.D.) Discord" width="200"></a>
</p>
<!-- /retcomm-readme-raid -->
