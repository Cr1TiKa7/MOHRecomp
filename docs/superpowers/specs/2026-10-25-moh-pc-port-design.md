# Medal of Honor (PS1) – Nativer PC-Port: Design

- **Datum:** 2026-10-25
- **Status:** Abgenommen (2026-10-25)
- **Ablage:** `docs/superpowers/specs/` im Projekt-Repo `D:\RecompDev\MOHRecomp`

## 1. Ziel

**Von dir festgelegt:**
- Ein echter nativer PC-Port (`.exe`) von *Medal of Honor* für die PS1. Es soll kein Emulator sein. Das Projekt darf viele Sessions dauern.
- Zusätzlich zum nativen Lauf soll der Port können:
  - Maus + Tastatur mit freiem Zielen wie bei einem PC-Shooter
  - Widescreen und hohe Auflösung
  - eine höhere Bildrate als das Original
- Entwicklung zuerst privat. Später als öffentliches GitHub-Repo, ohne Spieldaten: Jeder braucht seine eigene Disc.
- Technische Basis ist PSXRecomp (Ansatz A).
- Reihenfolge der Features: Maus vor Widescreen.

**Meine Annahmen** (bitte korrigieren, falls falsch):
- Zielplattform ist nur Windows 11 x64. Linux- und macOS-Builds kommen höchstens später.
- Gamepad-Steuerung bleibt vollständig erhalten. Maus und Tastatur kommen zusätzlich dazu, sie ersetzen nichts.
- Basis ist ausschließlich deine PAL-Disc (siehe Abschnitt 2). Andere Regionen werden nicht unterstützt.

## 2. Ausgangslage

| | |
|---|---|
| Disc | `D:\Downloads\Medal of Honor (Europe)\Medal of Honor (Europe).cue`, ein Track MODE2/2352 |
| Version | PAL UK, Serial **SLES-02470**, Volume `MOH_PALUK`, 50 Hz |
| Boot-EXE | `SLES_024.70` (174 KB) |
| Code-Overlays | `SHELL.BIN` (353 KB, Menüs), `LEVEL.BIN` (592 KB, Einzelspieler), `LEVEL2P.BIN` (510 KB, Splitscreen) |
| Videos | 22 × `.STR` unter `/MOVIE/` |
| Leveldaten | `/DATA/MSN1…8/` (`.BSD`, `.TAF`, `.VB`, `.TSP`), Menüs als `.RSC` |

**PC-Stand:**
- Vorhanden sind Git 2.51 und Python 3.13.
- Es fehlen CMake, Ninja und ein C-Compiler.
- C: hat nur noch ~21 GB frei, deshalb kommt alles auf D:.
- Ein PS1-BIOS wird nicht gebraucht, das mitgelieferte OpenBIOS (MIT) reicht. Die `ps1_rom.bin` aus RPCS3 ist kein SCPH1001 und passt nicht.

## 3. Ansatz

**Gewählt: PSXRecomp** (`https://github.com/RetroPortingToolKit/psxrecomp`, Beta, sehr aktiv)
- Das Framework übersetzt den MIPS-R3000A-Code nach C und linkt ihn gegen eine PS1-Hardware-Runtime: GPU (OpenGL/Software), SPU, CD/XA, MDEC-Videos, GTE, Speicherkarte, Controller.
- Code, der noch nicht nativ vorliegt, fängt ein Interpreter auf.

**Verworfen:**
- **B, eigener Recompiler:** Grafik, Sound und CD müssten neu gebaut werden. Das sind Monate, bevor das erste Bild erscheint.
- **C, komplette Decompilation:** Das sind Jahre Arbeit. Teile davon passieren trotzdem, nämlich beim Verstehen von Kamera- und Steuerungscode.

**Bekannt:** Ein Shooter wurde mit PSXRecomp noch nie portiert, Medal of Honor auch nicht. Die nächsten Vorbilder:
- Ape Escape: Dual-Analog, 3D-Widescreen
- R4: Frame-Generation, Widescreen
- Vigilante 8: Second Offense: echte Zwischenbilder über Render Passes

