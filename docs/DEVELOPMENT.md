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

# Release (ohne Debug-Server) -> build-release\Medal_of_Honor_PAL_Recompiled.exe
py -3 psxrecomp\psxrecomp_cli.py rebuild --config game.toml --project-root . --build-dir build-release --no-pgo --no-toolchain-download

# Entwicklung (Debug-Server auf Port 4370) -> build-dev\Medal_of_Honor_PAL_Recompiled.exe
py -3 psxrecomp\psxrecomp_cli.py rebuild --config game.toml --project-root . --build-dir build-dev --no-pgo --no-toolchain-download --cmake-extra=-DPSX_DEBUG_TOOLS=ON
```

Der Name der `.exe` folgt dem `WINDOW_TITLE` in `CMakeLists.txt` (seit dem ersten Release 2026-11-02 „Medal of Honor PAL Recompiled“, vorher „MOH Recompiled“). „PAL“ grenzt den Port von FractalEngineers „Medal of Honor Recompiled“ (USA-Disc, VR) ab, der denselben Namen und dasselbe Zip-Präfix `moh` schon benutzte. Ältere Build-Ordner enthalten noch eine `MOH_Recompiled.exe`, die die Tests nicht mehr benutzen.

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
pwsh -File tools/run-smoke.ps1 -Build dev -Test mouse             # Maus-Paket (siehe „Maus“)
pwsh -File tools/run-smoke.ps1 -Build dev -Test widescreen        # Breitbild-Paket (siehe „Breitbild“)
pwsh -File tools/run-smoke.ps1 -Build dev -Test pgxp              # PGXP-Paket bei 4K (siehe „PGXP und Auflösung“)

# C-Unit-Test der Maus-Rechenlogik (wird mit build-dev gebaut)
build-dev\moh_mouselook_test.exe
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
| `mouse` | Maus-Paket an (`build-dev\mods\state.toml`, danach wiederhergestellt), vier Starts. M1L1: Gier pro Impuls exakt; im Zielmodus Fadenkreuz Y/X, Kameraneigung und Drehen am Rand exakt; nach dem Loslassen Fadenkreuz 0, Neigung bleibt; senkrechte Bewegung ohne Zielmodus neigt exakt (freies Hoch/Runter), das Fadenkreuz bleibt 0; Bewegung in der Pause verfällt; alle vier Hook-Stellen laufen nativ. Splitscreen: kein Hook greift. Paket aus: keine Wirkung. `free_look` aus: senkrechte Bewegung ohne Zielmodus wirkt nicht, Drehen und Zielmodus schon. | ~12 min |
| `widescreen` | Breitbild-Paket an, fünf Starts. Intro-Film, Menü, Ladeplakat und Pause bleiben 4:3 (`present_ring`), M1L1 und Zielmodus sind breit (682 Pixel statt 512). HUD: Kompass am linken Rand, Munition am rechten, Fadenkreuz mittig (gemessene Verschiebung 0/170/85). Himmel füllt die Seitenstreifen (dunkler Anteil der oberen Hälfte ≤ 0,195 in vier Blickrichtungen). Blicke, in denen vorher am Rand Polygone fehlten (M1L1, M3L1, M7L1): ≤ 5 % dunkel, mit `ws_margin 200` unverändert. Paket aus: 4:3. | ~11 min |
| `pgxp` | PGXP-Paket an, interne Auflösung 4K. M1L1: `video_info` meldet Faktor 9 ohne Begrenzung, in 2 s Drehen und 2 s Laufen hat ein Anteil ≥ `PGXP_MIN_CORRECTED` (0,198) der Dreiecke ganz oder teilweise PGXP-Präzision (`geom_correction`). | ~5 min |
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

**Kernel-Patch-Slots des BIOS zählen nicht mit:** Beim ersten Speicherkarten-Zugriff schreibt die Psy-Q-Bibliothek des Spiels einen 4-Wort-Stub in den Kernel-RAM (`_patch_card`, `0x281C`). Der Interrupt-Handler durchläuft ihn bei jeder Exception, im Menü etwa 250-mal pro Sekunde. Das BIOS-Profil `psxrecomp/bios/OpenBIOS.toml` deklariert solche Stellen als `install_slots`, und die Runtime interpretiert genau diese Wörter mit Absicht (`psxrecomp/docs/dynamic_handler_install.md`). Der Aufruf dahinter läuft wieder nativ. Im Menü waren das 5199 von 5205 interpretierten Dispatches, also 2 % der wenigen Overlay-Dispatches dort, aber nur 3 Befehle pro Exception. `coverage-long`, `level`, `sweep` und `mp` lesen die Slots aus dem Profil, das zu `bios_info.image_id` passt (`flows.install_slots`), zählen deren Einträge als `slot` und lassen sie aus dem Interpreter-Anteil heraus. Jede andere interpretierte Adresse zählt weiter. Das geht nur, solange jeder Slot-Eintrag auch in `dispatch_interp_fallback` steckt. Sind es mehr Slot-Einträge als interpretierte Dispatches, bricht der Test ab („no longer nested“), statt abzuziehen. `coverage` zählt seit dem Boot und lässt die Slots drin, ist also strenger.

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

## Blickwinkel und Zielmodus

Gefunden in Mission 1 Level 1 (M4, 2026-10-26) mit `wtrace_*` und `disasm`. Die Konstanten stehen in `tests/smoke/moh.py` und `src/mouse/moh_addrs.h`.

- **Spieler-Struct:** `*(*(0x8009DC44) + 0x388)`, in M1L1 `0x800EEC2C`.
- **Gier:** Spieler + 0x184, 16.16-Festkomma, 4096 Winkeleinheiten pro Umdrehung, ohne Umbruch.
  - Geschrieben wird sie einmal pro Spiel-Frame bei `0x800801E0` (`SW $v0, 388($s0)`, Gier += Drehrate).
  - Die Stelle schreibt nur die Gier des Spielers. In der Pause läuft sie nicht.
- **Zielmodus** (R2 halten): Das Fadenkreuz erscheint, die Figur läuft nicht. Die Gier-Schreibstelle oben läuft dann nicht, die Zielfunktion übernimmt beide Achsen.
  - Gezielt wird mit digitalem Pad über das Steuerkreuz, mit analogem Pad über den linken Stick.
  - Jede Achse lädt eine Rate aus `16($sp)`: waagerecht bei `0x8007FC94` (`LW $v0`), senkrecht bei `0x8007FE7C` (`LW $a0`). An diesen beiden Stellen hängt das Maus-Plugin.
  - **Waagerecht:** Fadenkreuz X bei Spieler + 0x188 (+ Rate >> 3). Am Rand dreht die Ansicht, Gier += Rate (Schreibstelle `0x8007FD7C`).
  - **Senkrecht:** Fadenkreuz Y bei Spieler + 0x17C (0 = Mitte, negativ = oben, Grenzen ±983 040, + Rate >> 3). Am Rand kippt die Kamera: Spieler + 0x178, 16.16, positiv = oben, Grenzen ±0x02AA0000 (etwa 60°), − Rate >> 1.
  - **R2 loslassen** setzt das Fadenkreuz auf 0 (`0x80080028`). Mit digitalem Pad kippt die Kamera in etwa 1 s zurück, mit analogem Pad (also mit dem Maus-Paket) bleibt die Neigung stehen.
- **Außerhalb des Zielmodus** gibt es keinen Nickwinkel. Vertikal zielt das Spiel selbst, wenn EASY AIM an ist (Options → Controller).

| PS1-Taste (Belegung 1) | Wirkung im Level |
|---|---|
| Steuerkreuz hoch/runter | laufen |
| Steuerkreuz links/rechts | drehen |
| L1 / R1 | Seitschritt links / rechts |
| X | schießen |
| R2 (halten) | Zielmodus |
| L2 | ducken / aufstehen |
| Kreis | Waffe wechseln |
| Dreieck (halten) | Blick nach oben, beim Loslassen zurück |
| Quadrat, Select | ohne sichtbare Wirkung im Test |
| Start | Pause |

## RAM-Werte finden (`tools/ramdiff.py`)

1. Pro bekanntem Spielzustand einen RAM-Abzug machen (`read_ram 0x80000000 0x200000`).
2. Die Byte-Stellen suchen, deren Werte der erwarteten Folge entsprechen:

```powershell
py -3 tools/ramdiff.py --snapshots s0.bin s1.bin s2.bin --expected 0 1 2
```

So wurde der Zeiger auf den aktuellen Menüeintrag gefunden (`moh.MENU_ITEM_PTR_ADDR`). Steckt der Wert nicht als Byte im Speicher, sondern z. B. als Zeiger, muss man nach arithmetischen Folgen suchen (Schrittweite ≠ 1).

## Maus (`moh.input.mouse-keyboard`, M4)

Das Mod-Paket liegt unter `mods/preloaded/packages/moh.input.mouse-keyboard/` und ist standardmäßig aus.
- **Einschalten:** Launcher → Mods → Input → Mouse Look. Die Wahl landet in `mods\state.toml` neben der `.exe`.
- **Optionen:**
  - `sensitivity`: 1–200, Standard 40, das sind 6 550 Impulse pro Umdrehung
  - `invert_y`: Y-Achse umkehren
  - `free_look`: freies Hoch/Runter ohne Zielmodus, Standard an
  - Alle wirken auch live.
  - Bool-Optionen brauchen ihren Standardwert als Text (`default = "true"`): Das Framework liest `default = true` ohne Anführungszeichen stillschweigend als `"false"` (`mod_packages.cpp`).
- **Bedienung:** Klick ins Fenster fängt die Maus ein (dieser Klick schießt nicht), Esc gibt sie frei. Verlässt man das Spiel (Pause, Menü, Ladebild), gibt die Runtime die Maus frei, ein Klick fängt sie wieder.
- **Wirkung:**
  - Normales Spielen: Die Maus dreht und neigt die Ansicht wie der rechte Stick eines DualShock (freies Hoch/Runter). Das Spiel neigt, begrenzt und hält die Neigung selbst. Schüsse gehen dorthin, wohin die Ansicht zeigt: Einschusslöcher landeten bei −56°, −17° und +17° (gemessen) in der Bildmitte. L3 (Klick auf den linken Stick, in `keybinds.ini` nicht belegt) zentriert die Ansicht; solange er gehalten wird, verfällt senkrechte Mausbewegung, statt sich anzusammeln.
  - Rechte Maustaste (R2) hält den Zielmodus: Die Maus bewegt das Fadenkreuz, an dessen Rand dreht bzw. kippt die Ansicht.
  - Mit `free_look = false` neigt die Maus nur im Zielmodus. Spieler 1 bleibt ein Analog-Pad: Ein echter rechter Stick neigt weiter, und die Neigung bleibt stehen.
  - Freies Hoch/Runter hängt am Analog-Pad: Nur dessen Blick-Modus lädt die Neigungsrate bei `0x80080470`. Fiele die Analog-Vorgabe des Pakets weg, wirkte es nicht mehr.
- **Analoges Pad:** Mit dem Paket meldet sich Spieler 1 als DualShock. Dann gilt das Original-Verhalten mit Analogpad:
  - Die Kameraneigung bleibt nach dem Zielen stehen.
  - Im Zielmodus zielt der Stick, nicht das Steuerkreuz.
- **Code:**
  - `src/mouse/mouselook.c`: Rechenlogik
  - `src/mouse/moh_mouse_plugin.c`: Plugin `moh.mouse-look`. Hooks: Gier-Store `0x800801E0`, Neigungsrate `0x80080470` (normales Spielen, `LW $v1, 16($sp)`), Zielraten `0x8007FC94`/`0x8007FE7C` (Zielmodus).
  - Die Hook-Stellen stehen in `game.toml` (`mod_instruction_sites`). Nach Änderungen dort `generate` und neu bauen.
- **Debug:**
  - `{"cmd":"mod_cmd","name":"moh_mouse","args":"move <dx> <dy>"}` speist Mausimpulse ein. Die echte Maus-Erfassung ist unter Debug-Eingaben und im versteckten Fenster aus.
  - `mod_counters` zeigt `moh_mouse.activate`, `.yaw_hook`, `.tilt_hook`, `.aim_x_hook`, `.aim_y_hook`, `.acquired` (wie oft ein Klick die Maus eingefangen hat) und `.dropped` (per `move` eingespeiste Bewegung, die außerhalb des Spiels verworfen wurde; echte Mausbewegung verwirft die Runtime selbst).
  - Als „im Spiel“ gilt: `LEVEL.BIN` geladen und ein Hook lief in den letzten 12 VBlanks (240 ms). Danach gibt die Runtime die Maus frei.
- **Tests mit aktivem Paket:**
  - Ohne Achswerte schickt der Debug-Override jede Richtung doppelt ans Spiel, sobald Spieler 1 analog ist.
  - Die Helfer in `psxrun` schicken deshalb immer zentrierte Achsen. Das allein reicht nicht: Auch mit zentrierten Achsen zählt der einfache Override jeden Menüschritt doppelt, solange das Paket an ist.
  - Deshalb muss `MOH_SMOKE_PAD_LAYER=host` gesetzt sein, wenn `menu`, `mp`, `sweep` oder andere Tests mit aktivem Paket laufen. Dann steuern die Helfer Pad 1 über das virtuelle Host-Gamepad, das wie ein echtes Pad zählt. `-Test mouse` setzt das selbst.

## Tastaturbelegung (`config/keybinds.ini`)

Die Runtime liest `keybinds.ini` neben der `.exe`, die Launcher-Seite Controls bearbeitet dieselbe Datei. Unsere Belegung für Tastatur und Maus (M4, deutsche QWERTZ-Tastatur) liegt in `config/keybinds.ini`.
- Der Build kopiert sie neben die `.exe`, aber nur, wenn dort noch keine liegt (`cmake/copy_if_missing.cmake`). Eine vorhandene Datei gehört dem Spieler und bleibt unangetastet.
- Nach Änderungen an `config/keybinds.ini` kopierst du sie deshalb selbst:

```powershell
Copy-Item config\keybinds.ini build-release\keybinds.ini
```

| PS1 | Taste / Maus | Wirkung im Level |
|---|---|---|
| Steuerkreuz hoch / runter | W / S (Pfeil hoch/runter zusätzlich) | laufen |
| Steuerkreuz links / rechts | Pfeil links / rechts | drehen (die Maus dreht auch) |
| L1 / R1 | A / D (U / I zusätzlich) | Seitschritt |
| Kreuz | E, linke Maustaste | schießen |
| R2 | O, rechte Maustaste | Zielmodus halten |
| L2 | Z (in der Datei `Y`) | ducken |
| Kreis / Quadrat | R / Q | Waffe wechseln / – |
| Dreieck | Esc, F | Blick nach oben, solange gehalten; Esc im Menü = zurück |
| Start / Select | Return / rechte Umschalttaste | Pause / – |
| Sticks (`ls_*`, `rs_*`) | nicht belegt | Mit dem Maus-Paket ist Spieler 1 ein analoges Pad, eine Taste auf Steuerkreuz *und* Stick würde doppelt zählen. |

- SDL-Tastennamen meinen US-Positionen. Die Taste **Z** einer QWERTZ-Tastatur heißt in der Datei deshalb `Y`.
- **Maustasten:** `Mouse1` links, `Mouse2` Mitte, `Mouse3` rechts. Jede Eingabe nimmt bis zu zwei Tasten (`cross = E, Mouse1`).
- **Esc mit dem Maus-Paket:** Bei eingefangener Maus gibt Esc zuerst die Maus frei und erreicht das Spiel nicht. Dreieck liegt deshalb zusätzlich auf F.
- Die alte Belegung aus M2 liegt als `build-release\keybinds.ini.bak-m3`.
- Die Smoke-Tests sind von der Belegung unabhängig, sie steuern über den Debug-Port (`press`/`set_input`, mit aktivem Paket über das virtuelle Host-Gamepad).

## Breitbild (`moh.enhancement.widescreen`, M5)

Das Mod-Paket liegt unter `mods/preloaded/packages/moh.enhancement.widescreen/` und ist standardmäßig aus.
- **Einschalten:** Launcher → Mods → Visual → Widescreen 16:9.
- **Wirkung:** Im Level wird das Bild echt breiter gerendert (Native-Wide, 85 Pixel je Seite in 512er-Koordinaten), nichts wird gestreckt. Menüs, Briefing, Ladeplakat, Pause, Missionsauswertung und Videos bleiben 4:3 mit Seitenbalken (vom Smoke-Test geprüft: Menü, Ladeplakat, Pause, Intro-Film).
- **Nur im Spiel:**
  - Das Framework schaltet eine Szene ohne Weltgeometrie nie breit (2D-Veto). Das Plugin meldet deshalb per `psx_mod_set_world_scene_predicate`, wann gespielt wird.
  - Es gilt dasselbe Kriterium wie bei der Maus: `LEVEL.BIN` geladen, und der Gier-Store `0x800801E0` oder das Laden der Zielrate X `0x8007FC94` lief in den letzten 12 VBlanks. Die zweite Stelle hält den Zielmodus breit.
  - `game.toml [video] aspect_ratio` bleibt `"4:3"`. Das Seitenverhältnis setzt das Plugin bei Aktivierung (`psx_mod_set_fixed_display_aspect(16, 9)`).
- **Ausblenden am Rand:** Vier Tests verwerfen, was außerhalb des 4:3-Bildes liegt (Breite 540 aus `0x8009CE10`):
  - der Dreieckstest der Boot-EXE `0x80011214`
  - der Bounding-Box-Test der Levelknoten in `LEVEL.BIN` `0x8008B9C8`
  - der Würfeltest für Figuren und Requisiten in `LEVEL.BIN` `0x8008EB90` (Soldaten, gerufen über `0x8008EFBC`)
  - der Test für Einschusslöcher in `LEVEL.BIN` `0x8008C6A8` (Ring aus 100 Vierecken ab `0x80094244`)

  Alle werden über `[widescreen.cull]` in `game.toml` verbreitert, solange das Paket an ist, auch auf seinen 4:3-Bildschirmen (dort schneidet der Zeichenbereich ab). Ohne Paket bleiben sie unverändert. Die Stellen in `0x8008A338` nicht eintragen: Sie wären in `LEVEL2P.BIN` falsch.
- **HUD:**
  - Der Kompass besteht aus festen Paketen (`0xABF60`–`0xAD7B8`). Er wandert über `nw_left_hud_packet_lo/hi` an den linken Rand.
  - Die Munitionsanzeige liegt im selben Paketbereich wie die Welt. Das Plugin markiert sie deshalb einzeln mit `psx_mod_anchor_hud_primitive` für den rechten Rand:
    - Textzeichen oben rechts (x ≥ 342, y ≤ 20), Store `0x8005FC1C`
    - das Munitionssymbol, Store `0x800807C8`
  - Fadenkreuz, Meldungen und Untertitel bleiben mittig.
- **Himmel:**
  - Der Himmel besteht aus acht Farbverlaufsstreifen von x 0 bis 512, die bei `0x8008A098` verkettet werden.
  - Das Plugin markiert sie als Hintergrund (`gpu_ws_tag_background_prim`), damit sie die Seitenstreifen füllen. Die Funktion ist intern in der Runtime (`gpu.h`), ein Framework-Update kann sie umbenennen.
- **Splitscreen:** `LEVEL2P.BIN` erfüllt das Spiel-Kriterium nicht. Der Splitscreen bleibt deshalb 4:3.
- **Code:** `src/widescreen/moh_widescreen_plugin.c`. Die Hook-Stellen stehen in `game.toml` (`mod_instruction_sites`), Konstanten in `src/mouse/moh_addrs.h`. Nach Änderungen an `game.toml` `generate` und neu bauen.
- **Debug:**
  - `present_ring` zeigt pro Bild den Weg (`native43` oder breit) und `nw_extra`.
  - `ws_nw` und `display_aspect` zeigen den Zustand, `ws_margin` verbreitert die Ausblend-Grenze zum Testen.
  - `mod_counters` zeigt `moh_widescreen.activate`.

## PGXP und Auflösung (M5)

- **PGXP bleibt Wahl des Spielers** (Launcher → Mods → Visual → PGXP Precision, standardmäßig aus). `game.toml` setzt dazu nichts, es gelten die Framework-Werte für Runtimes ohne PGXP-Variante: Toleranz 0,5, Positions-Cache an.
- **Gemessener Anteil der Dreiecke, die ganz oder teilweise PGXP-Präzision haben,** in M1L1 (2 s Drehen, 2 s Laufen):

  | Variante | Anteil |
  |---|---|
  | Framework-Werte (Toleranz 0,5) | 0,248 |
  | Toleranz −1 | 0,576 |
  | Toleranz −1 ohne Positions-Cache (`pgxp_position_fallback = false`) | 0,008 |
  | `cpu_mode` | 0,254 |
  | eigene PGXP-Runtime (`-DPSX_PGXP_VARIANT=ON`) | 0,755 |

- **Warum nicht standardmäßig an:**
  - Auf dieser Runtime stammt fast jede Korrektur aus dem Positions-Cache. Der Cache gibt auch 2D-Polygonen, die die CPU baut, Sub-Pixel-Anteile fremder 3D-Ecken.
  - In M7L1 bekamen so alle Ecken des Kompasses wechselnde Bruchteile, schon im Stillstand (`pgxp_tri_ring`, Pakete `0xABF60`–`0xAD7B8`). Der Kompass zittert dann um bis zu einen PS1-Pixel, mit Toleranz 0,5 um bis zu einen halben.
  - `docs/ENHANCEMENTS.md` des Frameworks beschreibt denselben Effekt an einem anderen Spiel.
- **Keine eigene PGXP-Runtime:** Sie korrigiert ohne Cache und damit ohne HUD-Zittern. Sie kostet aber schon mit PGXP aus rund 16 % Durchsatz, und mit PGXP an lag sie unter Turbo bei 48 Bildern/s. Das Spiel braucht 50.
- **Auflösung:** Die interne Auflösung bleibt Wahl des Spielers (Launcher → Mods → Internal Resolution, bis 4K). Bei 4K meldet `video_info` `effective_scale` 9.
- **Debug:**
  - `geom_correction` zählt `tri_precise`, `tri_mixed` und `tri_native`.
  - `pgxp_tri_ring` listet die korrigierten Dreiecke mit Paketadresse und Quelle jeder Ecke (0 nativ, 1 Cache, 2 Datenfluss).

## Veröffentlichen

- **GitHub-Release:** Der Workflow *Release builds* (`.github/workflows/release.yml`) baut das committete `generated/` auf Linux, Windows und macOS und hängt `moh-pal-<Version>-<Plattform>.zip` an. Erzeugt wurde er aus der Vorlage des gepinnten Frameworks:

  ```powershell
  py -3 psxrecomp\tools\new_project_layout\fill_tokens.py psxrecomp\docs\ci\templates\game-release.yml .github\workflows\release.yml --ci-placeholders --set "ZIP_PREFIX=moh-pal" --set "GAME_TITLE=Medal of Honor PAL Recompiled" --set "WINDOW_TITLE=Medal of Honor PAL Recompiled"
  ```

  Nach einem Framework-Update den Workflow so neu erzeugen, damit er zu den Skripten im Submodul passt.
- **Inhalt des Zips** (`scripts/package_release.sh`): `.exe`, OpenBIOS, Mod-Pakete, Overlay-Toolchain, dazu `keybinds.ini` (`--runtime-file`; der Build legt `config/keybinds.ini` neben die `.exe`) und `DISC.md` (welcher Dump passt).
- **Vor einem Release lokal prüfen wie die CI:** `pwsh -File tools/ci-clone-check.ps1 [-Version 0.1.0]`. Das Skript klont den letzten Commit nach `D:\RecompDev\Temp\moh-ci-clone`, läuft durch die Prüfschritte von `release.yml`, baut mit Release-Kanal `public` und packt `dist\moh-pal-<Version>-windows-x64.zip`. Danach das Zip in einen leeren Ordner entpacken und mit `--disc <cue> --no-launcher` starten. Nur Committetes zählt, also vorher committen.
- **Lokal packen** geht nur mit einem Build, der einen Release-Kanal hat (`--cmake-extra=-DPSX_RELEASE_CHANNEL=public`), sonst lehnt der Packer ab. Die genauen Schritte stehen in `tools/ci-clone-check.ps1`.

- **Nach jeder Änderung an `game.toml`** `generate` laufen lassen, auch wenn sich am Code nichts ändert: `generated/AOT_STATIC_AUDIT.json` hält den SHA-256 von `game.toml` fest, und `psxrecomp/tools/package_title_release.py` lehnt einen veralteten Stand ab.
- **Retro-Catalog:** Der Eintrag liegt als Entwurf in `docs/upstream/retro-catalog-medal-of-honor-pal-psx.json`. Eingereicht wird über das Formular des Katalogs, Ablauf und Fallstricke stehen in `D:\RecompDev\PS1_RECOMP_NOTES.md` (Abschnitt Retro Launcher).

## Debug-Port

Nur im Dev-Build. Pro TCP-Verbindung geht genau eine JSON-Zeile hin und eine zurück, z. B. `{"id":1,"cmd":"ping"}`. Python-Client: `tests/smoke/psxdbg.py` (`send(cmd, port=4370, payload=None, **params)`).

Fallstricke:
- `ping` beantwortet ein I/O-Thread ohne Bildzähler. Die Bildnummer liefert `frame`.
- `audio_wav` mit `start < 0` liefert die ältesten Samples. Für die jüngsten muss man `start = audio_stats.taps[i].frames - count` übergeben.
- `mdec_state.decode_macroblocks` gilt pro Bild, `dma_in_words` pro Film: Der Zähler behält den Stand des letzten Films und fängt beim nächsten Film wieder bei fast null an (`coverage_long.film_words`). Zurückgesetzt wird er vom MDEC-Reset (Bit 31 im Steuerregister, `mdec.c` `soft_reset`), den das Spiel zu Beginn eines Films schreibt.
- `psxdbg.send` wirft bei `{"ok": false}` keinen Fehler. Wo es zählt, die Antwort prüfen.
- `send(…, port=…)` ist der TCP-Port. Das Feld `port` eines Befehls (Controller-Port bei `set_input`/`press`/`clear_input`) gehört in `payload=`.
- Ein `clear_input` ohne `port` beendet auch die Eingabe für Port 2 und zieht damit den Test-Controller dort ab. Für Spieler 1 allein: `payload={"port": 1}`.
- `cd_read_log` protokolliert nur die Start-LBA jedes Lesevorgangs. `lba_lo`/`lba_hi` filtern `entries`, nicht `total`.
- `overlay_loader_status.dispatch_native` zählt nur DLL-Aufrufe. Treffer im statischen Shard stehen in `overlay_static_entries.total_hits`.

## Was nie ins Repo gehört

Disc-Images, BIOS-Dumps, Logs, `overlay_captures.json` (enthält Spielcode), Savestates und Speicherkarten. Die `.gitignore` deckt das ab. Vor jedem Commit trotzdem `git status` prüfen.
