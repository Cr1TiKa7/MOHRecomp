# Entwicklung

Kurzreferenz für die tägliche Arbeit an MOHRecomp. Das Konzept steht in [superpowers/specs/2026-10-25-moh-pc-port-design.md](superpowers/specs/2026-10-25-moh-pc-port-design.md).

## Umgebung

Jede neue PowerShell-Sitzung lädt zuerst die Umgebung:

```powershell
. D:\RecompDev\dev-env.ps1
Set-Location D:\RecompDev\MOHRecomp
```

`dev-env.ps1` liegt bewusst außerhalb des Repos, weil es maschinenspezifisch ist. Es setzt diese Variablen:

| Variable | Zweck |
|---|---|
| `TEMP` / `TMP` | `D:\RecompDev\Temp`, damit C: frei bleibt |
| `PSXRECOMP_TOOLCHAIN_DIR` / `RETCOMM_TOOLCHAIN_DIR` | `D:\RecompDev\Toolchain` (cmake-clang-v1 1.0.14) |
| `RETCOMM_TOOLCHAIN_CACHE` / `RETCOMM_DATA_HOME` / `RETCOMM_DATA_DIR` / `CCACHE_DIR` / `PSX_RESIDENT_CACHE` | Caches auf D: statt `%LOCALAPPDATA%` |
| `PATH` | Toolchain-`bin` und Git-Bash vorangestellt |
| `MOH_CUE` | Pfad zur Disc (PAL, SLES-02470) |

Die `.gitattributes` erzwingt LF für alle Textdateien, unabhängig von `core.autocrlf`. Ohne sie bricht Windows PowerShell 5.1 in Framework-Skripten an Gits LF/CRLF-Warnungen ab.

Ein Ausnahmefall: Der Mod-Medien-Cache der Runtime (`%LOCALAPPDATA%\psxrecomp\imports`) hat keine Umleitung. Er wird nur von Mods benutzt, die Medien importieren.

## Code erzeugen und bauen

```powershell
# Spiel-C aus der Disc neu erzeugen (deterministisch; danach generated/ committen)
py -3 psxrecomp\psxrecomp_cli.py generate --config game.toml --project-root . --disc $env:MOH_CUE

# Release (ohne Debug-Server) -> build-release\MOH_Recompiled.exe
py -3 psxrecomp\psxrecomp_cli.py rebuild --config game.toml --project-root . --build-dir build-release --no-pgo --no-toolchain-download

# Entwicklung (Debug-Server auf Port 4370) -> build-dev\MOH_Recompiled.exe
py -3 psxrecomp\psxrecomp_cli.py rebuild --config game.toml --project-root . --build-dir build-dev --no-pgo --no-toolchain-download --cmake-extra=-DPSX_DEBUG_TOOLS=ON
```

## Tests

```powershell
# Unit-Tests der Test-Helfer
py -3 -m unittest discover -s tests/smoke -v

# Smoke-Tests gegen build-dev: einzeln (-Test boot|intro|menu|coverage|level|save) oder alle nacheinander
pwsh -File tools/run-smoke.ps1 -Build dev -Test all

# Spielstand-Test (braucht das lokale Fixture, nicht Teil von "all")
pwsh -File tools/run-smoke.ps1 -Build dev -Test save
```

| Test | Prüft | Dauer |
|---|---|---|
| `boot` | Bildzähler läuft, erstes echtes Bild, Kartendatei angelegt und formatiert | ~15 s |
| `intro` | Intro-Video bekommt MDEC-Daten, SPU-Ausgang hörbar (RMS ≥ 200) | ~45 s |
| `menu` | Spiel hat die Speicherkarte abgefragt (`sio_state`), Hauptmenü-Ring (6 Einträge), Options öffnen und mit Dreieck verlassen | ~2 min |
| `coverage` | Ohne Runtime-Autocompile und ohne DLL-Cache: Loader aktiv, keine DLL lief, Interpreter-Anteil < 1 %, statischer Overlay-Code lief. Danach NEW GAME mit X durchs Briefing, bis `LEVEL.BIN` an `0x80039F28` liegt, und das Spiel läuft weiter. | ~3 min |
| `level` | Mission 1, Level 1 ohne Autocompile: wartet, bis das Ladeplakat weg ist. Bildrate ≥ 48 (Median aus 3 × 5 s), Ton, UP verändert das Bild deutlich stärker als Stillstand, 2 min Laufen/Drehen/Schießen ohne Hänger, Interpreter-Anteil im Level-Fenster < 1 %. | ~4 min |
| `save` | Lädt das Fixture `D:\RecompDev\fixtures\moh-m1l1-complete.mcd` über WAR RECORDS → LOAD GAME. Der Spielername steht vorher nicht im Spielspeicher, danach schon. Die Karte wurde gelesen, das Spiel läuft weiter, das Fixture bleibt unverändert. | ~2 min |

**Fixture:** Die Karte stammt aus einem echten Durchlauf von Mission 1, Level 1 im Release-Build, gespeichert am 2026-10-26 als `BESLES-02470PASCAL0`. Sie liegt nur lokal und kommt nie ins Repo. Neu erzeugen: Level durchspielen, speichern, `saves\card1.mcd` dorthin kopieren.