## 4. Grundlage

### 4.1 Ordner (alles auf D:)

```
D:\RecompDev\
  Toolchain\      portables Paket cmake-clang-v1 (Clang, CMake, Ninja, ~209 MB)
  Temp\           TEMP/TMP für Builds, damit C: frei bleibt
  psxrecomp\      Framework-Klon (nur zum Scaffolding und Nachschlagen)
  MOHRecomp\      unser Projekt-Repo, privat
```

**Umgebung beim Bauen:**
- `PSXRECOMP_TOOLCHAIN_DIR` zeigt aufs Toolchain-Paket.
- `RETCOMM_TOOLCHAIN_DIR` zeigt auf D:, sonst landet der Paket-Cache unter `%LOCALAPPDATA%` auf C:.
- `TEMP`/`TMP` zeigen auf `D:\RecompDev\Temp`.

Falls das Kompilieren der Overlays `gcc` braucht, kommt MSYS2 MinGW nach `D:\msys64`. Ob Clang dafür reicht, ist noch offen (siehe Abschnitt 8).

### 4.2 Projekt-Repo

- **Anlegen:** mit `tools\new_project_layout\setup_project.ps1`, mit diesen Optionen:
  - `-Disc <cue> -Dir D:\RecompDev -Name MOHRecomp -Players 1`
  - `-Yes -EnableRecompUi -NoNetplay -NoFetchBoxart -NoGithub -Generate -EnableBuild`
  - Die genauen Flag-Namen prüfe ich vorher in der Hilfe des Skripts.
- **Framework:** PSXRecomp ist als Submodul auf einen festen Commit gepinnt. Aktualisiert wird nur bewusst, mit Notiz im Commit.
- **Eigene Framework-Änderungen** (z. B. für die Maus) liegen als Patches im Repo unter `patches/psxrecomp/` und werden beim Bauen angewandt. Erweist sich das als zu umständlich, wechseln wir auf einen eigenen Fork. Was allgemein nützlich ist, kann später als Pull Request zurück ins Framework.
- **Nie im Repo:** Disc-Image, BIOS-Dumps, Logs, `overlay_captures.json` (enthält Spielcode im Originalwortlaut), Speicherstände.
- **Features als Mod-Pakete:** Jedes Feature ist ein eigenes, abschaltbares Paket unter `mods/preloaded/packages/`:
  - `moh.input.mouse-keyboard`
  - `moh.enhancement.widescreen`
  - `moh.enhancement.frame-rate`

  Ist ein Paket aus, gilt das Originalverhalten.

### 4.3 Zwei Build-Varianten

- **Entwicklung:** `-DCMAKE_BUILD_TYPE=Release -DPSX_DEBUG_TOOLS=ON`. Öffnet den Debug-Port 4370 (siehe Abschnitt 7).
- **Spielen/Release:** normaler Release-Build ohne Debug-Port.

## 5. Meilensteine

Erst wenn ein Meilenstein erfüllt ist, beginnt der nächste. Jeder bekommt einen eigenen Umsetzungsplan.

