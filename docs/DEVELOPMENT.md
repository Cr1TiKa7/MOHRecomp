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

# Lange Läufe, nicht Teil von "all"
pwsh -File tools/run-smoke.ps1 -Build dev -Test sweep              # alle 24 Levels (-Mission N: nur eine Mission)
pwsh -File tools/run-smoke.ps1 -Build dev -Test mp                 # Splitscreen
pwsh -File tools/run-smoke.ps1 -Build dev -Test coverage-long      # je 10 min Videos, Menüs, Levels
```

| Test | Prüft | Dauer |
|---|---|---|
| `boot` | Bildzähler läuft, erstes echtes Bild, Kartendatei angelegt und formatiert | ~15 s |
| `intro` | Intro-Video bekommt MDEC-Daten, SPU-Ausgang hörbar (RMS ≥ 200) | ~45 s |
| `menu` | Spiel hat die Speicherkarte abgefragt (`sio_state`), Hauptmenü-Ring (6 Einträge), Options öffnen und mit Dreieck verlassen | ~2 min |
| `coverage` | Ohne Runtime-Autocompile und ohne DLL-Cache: Loader aktiv, keine DLL lief, Interpreter-Anteil < 1 %, statischer Overlay-Code lief. Danach NEW GAME mit X durchs Briefing, bis `LEVEL.BIN` an `0x80039F28` liegt, und das Spiel läuft weiter. | ~3 min |
| `level` | Mission 1, Level 1 ohne Autocompile: wartet, bis das Ladeplakat weg ist. Bildrate ≥ 48 (Median aus 3 × 5 s), Ton, UP verändert das Bild deutlich stärker als Stillstand, 2 min Laufen/Drehen/Schießen ohne Hänger, Interpreter-Anteil im Level-Fenster < 1 %. | ~4 min |
| `save` | Lädt das Fixture `D:\RecompDev\fixtures\moh-m1l1-complete.mcd` über WAR RECORDS → LOAD GAME. Der Spielername steht vorher nicht im Spielspeicher, danach schon. Die Karte wurde gelesen, das Spiel läuft weiter, das Fixture bleibt unverändert. | ~2 min |
| `sweep` | Pro Level eine eigene Instanz ohne Autocompile: Sprung ins Level (siehe „Level-Sprung“), 30 s Laufen/Drehen/Schießen. Das Level hat seine eigenen Daten gelesen (bei allen außer M1L1 keine von M1L1), das Bild ändert sich weiter, Interpreter-Anteil < 1 %. Eine Zeile pro Level, bricht nie vorzeitig ab. `-Bonus` springt stattdessen in die MSN12-Ordner. | ~3 min pro Level |
| `mp` | Ohne Autocompile: steckt über den Debug-Port einen Controller in Port 2, MULTIPLAYER → START GAME. `LEVEL2P.BIN` liegt an `0x80039F28`, jeder Controller dreht nur seine Bildhälfte (Spieler 1 oben), 60 s beide Spieler aktiv, `/DATA/TWOPLAYR/` gelesen, Interpreter-Anteil < 1 %. | ~4 min |
| `coverage-long` | Ohne Autocompile je 10 min Videos (Boot ohne Turbo, dann der ~108-s-Film unter BRIEFING in Schleife; jeder Durchlauf muss MDEC-Daten liefern und ins Menü zurückkehren), Menüs (Ring, OPTIONS, WAR RECORDS, GALLERY) und Levels (M1L1, M3L1, M7L1). Jede Phase zählt nur ihre eigenen Fenster und muss < 1 % interpretiert bleiben. Einträge an den Kernel-Patch-Slots des BIOS stehen als `slot=` daneben und zählen nicht mit (siehe „Overlays vorab nativ“). | ~45 min |

**Fixture:** Die Karte stammt aus einem echten Durchlauf von Mission 1, Level 1 im Release-Build, gespeichert am 2026-10-26 als `BESLES-02470PASCAL0`. Sie liegt nur lokal und kommt nie ins Repo. Neu erzeugen: Level durchspielen, speichern, `saves\card1.mcd` dorthin kopieren.

Die Tests starten das Spiel mit `SDL_AUDIODRIVER=dummy`, es ist also nichts zu hören. Die gemessenen Audio-Abgriffe liegen vor dem Ausgabegerät. `PSX_HOST_MUTE` wirkt in dieser Runtime nicht.

- Jeder Test legt Log, Screenshots und Speicherkarten unter `D:\RecompDev\Temp\<test>-<Zeitstempel>\` ab.
- Ist Port 4370 schon belegt, bricht er ab. Dann läuft noch eine andere Instanz.
- Gemeinsame Helfer stehen in `tests/smoke/psxrun.py` (Start, Tasten, RAM, Beenden), spielspezifische Fakten in `tests/smoke/moh.py`.

## Overlays vorab nativ (`aot/overlays.json`)

`SHELL.BIN` (Menüs), `LEVEL.BIN` (Einzelspieler-Level) und `LEVEL2P.BIN` (Splitscreen) werden aus den Disc-Daten vorab kompiliert:
- Alle drei liegen abwechselnd an derselben Ladeadresse `0x80039F28`. Belegt ist das durch den Lader-Code der Boot-EXE (Check `words`) und im RAM. Das erste Wort des Overlays ist 7 (`SHELL`), 5 (`LEVEL`) oder 6 (`LEVEL2P`). Die Byte-Guards der Runtime wählen das richtige Image.
- gebunden an den SHA-256 des Datentracks
- `generate` baut daraus `generated/overlays_static*.c` (SHELL 15.270 + LEVEL 14.208 + LEVEL2P 13.664 native Einstiege), die `CMakeLists.txt` linkt es über `GAME_OVERLAY_STATIC_C`. `generated/AOT_STATIC_AUDIT.json` listet die Images unter `required_images`.
- Ergebnis: Menü und Level laufen mit 50 Bildern/s. Ohne `LEVEL.BIN` im Rezept lief das Level interpretiert mit ~33.

**Boot-EXE-Funktionen, die nur Overlays aufrufen:** Der Recompiler findet in der EXE nur Funktionen, die die EXE selbst erreicht. Springt ein Overlay per `jal` in eine EXE-Funktion ohne Einstieg, läuft sie bei jedem Aufruf interpretiert. Im Splitscreen war das der Stapel-Umschalter `0x8001535C`, der allein fast den ganzen Interpreter-Anteil ausmachte. Solche Ziele kommen als Seeds nach `seeds/ghidra_funcs.txt`, danach `generate` und neu bauen. Finden lassen sie sich so: alle `CPS jal -> 0x…`-Ziele in `generated/overlays_static*.c` unter `0x80039F28`, die in `generated/SLES_024.70_dispatch.c` kein `func_…` haben. Welcher Code im Spiel interpretiert läuft, zeigt `dirty_ram_stats` (`per_pc`, Differenz zweier Abfragen).

**Kernel-Patch-Slots des BIOS zählen nicht mit:** Beim ersten Speicherkarten-Zugriff schreibt die Psy-Q-Bibliothek des Spiels einen 4-Wort-Stub in den Kernel-RAM (`_patch_card`, `0x281C`). Der Interrupt-Handler durchläuft ihn bei jeder Exception, im Menü etwa 250-mal pro Sekunde. Das BIOS-Profil `psxrecomp/bios/OpenBIOS.toml` deklariert solche Stellen als `install_slots`, und die Runtime interpretiert genau diese Wörter mit Absicht (`psxrecomp/docs/dynamic_handler_install.md`). Der Aufruf dahinter läuft wieder nativ. Im Menü waren das 5199 von 5205 interpretierten Dispatches, also 2 % der wenigen Overlay-Dispatches dort, aber nur 3 Befehle pro Exception. Die Smoke-Tests lesen die Slots aus dem Profil, das zu `bios_info.image_id` passt (`flows.install_slots`), zählen deren Einträge als `slot` und lassen sie aus dem Interpreter-Anteil heraus. Jede andere interpretierte Adresse zählt weiter.

Bei einer anderen Disc bricht die Pipeline mit „not applicable“ ab. Prüfen ohne Build:

```powershell
py -3 psxrecomp\tools\aot_overlay_pipeline.py extract --profile aot\overlays.json --game-toml game.toml --recompiler build-recompiler\psxrecomp-game.exe --work-dir D:\RecompDev\Temp\aot-work
```

## Level-Sprung

Der Spielstand liegt in der Boot-EXE und überlebt den Wechsel der Overlays: Missionsindex an `0x800387F8`, Levelindex an `0x800387FC`, beide ab 0. `flows.start_level` startet NEW GAME, schreibt nach 3 s beide Werte und drückt X durch Videos und Briefing. `LEVEL.BIN` lädt dann das gewählte Level (Pfadformat `data\msn%ld\lvl%ld\…`). Das Briefing zeigt trotzdem das von Mission 1. Früher geschrieben überschreibt das Spiel die Werte beim Zurücksetzen.

Die Missionsordner auf der Disc sind MSN1–5, MSN7 und MSN9 (MSN9 ohne LVL3), zusammen 24 Levels. MSN12 hat sieben Ordner mit je drei Dateien. Der Splitscreen lädt seine Standardkarte aus MSN12/LVL4, und ein Sprung mit Missionsindex 11 lädt nach NEW GAME `LEVEL2P.BIN` statt `LEVEL.BIN` (`-Test sweep -Bonus`: 0/7, alle mit Overlay-Wort 6). Es sind also die Mehrspieler-Karten, im Einzelspieler nicht spielbar. Die Sektorbereiche aller Levels stehen in `tests/smoke/moh.py`.

## Splitscreen

MULTIPLAYER öffnet einen eigenen Raum, START GAME ist vorgewählt. Ohne Controller in Port 2 erscheint „NOT ALL CONTROLLERS PLUGGED IN…“. Dafür braucht das Projekt `MAX_PLAYERS 2` (`CMakeLists.txt`) und `players = 2` (`game.toml`).

- Zum Spielen: im Launcher unter Controls Spieler 2 ein Gamepad zuweisen. Standardmäßig hat Spieler 2 kein Gerät, der Einzelspieler bleibt also unverändert.
- Spieler 2 auf der Tastatur ist nicht vorgesehen: `[player2]` in `keybinds.ini` belegt Tasten, die Spieler 1 mit WASD schon nutzt.
- Tests: `set_input`/`press` mit `payload={"port": 2, "connected": 1}` steckt einen digitalen Controller ein, solange der Test ihn treibt (`flows.plug_pad2`, `flows.hold`).

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

Nur im Dev-Build. Pro TCP-Verbindung geht genau eine JSON-Zeile hin und eine zurück, z. B. `{"id":1,"cmd":"ping"}`. Python-Client: `tests/smoke/psxdbg.py` (`send(cmd, port=4370, payload=None, **params)`).

Fallstricke:
- `ping` beantwortet ein I/O-Thread ohne Bildzähler. Die Bildnummer liefert `frame`.
- `audio_wav` mit `start < 0` liefert die ältesten Samples. Für die jüngsten muss man `start = audio_stats.taps[i].frames - count` übergeben.
- `mdec_state.decode_macroblocks` gilt pro Bild, `dma_in_words` pro Film: Der Zähler behält den Stand des letzten Films und fängt beim nächsten Film wieder bei fast null an (`coverage_long.film_words`).
- `psxdbg.send` wirft bei `{"ok": false}` keinen Fehler. Wo es zählt, die Antwort prüfen.
- `send(…, port=…)` ist der TCP-Port. Das Feld `port` eines Befehls (Controller-Port bei `set_input`/`press`/`clear_input`) gehört in `payload=`.
- Ein `clear_input` ohne `port` beendet auch die Eingabe für Port 2 und zieht damit den Test-Controller dort ab. Für Spieler 1 allein: `payload={"port": 1}`.
- `cd_read_log` protokolliert nur die Start-LBA jedes Lesevorgangs. `lba_lo`/`lba_hi` filtern `entries`, nicht `total`.
- `overlay_loader_status.dispatch_native` zählt nur DLL-Aufrufe. Treffer im statischen Shard stehen in `overlay_static_entries.total_hits`.

## Was nie ins Repo gehört

Disc-Images, BIOS-Dumps, Logs, `overlay_captures.json` (enthält Spielcode), Savestates und Speicherkarten. Die `.gitignore` deckt das ab. Vor jedem Commit trotzdem `git status` prüfen.