Die Tests starten das Spiel mit `SDL_AUDIODRIVER=dummy`, es ist also nichts zu hören. Die gemessenen Audio-Abgriffe liegen vor dem Ausgabegerät. `PSX_HOST_MUTE` wirkt in dieser Runtime nicht.

- Jeder Test legt Log, Screenshots und Speicherkarten unter `D:\RecompDev\Temp\<test>-<Zeitstempel>\` ab.
- Ist Port 4370 schon belegt, bricht er ab. Dann läuft noch eine andere Instanz.
- Gemeinsame Helfer stehen in `tests/smoke/psxrun.py` (Start, Tasten, RAM, Beenden), spielspezifische Fakten in `tests/smoke/moh.py`.

## Overlays vorab nativ (`aot/overlays.json`)

`SHELL.BIN` (Menüs) und `LEVEL.BIN` (Einzelspieler-Level) werden aus den Disc-Daten vorab kompiliert:
- Beide liegen abwechselnd an derselben Ladeadresse `0x80039F28`. Belegt ist das durch den Lader-Code der Boot-EXE (Check `words`) und im RAM. Die Byte-Guards der Runtime wählen das richtige Image.
- gebunden an den SHA-256 des Datentracks
- `generate` baut daraus `generated/overlays_static*.c` (SHELL 15.270 + LEVEL 14.208 native Einstiege), die `CMakeLists.txt` linkt es über `GAME_OVERLAY_STATIC_C`
- Ergebnis: Menü und Level laufen mit 50 Bildern/s. Ohne `LEVEL.BIN` im Rezept lief das Level interpretiert mit ~33.

Bei einer anderen Disc bricht die Pipeline mit „not applicable“ ab. Prüfen ohne Build:

```powershell
py -3 psxrecomp\tools\aot_overlay_pipeline.py extract --profile aot\overlays.json --game-toml game.toml --recompiler build-recompiler\psxrecomp-game.exe --work-dir D:\RecompDev\Temp\aot-work
```

## RAM-Werte finden (`tools/ramdiff.py`)

1. Pro bekanntem Spielzustand einen RAM-Abzug machen (`read_ram 0x80000000 0x200000`).
2. Die Byte-Stellen suchen, deren Werte der erwarteten Folge entsprechen:

```powershell
py -3 tools/ramdiff.py --snapshots s0.bin s1.bin s2.bin --expected 0 1 2
```

So wurde der Zeiger auf den aktuellen Menüeintrag gefunden (`moh.MENU_ITEM_PTR_ADDR`). Steckt der Wert nicht als Byte im Speicher, sondern z. B. als Zeiger, muss man nach arithmetischen Folgen suchen (Schrittweite ≠ 1).

## Tastaturbelegung (`config/keybinds.ini`)

Die Runtime liest `keybinds.ini` neben der `.exe`. Fehlt die Datei, legt sie sie mit den Framework-Standardtasten an. Unsere Belegung (Wunsch vom 2026-10-26, deutsche QWERTZ-Tastatur) liegt in `config/keybinds.ini`. Nach einem Neuaufsetzen der Build-Ordner kopierst du sie neben die `.exe`:

```powershell
Copy-Item config\keybinds.ini build-release\keybinds.ini
```

| PS1 | Taste |
|---|---|
| Steuerkreuz / linker Stick | W A S D (Pfeiltasten zusätzlich) |
| Kreuz / Kreis / Quadrat / Dreieck | E / R / Q / Esc |
| L2 / L1 / R1 / R2 | Z / U / I / O |
| Start / Select | Return / rechte Umschalttaste |

SDL-Tastennamen meinen US-Positionen. Die Taste **Z** einer QWERTZ-Tastatur heißt in der Datei deshalb `Y`.

Die Smoke-Tests sind von der Belegung unabhängig, sie steuern über den Debug-Override (`press`/`set_input`). Ab M4 wird die Belegung Teil des Mod-Pakets `moh.input.mouse-keyboard`.

## Debug-Port

Nur im Dev-Build. Pro TCP-Verbindung geht genau eine JSON-Zeile hin und eine zurück, z. B. `{"id":1,"cmd":"ping"}`. Python-Client: `tests/smoke/psxdbg.py` (`send(cmd, port=4370, **params)`).

Fallstricke:
- `ping` beantwortet ein I/O-Thread ohne Bildzähler. Die Bildnummer liefert `frame`.
- `audio_wav` mit `start < 0` liefert die ältesten Samples. Für die jüngsten muss man `start = audio_stats.taps[i].frames - count` übergeben.
- `mdec_state.decode_macroblocks` gilt pro Bild. Fortlaufend zählt `dma_in_words`.

## Was nie ins Repo gehört

Disc-Images, BIOS-Dumps, Logs, `overlay_captures.json` (enthält Spielcode), Savestates und Speicherkarten. Die `.gitignore` deckt das ab. Vor jedem Commit trotzdem `git status` prüfen.