| # | Meilenstein | Fertig, wenn… |
|---|---|---|
| **M0** | Einrichtung | Toolchain liegt auf D:, das Projekt ist angelegt und baut, die `.exe` startet bis zum ersten Bild (PS-Logo oder Legal-Screen). Die Spec ist ins Repo committet. |
| **M1** | Bis ins Menü | Intro-Videos laufen mit Ton. Das Hauptmenü (`SHELL.BIN`, nativ aus Disc-Daten) lässt sich per Fernsteuerung bedienen. Die Speicherkarte wird angelegt und erkannt. |
| **M2** | Erstes Level | Mission 1, Level 1 (`LEVEL.BIN`) lädt und ist ohne Absturz von Start bis Levelende spielbar: Ton, Gegner, Briefing, Ladebildschirme. Geprüft wird per Fernsteuerung, notfalls mit Speicher-Tricks (z. B. unverwundbar), oder du spielst es kurz durch. Nach Levelende speichern, nach Neustart laden: Das Spiel speichert erst nach Missionen, das Menü hat keinen Speicherpunkt (Änderung vom 2026-10-25). |
| **M3** | Ganzes Spiel | Alle Missionen laden und lassen sich abschließen. Die drei Overlays sind aus Disc-Daten vorkompiliert. Mit `PSX_OVERLAY_AUTOCOMPILE_OFF=1` liegt `dispatch_interp_fallback` laut `stall_report` unter 1 % aller Dispatches, gemessen über je 10 Minuten Menü, Einzelspieler-Level und Videos. Splitscreen startet ohne Absturz. Den kompletten Durchlauf spielst du. |
| **M4** | Maus + Tastatur | Freies Zielen mit der Maus, Empfindlichkeit einstellbar, Y-Achse invertierbar. WASD-Bewegung, Tasten in einer Konfigdatei frei belegbar. Gamepad funktioniert unverändert. Du nimmst das Spielgefühl ab. |
| **M5** | Bild | 16:9 ohne Objekte, die am neuen Bildrand verschwinden. HUD unverzerrt und korrekt verankert. Interne Auflösung bis 4K. Videos mit Pillarbox. Polygone wackeln nicht mehr (PGXP). |
| **M6** | Höhere Bildrate | Flüssige Darstellung über den originalen ~25 fps, auch beim schnellen Umsehen mit der Maus. Die Spiellogik läuft unverändert im Originaltempo. |
| **M7** | Veröffentlichung | Öffentliches GitHub-Repo, Release-Zip ohne Spieldaten, Lizenzhinweise, README mit Anleitung „eigene Disc einlegen“. Offene Rechtsfragen aus Abschnitt 9 sind geklärt. |

## 6. Feature-Design

### 6.1 Overlays nativ machen (M1–M3)

- **Bevorzugt, aus Disc-Daten:** Ein Rezept `aot/overlays.json` beschreibt `SHELL.BIN`, `LEVEL.BIN` und `LEVEL2P.BIN` als `images[]` mit `method: "fixed_address_files"`:
  - `load_addr` wird über `checks[].method: "words"` gegen den Lader-Code in der Boot-EXE abgesichert.
  - Daraus entsteht mit `static_output: "generated/overlays_static.c"` nativer Code.
  - Die Pipeline: `tools/aot_overlay_pipeline.py extract|static|release`, Prüfung mit `tools/audit_aot_cache.py`.
- **Ladeadresse und Einstiegspunkte:**
  - `SHELL.BIN` liegt an `0x80039F28`. Belegt ist das im RAM und im Lader-Code der Boot-EXE (`lui a1,0x8004` / `addiu a1,a1,0x9F28` bei `0x8003728C`). Seit M1 steht das im Rezept (`allow_missing`, die Pipeline findet die Funktionen selbst).
  - Die Overlays sind rohe Dateien ohne PS-X-Header. Das erste Wort ist 7 (`SHELL`), 5 (`LEVEL`) oder 6 (`LEVEL2P`).
  - `LEVEL.BIN` ersetzt `SHELL.BIN` an derselben Basis `0x80039F28`. Belegt ist das im RAM nach NEW GAME, Briefing und Laden, bei M1. Seit M2 steht es als zweites Image im Rezept, und Mission 1, Level 1 läuft mit 50 Bildern/s.
  - `LEVEL2P.BIN` (Splitscreen) liegt ebenfalls an `0x80039F28`. Belegt ist das im RAM nach MULTIPLAYER → START GAME (Overlay-Wort 6), bei M3. Seit M3 steht es als drittes Image im Rezept (13.664 native Einstiege), `mp_smoke` prüft den Splitscreen.
  - Fünf Funktionen der Boot-EXE rufen nur die Overlays auf, darunter der Stapel-Umschalter `0x8001535C`. Sie stehen seit M3 als Seeds in `seeds/ghidra_funcs.txt`, sonst liefen sie bei jedem Aufruf interpretiert.
- **Übergangslösung:** Mit `[runtime] overlay_cache = true` wird Code beim Spielen eingefangen und mit `tools/compile_overlays.py` kompiliert. Was fehlt, läuft im Interpreter: korrekt, aber langsamer.
- **Fortschritt messen:**
  - `tools/stall_report.py` vergleicht `dispatch_native` mit `dispatch_interp_fallback`.
  - Dazu kommen `overlay_loader_status` und `dirty_ram_stats`.
- **Fehlende Funktionen** in der Boot-EXE kommen als Seeds nach `seeds/ghidra_funcs.txt`, danach wird neu generiert.

### 6.2 Maus + Tastatur (M4)

**Warum nicht die Framework-Maus:**
- `PSXModMousePolicy` kann nur den rechten Analogstick überschreiben.
- Die Maus wird nur bei gedrückter linker Taste eingefangen.
- Validiert ist sie auf einem älteren Ape-Escape-Zweig.
- Für freies Zielen ist das ungeeignet.

**Vorgehen:**
1. **Blickwinkel finden:** Die Spielfigur wird per Debug-Port (`set_input`) gedreht. Mit `read_ram` und `watch` vergleiche ich den Speicher, bis die Werte für Gier (horizontal) und Nick (vertikal) im Spieler-Struct gefunden sind.
2. **Steuerfunktion finden:** Mit `wtrace_*` sehe ich, welcher Code in `LEVEL.BIN` diese Werte schreibt. Das ist die Funktion, die Controller-Eingaben in Drehung umsetzt.
3. **Einhaken:** Über `psx_mod_register_function_entry_plugin` oder `psx_mod_register_instruction_plugin`, mit Eintrag in `[recompiler] mod_function_entry_funcs` bzw. `mod_instruction_sites`. Pro Spiel-Frame wird der gesammelte Maus-Versatz × Empfindlichkeit direkt auf Gier und Nick addiert. Die vertikalen Grenzen des Spiels bleiben dabei bestehen.
   - Beide Hooks funktionieren laut Doku auch in Overlay-Shards.
   - Prüfung der Instruktion über `expected_word`, damit der Hook nur am richtigen Overlay greift.
4. **Rohe Mausbewegungen:** Die Framework-Runtime braucht eine Quelle für relative Mausbewegungen, also SDL-Relative-Mouse-Mode bei Fokus und Freigabe mit Esc. Das ist ein Patch nach `patches/psxrecomp/`. Ein solches Plugin-API für rohe Bewegungen gibt es laut Doku noch nicht.
5. **Tastatur und Maustasten:** `psx_mod_set_pad_transform` bildet Tasten auf Pad-Eingaben ab:
   - WASD → Bewegen/Seitschritt
   - Linksklick → Schießen
   - Rechtsklick und weitere Tasten frei belegbar
   - Die Belegung steht in einer Konfigdatei im Paket.
6. **Einstellungen:** Empfindlichkeit, Y-Invertierung und Tastenbelegung liegen in der Mod-Konfiguration und lassen sich ohne Neubau ändern.

**Offen, erst im Code zu klären:**
- Wie das Spiel analoge und digitale Eingaben verarbeitet
- Ob es eine Zielhilfe gibt, die mit der Maus stört. Falls ja, wird sie im Maus-Modus abschaltbar.
- Wie weit sich nach oben und unten zielen lässt

### 6.3 Bild (M5)

- **Auflösung und Stabilität:** die eingebauten Pakete `psx.enhancement.internal-resolution` (bis 4K) und `psx.enhancement.pgxp`.
- **16:9:** Das Paket `moh.enhancement.widescreen` ruft bei Aktivierung `psx_mod_set_fixed_display_aspect()` auf. Das kann zwei Dinge bedeuten:
  - GTE-X-Stauchung (Standardweg)
  - echtes breiteres Rendern (Native-Wide)

  Ob Native-Wide unter OpenGL geht, ist laut Doku widersprüchlich. Ich teste es zuerst, sonst nehmen wir die Stauchung.
- **Ausblenden am Rand (Culling):** Der Code, der Objekte außerhalb von 4:3 verwirft, liegt sehr wahrscheinlich in `LEVEL.BIN`. `psxrecomp-analyze --scan-widescreen` durchsucht nur die Boot-EXE, deshalb suche ich die Stellen von Hand:
  - Anhaltspunkt sind Laufzeitbeobachtungen, also Objekte, die am Rand verschwinden.
  - Die Stellen kommen als `[widescreen.cull]`-Einträge in die Konfiguration (`slti_sites`, `bltz_sites`, `screen_x_sites` usw.), danach wird neu generiert.
  - Ausblenden in Weltkoordinaten vor der Projektion braucht einen eigenen Patch.
- **HUD:** `auto_ui_anchor = "edges"`, damit Munition und Gesundheit an den Bildrand rutschen. Für einzelne Elemente `psx_mod_anchor_hud_primitive`. Das Fadenkreuz bleibt in der Mitte und unverzerrt.
- **Videos:** werden automatisch als 4:3 mit Pillarbox gezeigt.

### 6.4 Höhere Bildrate (M6)

**Grundsatz:** Die Spiellogik und die virtuelle PS1 laufen immer im Originaltempo. `psx_mod_set_native_vblank_rate` ist tabu, weil es die ganze Maschine beschleunigt.

- **Stufe 1, Frame-Generation des Frameworks:**
  - Einstellungen: `[video] render_thread = true`, `frame_generation = true`, `frame_generation_method = "redraw"`.
  - Braucht keinen spielspezifischen Code.
  - Bekannte Schwäche: Sie verwirft Zwischenbilder bei großen Drehungen und bei Schnitten. Mit Maussteuerung wäre das beim Umsehen spürbar. Außerdem kostet sie bis zu knapp einen Spiel-Frame Latenz.
  - Dient als schneller Zwischenstand und Vergleichsmaßstab.
- **Stufe 2, Render Passes (voraussichtlich das Ziel):**
  - Pro Logik-Frame wird der Zeichen-Code des Spiels mehrmals mit interpolierten Kamera- und Objektpositionen ausgeführt (`psx_mod_render_pass_frame`, `psx_motion_track/apply`).
  - Vorbild: `v82_frame_rate_plugin.cpp` aus dem Vigilante-8-Port.
  - Die Kamera kenne ich aus M4. Die Objekt-Transformationen muss ich zusätzlich finden.
- **Bonus Stufe 2:** Die Kamera der Zwischenbilder kann mit der aktuellen Mausposition gezeichnet werden statt interpoliert. Dadurch fühlt sich das Zielen direkt an, obwohl die Logik mit 25 Hz läuft.
- **Einschränkungen:** Interpolation läuft nur mit dem OpenGL-Renderer, VSync wird dabei abgeschaltet. Bei Videos ist sie ausgesetzt.

## 7. Teststrategie

- **Ich teste über den Debug-Port 4370** (Build mit `PSX_DEBUG_TOOLS=ON`), mit `tools/debug_client.py` oder eigenen Skripten. Pro Verbindung geht nur eine Anfrage.
  - **Eingaben:** `set_input` / `clear_input`, für exakte Abläufe `input_route_append` + `input_route_start at_frame=N`
  - **Bilder:** `present_shot` (fertiges Bild mit korrektem Seitenverhältnis), `screenshot`, `screenshot_hires`
  - **Speicher:** `read_ram`, `write_ram` (ein Byte pro Aufruf), `watch`, `wtrace_*`
  - **Zustände:** `savestate` / `savestate_status`. Die Parameter sind undokumentiert, ich lese sie im Quellcode nach. Damit lege ich Testpunkte an, z. B. Levelstart M1L1.
  - **Tempo:** `turbo enabled=1` für schnelles Durchlaufen
  - **Abdeckung:** `tools/stall_report.py`, `overlay_loader_status`
- **Fenster:** Das Spiel läuft mit `--hidden-window` oder sichtbar. Ton stumm über `SDL_AUDIODRIVER=dummy` (`PSX_HOST_MUTE` wirkt in dieser Runtime nicht, Stand M1).
- **Regressionsschutz:** Pro Meilenstein lege ich kurze Smoke-Skripte unter `tests/smoke/` an: Spiel starten, an Punkt X navigieren, Screenshot machen, auf Absturz und Bildinhalt prüfen. Vor jedem Commit laufen alle bisherigen Smoke-Tests.
- **Vergleich mit dem Original:** Wenn das Verhalten unklar ist, ziehen wir einen Emulator heran (z. B. DuckStation portabel auf D:). Nur bei Bedarf.
- **Du testest:** Spielgefühl (Maus, Flüssigkeit), kompletter Durchlauf in M3, alles Subjektive. Gefundene Fehler meldest du mit Mission/Level und möglichst einem Speicherstand.

## 8. Risiken und offene Punkte

| Risiko | Auswirkung | Umgang |
|---|---|---|
| Framework ist Beta und ändert sich täglich | Fehler in der Runtime, Updates können Dinge kaputt machen | Gepinnter Stand, Updates nur bewusst, Framework-Fehler als Patch oder Upstream-Issue |
| Noch nie ein Shooter portiert | Unbekannte Probleme mit GTE, Timing, Overlays | Meilensteine klein halten, früh in echte Levels (M2) |
| PAL/50 Hz nirgends dokumentiert | Timing- oder Tempo-Fehler | In M1/M2 Tempo mit dem Original vergleichen |
| ~~Ladeadresse von `LEVEL2P.BIN` noch unbelegt~~ | Rezept stimmt nicht | Erledigt in M3: ebenfalls `0x80039F28`, im RAM belegt, drittes Image im Rezept |
| Splitscreen mit echtem zweiten Controller nur per Debug-Port geprüft | Gerätezuweisung im Launcher könnte haken | Du prüfst einmal Tastatur + Gamepad (M3, `PLAYTEST.md`) |
| Maus braucht Framework-Patch | Wartung bei Framework-Updates | Patch klein halten, später Upstream-PR anbieten |
| Zielhilfe/Grenzen im Original | Maus fühlt sich „gebremst“ an | In M4 analysieren, im Maus-Modus abschaltbar machen |
| Frame-Gen verwirft schnelle Drehungen | Ruckeln beim Umsehen | Stufe 2 (Render Passes) einplanen |
| Native-Wide unter OpenGL unklar | Nur Stauchungs-Widescreen | Früh in M5 testen |
| Overlay-Kompilierung braucht evtl. `gcc` | Extra-Installation | MSYS2 auf D:, erst bei Bedarf |
| Spielgefühl kann ich nicht beurteilen | Abnahme hängt an dir | Klare Abnahmepunkte in M3/M4/M6 |

## 9. Rechtliches und Veröffentlichung

- **PSXRecomp-Lizenz:** PolyForm Noncommercial 1.0.0. Der Port darf nicht verkauft oder kommerziell genutzt werden. Ob das Zeigen auf einem monetarisierten Twitch-Stream als kommerzielle Nutzung zählt, ist eine Grauzone. Das klärst du vor dem ersten Stream damit.
- **Keine Spieldaten:** Repo und Release enthalten keine Spieldaten, kein BIOS und keine `overlay_captures.json`. Das Release-Zip enthält laut Framework-Checkliste keinen generierten C-Code.
- **Offen bis M7:** Die Framework-Checkliste sieht vor, `generated/` (aus dem Spielcode erzeugtes C) im Repo zu committen. Im öffentlichen Repo wäre das eine Ableitung des Originalcodes. Vor M7 entscheiden wir, ob `generated/` öffentlich wird oder Nutzer es selbst aus ihrer Disc erzeugen.

## 10. Nicht-Ziele

- Splitscreen über „startet ohne Absturz“ hinaus, Online-Multiplayer, Netplay
- HD-Texturpakete, neue Inhalte, Gameplay-Änderungen außer Steuerung und Zielhilfe
- NTSC- oder andere Disc-Versionen
- Linux- und macOS-Builds (vielleicht nach M7)
- Eine Decompilation des ganzen Spiels
