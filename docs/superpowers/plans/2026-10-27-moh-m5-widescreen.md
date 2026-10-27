# M5 Bild – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Im Spiel 16:9 ohne Objekte, die am neuen Bildrand verschwinden. Das HUD ist unverzerrt und an den Rändern verankert, das Fadenkreuz bleibt in der Mitte. Interne Auflösung bis 4K, Videos mit Pillarbox, weniger Polygonwackeln (PGXP).

**Architecture:**
- **Breitbild:** Das Mod-Paket `moh.enhancement.widescreen` mit dem statischen Plugin `moh.widescreen` schaltet bei Aktivierung 16:9 im **Native-Wide**-Modus des Frameworks ein. Die Zeichenfläche wird breiter, die Projektion bleibt 4:3, also nichts wird gestaucht.
- **Nur im Spiel:** Menüs, Ladebild und Videos bleiben 4:3.
- **Konfiguration:** Was am Rand fehlt (Himmel, ausgeblendete Polygone) und welche HUD-Teile an den Rand gehören, steht in `game.toml` `[widescreen]` / `[widescreen.cull]`. Die Werte findet die Erkundung in den Tasks 2–4.
- **Auflösung und PGXP:** über die eingebauten Pakete `psx.enhancement.internal-resolution` und `psx.enhancement.pgxp`. Task 5 misst, wie gut PGXP mit unseren vorkompilierten Overlays greift, und entscheidet die Voreinstellung.

**Tech Stack:** wie M4. Neu:
- `[widescreen]` / `[widescreen.cull]` in `game.toml`, danach `generate`
- Debug-Befehle `display_aspect`, `ws_nw`, `gpu_state` (Teil `ws`), `present_ring`, `ws_margin`, `gpu_frame_dump`, `ws_tag_stats`, `pgxp`, `geom_correction`, `video_info`
- `PSX_OVERLAY_NATIVE_OFF=1` zum Ausprobieren von Culling-Listen ohne Neugenerieren

**Spec:** `docs/superpowers/specs/2026-10-25-moh-pc-port-design.md`, Meilenstein M5, Abschnitte 4.2, 6.3 und 7.

## Vorab offen

- **M3:** fps-Tests (Task 0 aus M3) und der Rest der Kampagne.
- **M4:**
  - Abnahme nach `docs/PLAYTEST.md` („M4“)
  - fps-Tests mit Paket
  - vorgemerkter Wunsch: freies Hoch/Runter ohne Rechtsklick, falls Schüsse dem geneigten Blick folgen (Ledger M4)
- M5 blockiert nichts davon. Kollisionen gibt es nur in `game.toml` und `generated/`: Beide Aufgaben ändern sie. Was zuerst kommt, wird dort zuerst committet.

## Fakten aus der Erkundung (2026-10-27, Dev-Build, M1L1)

Erhoben mit Wegwerf-Skripten (`m5_probe1.py`, `m5_probe2.py`, `scan_cmp.py`, nicht im Repo).

- **Bildgröße:** 512 × 256 (`video_info`: `display_w 512`, `internal_lines 256`, `reference_lines 240`). Die Standard-Suchwerte des Frameworks (320 Pixel, `screen_w_imms` 0x140/0x141) passen also nicht.
- **Native-Wide unter OpenGL funktioniert:**
  - Testweg: Kopie von `game.toml` plus `[widescreen] native_wide = true, gte_game_mode = true`, im Spiel der Debug-Befehl `display_aspect num=16 den=9`.
  - Ergebnis: `gpu_state.ws.mode = 2`, `nw_extra = 170` (85 Pixel je Seite), `present_ring` meldet den Pfad `wide` mit 682 Pixeln Breite.
  - Der Screenshot (`screenshot`) ist dann 682 × 256 groß.
- **Was im 16:9-Bild fehlt (M1L1):**
  - Der Boden reicht bis an den Rand.
  - Oben links und rechts ist der dunkle Himmel schwarz. Vermutlich ist er eine 4:3-Hintergrundfläche.
  - Große Polygone nahe dem Rand fehlen ganz, mit schräger Kante (eine Hecke links). Das Spiel verwirft also Polygone in Bildschirmkoordinaten.
  - Im Code von `LEVEL.BIN` (von der Disc) stehen 22 × `slti rX, rY, 0x200` (512) und einige Vergleiche gegen 0x100/0x101/0x1FF/0x400. Das sind die Hauptkandidaten (Liste: `scan_cmp.py` im Scratchpad).
- **Menü:** Mit `gte_game_mode = true` wird auch das Hauptmenü breit. Seine 3D-Raumszene endet an den 4:3-Kanten, außen bleibt Schwarz. Menüs sollen deshalb 4:3 bleiben, gesteuert über ein Spiel-Kriterium statt über den GTE-Detektor (Task 1).
- **HUD:** Kompass oben links und Munition oben rechts bleiben in Native-Wide auf ihren 4:3-Positionen, also 85 Pixel vom Rand eingerückt. Das Fadenkreuz bleibt mittig.
- **Werkzeug fürs HUD:** `[widescreen] nw_left_hud_packet_lo/hi` verschiebt alle Pakete aus einem Speicherbereich nach Bilddritteln: links an den linken Rand, rechts an den rechten, die Mitte bleibt (`gpu.c` `ws_nw_hud_shift`).
- **Werkzeug für den Hintergrund:** `[widescreen] nw_backdrop` zieht einen bildschirmfüllenden 2D-Hintergrund auf volle Breite (`gpu.c`, „Native-wide full-frame 2D backdrop stretch“).
- **4K:** Paket `psx.enhancement.internal-resolution` mit `resolution = "4k"`:
  - Faktor 9, FBO 9216 × 4608, `gl_clamp_reason 0`
  - 20,0 ms pro Frame (50 fps) bei 4:3, `scene_gpu_ms_avg` 9,9
- **PGXP:** Paket `psx.enhancement.pgxp` mit unserer Runtime ohne PGXP-Variante, M1L1, 2 s Drehen:
  - `active 1`
  - Dreiecke: `tri_precise` 2 282, `tri_mixed` 84 677, `tri_native` 114 391, also etwa 1 % ganz, 42 % teilweise, 57 % gar nicht korrigiert
  - `tolerance_reject` 364 386 von 604 050 Abfragen
- **PGXP-Variante:** Die Runtime-Variante mit PGXP (`PGXP` in `psxrecomp_add_game_runtime`) verträgt sich laut `aot_overlay_pipeline.py:1156` nicht mit statischen Overlay-Shards. Das misst Task 5.
- **Videos:** Laut Framework werden MDEC-Videos automatisch 4:3 mit Pillarbox gezeigt (`main.cpp:9839`). Belegt wird das in Task 1.

## Abweichungen von der Spec (Task 6 trägt sie ein, Nutzer gibt frei)

1. **HUD-Verankerung:** Die Spec sah `auto_ui_anchor = "edges"` vor. Das wirkt nur im Stauch-Modus, in Native-Wide ist es aus (`gpu.c` `ws_active()`). Stattdessen kommen `nw_left_hud_packet_lo/hi` (HUD-Paketbereich, Verschiebung nach Bilddritteln) oder `psx_mod_anchor_hud_primitive` zum Einsatz (Task 4).
2. **Breitbild nur im Spiel:** Die Spec sagt dazu nichts. Weil die Menüszenen nur 4:3 groß gebaut sind, steuert ein Spiel-Kriterium den Wechsel (Task 1), nicht der allgemeine GTE-Detektor.
3. **PGXP-Voreinstellung:** Die Spec nennt nur das Paket. Task 5 misst und entscheidet, ob es per Override standardmäßig an ist und ob eine eigene Runtime-Variante nötig ist.

## Global Constraints

- **Alles aus M0–M4 gilt weiter:**
  - D: für alles
  - keine Spieldaten, Savestates, Speicherkarten oder Screenshots im Repo
  - `. D:\RecompDev\dev-env.ps1`
  - Commits mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  - kein Push
  - Python nur Standardbibliothek
  - `SDL_AUDIODRIVER=dummy`
  - Testinstanzen nur per PID beenden
  - Dateien mit LF
  - Framework unverändert auf `7097d53`
- **Bildraten-Tests** nur, wenn der Nutzer den PC freigibt. Alle anderen Tests dürfen nebenher laufen.
- **Paket standardmäßig aus:** `moh.enhancement.widescreen` hat `default_enabled = false`. Ohne Paket bleibt das Bild 4:3 wie in M4, und alle bisherigen Smoke-Tests laufen unverändert.
- **Keine Stauchung:** Native-Wide ist Pflicht. Fällt es aus, wird pillarboxed und nie gestreckt.
- **Werte aus der Erkundung** stehen als Konstanten in `tests/smoke/moh.py` (Präfix `WS_`), mit Fundstelle im Kommentar.
- **Culling-Stellen nur über `[widescreen.cull]`:** keine eigenen Code-Patches. Bei 4:3 sind sie wirkungslos, das stellt das Framework sicher.

## Review Focus

1. **2D-Bildschirme im Breitbild:** Menü, Briefing, Ladebild, Pausenmenü, Missionsauswertung und Videos sollen 4:3 bleiben (Pillarbox), nicht halb schwarz und nicht gestreckt (Task 1, Fälle Menü, Video, Ladebild, Pause).
2. **Aufploppen am Rand beim schnellen Drehen:** Polygone dürfen am neuen Rand nicht verschwinden, auch in anderen Levels, Innenräumen und mit Gegnern am Rand (Task 3: mehrere Blickrichtungen in drei Levels).
3. **HUD in der Bildmitte:** Fadenkreuz, Meldungen und Untertitel bleiben mittig. Nur Eckelemente wandern an den Rand (Task 4: Fadenkreuz im Zielmodus prüfen).
4. **Splitscreen mit Breitbild-Paket:** startet und bleibt bedienbar, als 4:3 oder sauber breit, aber ohne Absturz (Task 6: `mp` mit Paket).
5. **Leistung bei 4K + Breitbild + PGXP:** mindestens 48 fps im Level. Gemessen wird erst, wenn der PC frei ist (Task 6, Schritt für den Nutzer).

---

### Task 1: Breitbild-Paket, nur im Spiel

**Files:**
- Create: `mods/preloaded/packages/moh.enhancement.widescreen/1.0.0/manifest.toml`
- Create: `src/widescreen/moh_widescreen_plugin.c`
- Modify: `CMakeLists.txt` (`target_sources`)
- Modify: `game.toml` (`[widescreen]`: Spiel-Kriterium, siehe Step 2)
- Create: `tests/smoke/widescreen_smoke.py`, `tests/smoke/test_widescreen.py`
- Modify: `tests/smoke/modstate.py` (mehrere Pakete), `tests/smoke/test_modstate.py`
- Modify: `tools/run-smoke.ps1` (`-Test widescreen`)

**Interfaces – Produces:**
- Paket `moh.enhancement.widescreen`, Feature `widescreen`, Plugin `moh.widescreen`.
- `modstate.enabled(build_dir, values, features=None)`:
  - `features` ist eine Liste von `(package_id, feature_id, values)`.
  - Ohne `features` gilt wie bisher das Maus-Paket.
- In `widescreen_smoke.py`:
  - `wide_state(port) -> dict`: `gpu_state.ws` plus der letzte `present_ring`-Eintrag als `{"path": str, "present_w": int, "nw_extra": int}`.
  - `band_dark_fraction(png_path, nw_extra) -> (left, right)`: Anteil der Pixel mit Helligkeit unter 8 in den beiden äußeren Streifen der Breite `nw_extra // 2`.

- [ ] **Step 1: Failing tests**
  - `test_modstate.py`: zwei Features in einer Datei, beide `enabled = true`, Werte je Feature getrennt.
  - `test_widescreen.py`:
    - `band_dark_fraction` an zwei kleinen PNGs (mit `pngcheck`-Helfern aus `test_helpers` erzeugt): schwarze Streifen → (1.0, 1.0), helle → (0.0, 0.0).
    - `present_entry([...])` liest Pfad, Breite und `nw_extra` aus einem `present_ring`-Ereignis. Feldreihenfolge wie im Probe-Bericht: `[seq, frame, path, present_w, disp_w, disp_h, …, nw_extra, …]`. Vor dem Test im Quelltext von `handle_present_ring` (`debug_server.c:11504`) nachprüfen.
- [ ] **Step 2: Spiel-Kriterium festlegen.** Mit einer Kopie von `game.toml` (wie in der Probe, per `--game`) und `display_aspect 16:9` beide Varianten ausprobieren und die erste nehmen, die alle Fälle aus Step 5 schafft:
  - (a) `[widescreen] gameplay_state_addr = "0x80039F28"`, `gameplay_state_values = [5]` (`LEVEL.BIN` geladen)
  - (b) `psx_mod_set_world_scene_predicate` im Plugin: 1, wenn der Gier-Hook (Stelle `0x800801E0`, Wort `0xAE020184`, nur Spieler) in den letzten 12 VBlanks lief. Die Wächter-Logik wie in `moh_mouse_plugin.c` `is_player` übernehmen, eigene Registrierung unter `moh.widescreen`.
  - Ergebnis ins Ledger und als `WS_GAMEPLAY_GATE` in `moh.py`.
- [ ] **Step 3: Paket und Plugin.**
  - Manifest Format 11, Gruppe „Visual“, `default_enabled = false`, `[[plugin]] id = "moh.widescreen"`.
  - Aktivierung: `psx_mod_set_fixed_display_aspect(16, 9)`, `psx_mod_set_native_wide_projection_correction(1)`, dazu bei (b) das Prädikat.
- [ ] **Step 4:** Unit-Tests grün, Dev-Build bauen.
- [ ] **Step 5: `widescreen_smoke.py`** (Paket an, `display_aspect 16 9` nur falls das versteckte Fenster es braucht):
  - Intro-Video: `present_ring`-Pfad ist nicht `wide`.
  - Hauptmenü: nicht `wide`.
  - Ladebild nach NEW GAME: nicht `wide`.
  - M1L1 im Spiel: `wide`, `nw_extra == 170`, Screenshot 682 Pixel breit.
  - Pause (Start): nicht `wide`, oder der Pausenbildschirm ist ein Overlay über dem Level, dann `wide` mit der Szene dahinter. Festhalten, was das Spiel zeigt, als Konstante `WS_PAUSE_PATH`.
  - Paket aus: im Level nicht `wide`.
- [ ] **Step 6:** `-Test widescreen` → OK. `-Test menu` ohne Paket → OK.
- [ ] **Step 7: Commit:** „M5: widescreen package, 16:9 only in gameplay“.

### Task 2: Himmel und Hintergrund in den Seitenstreifen

**Files:**
- Modify: `game.toml` (`[widescreen]` `nw_backdrop` oder `[widescreen.cull]`, je nach Befund)
- Modify: `tests/smoke/widescreen_smoke.py` (Fall „Seitenstreifen“), `tests/smoke/moh.py` (`WS_VIEWS`, `WS_MAX_DARK`)

- [ ] **Step 1: Befund.**
  - In M1L1 bei 16:9 (Blickrichtung wie `view0` der Probe) liefert `gpu_frame_dump` die Primitive des Frames.
  - Gesucht ist das Primitiv, das bei 4:3 den Himmel füllt: ein bildschirmfüllendes Rechteck oder Polygon, das zuerst gezeichnet wird.
  - Notieren: Typ, Koordinaten, Paketadresse.
- [ ] **Step 2: Lösung wählen.**
  - Ist es ein 2D-Vollbild-Hintergrund: `nw_backdrop` (Schlüssel und Werte aus `gpu.c` lesen) eintragen.
  - Ist es Geometrie, die am Rand ausgeblendet wird: Das gehört zu Task 3. Dieser Task endet dann mit dem Befund im Ledger.
- [ ] **Step 3: Test.**
  - `widescreen_smoke` dreht in M1L1 in die Blickrichtungen `WS_VIEWS` (z. B. 0°, 90°, 180°, 270°, gesetzt über `write_ram` auf die Gier wie in M4 Task 1).
  - `band_dark_fraction` beider Streifen muss ≤ `WS_MAX_DARK` sein.
  - Den Schwellwert nach dem Befund festlegen: der dunkelste korrekte 4:3-Bereich derselben Ansicht plus 0,05.
- [ ] **Step 4:** Test zuerst rot (ohne Änderung), dann grün. Commit: „M5: fill the side bands' sky“.

### Task 3: Ausblenden am Rand abschalten

**Files:**
- Modify: `game.toml` (`[widescreen.cull]`)
- Modify: `generated/` (neu erzeugt)
- Modify: `tests/smoke/widescreen_smoke.py` (Fall „Kanten“ in drei Levels), `tests/smoke/moh.py` (`WS_EDGE_LEVELS`)

- [ ] **Step 1: Kandidaten.**
  - Die 22 `slti …, 0x200` und die übrigen Bildschirmvergleiche aus `scan_cmp.py`, dazu `disasm` ihrer Umgebung im laufenden Spiel.
  - Typisches Muster: SX aus `SXY`/`swc2`, Vergleich gegen 0 und 512, Sprung über das Einhängen ins OT.
  - Die Kandidaten nach Funktion gruppieren.
- [ ] **Step 2: Ausprobieren ohne Neugenerieren.**
  - Start mit `PSX_OVERLAY_NATIVE_OFF=1` und `PSX_OVERLAY_AUTOCOMPILE_OFF=1`: `LEVEL.BIN` läuft im Interpreter, der die `[widescreen.cull]`-Listen zur Laufzeit liest.
  - Je Gruppe die passende Liste eintragen (`slti_sites`, `slti_lower_sites`, `bltz_sites`, `screen_x_sites` usw., Bedeutung in `docs/WIDESCREEN.md` 263–352).
  - Dazu `screen_w_imms = ["0x200", "0x201"]`, falls `auto_screen_x` getestet wird.
  - Prüfen: Die Kanten-Ansichten aus Step 4 haben keine fehlenden Polygone mehr. Gemessen an `band_dark_fraction` und am Vergleich mit `ws_margin value=200`: mehr Rand ändert nichts mehr, wenn nichts mehr verworfen wird.
  - Greift das Interpreter-Ausprobieren nicht, wird je Versuch `generate` ausgeführt und neu gebaut.
- [ ] **Step 3: Festschreiben.**
  - Die wirksame Liste kommt in `game.toml`, dann `generate`. Im Diff von `generated/` ändern sich nur diese Stellen.
  - Dev- und Release-Build neu bauen.
- [ ] **Step 4: Test** in `widescreen_smoke`, für jedes Level aus `WS_EDGE_LEVELS` = M1L1, M3L1, M7L1 (Sprung wie im Sweep):
  - 4 Blickrichtungen, `band_dark_fraction` ≤ `WS_MAX_DARK`.
  - Zweite Prüfung: Ein Screenshot mit `ws_margin value=200` unterscheidet sich in den Seitenstreifen um weniger als 2 (`mean_abs_diff` der Streifen) vom normalen.
  - Erst rot (vor Step 3), dann grün.
- [ ] **Step 5:** `-Test coverage` und `-Test sweep -Mission 1` ohne Paket weiter OK. Die Culling-Stellen sind bei 4:3 wirkungslos.
- [ ] **Step 6: Commit:** „M5: widen LEVEL.BIN's screen-edge culling“, mit `generated/`.

**Abbruch:** Liegt das Ausblenden in Weltkoordinaten vor der Projektion (Sichtkegel), helfen die Bildschirmlisten nicht. Dann Befund mit `disasm` belegen, `[aspect_cone]`/`[[angle]]` aus `docs/config_schema.md` prüfen und dem Nutzer berichten, bevor ein eigener Patch entsteht.

### Task 4: HUD an die Ränder

**Files:**
- Modify: `game.toml` (`[widescreen] nw_left_hud_packet_lo/hi`, oder Tags im Plugin)
- Modify: `src/widescreen/moh_widescreen_plugin.c` (nur falls Tags nötig)
- Modify: `tests/smoke/widescreen_smoke.py` (Fall „HUD“), `tests/smoke/moh.py` (`WS_HUD_PACKET_LO/HI`)

- [ ] **Step 1: Befund.**
  - `gpu_frame_dump` in M1L1: Paketadressen der Kompass-Primitive (oben links) und der Munitionsanzeige (oben rechts), dazu von Fadenkreuz und Waffe.
  - Liegen die HUD-Pakete in einem eigenen Bereich, ohne Welt-Polygone darin, dann `nw_left_hud_packet_lo/hi` darauf setzen.
  - Sonst `psx_mod_anchor_hud_primitive` je Frame über einen Hook an der HUD-Zeichenfunktion. Diese Entscheidung kommt ins Ledger.
- [ ] **Step 2: Test** mit einem neuen Helfer `find_patch_x(wide_png, narrow_png, box, search) -> int`.
  - Er schneidet `box = (x0, y0, x1, y1)` aus dem 4:3-Bild (512 breit) aus und sucht im 16:9-Bild (682 breit) die x-Verschiebung mit der kleinsten mittleren Abweichung, über den Bereich `search` (z. B. 0…170).
  - Unit-Test mit zwei erzeugten PNGs: Ein Muster bei x = 10 im schmalen und bei x = 180 im breiten Bild ergibt 170.
  - Kästen als Konstanten `WS_HUD_COMPASS_BOX`, `WS_HUD_AMMO_BOX`, `WS_CROSSHAIR_BOX` in `moh.py`, aus den 4:3-Screenshots der Probe abgelesen.
  - Erwartet im Level, gleiche Ansicht einmal bei 4:3 und einmal bei 16:9:
    - Kompass Verschiebung 0 ± 2 (linker Rand)
    - Munition 170 ± 2 (rechter Rand)
    - Fadenkreuz im Zielmodus (R2 per Host-Gamepad) 85 ± 2 (Mitte)
  - Erst rot (Kompass liegt bei 85), dann grün.
- [ ] **Step 3: Commit:** „M5: anchor the corner HUD to the wide edges“.

### Task 5: Auflösung und PGXP

**Files:**
- Create (je nach Entscheidung): `mods/preloaded/packages/psx.enhancement.pgxp/1.0.0/manifest.toml` (Override, gleiche ID und Version)
- Modify: `game.toml` `[video]` (z. B. `pgxp_tolerance`, nur falls gemessen besser)
- Modify: `tests/smoke/widescreen_smoke.py` oder neu `tests/smoke/pgxp_smoke.py`, `tests/smoke/moh.py` (`PGXP_MIN_CORRECTED`)

- [ ] **Step 1: Messen.** Gleiche Route in M1L1 (2 s Drehen, 2 s Laufen), `geom_correction`. Der Anteil `(tri_precise + tri_mixed) / alle` in vier Varianten:
  - (a) Standard
  - (b) `pgxp_tolerance` höher (Wert aus `docs/ENHANCEMENTS.md`)
  - (c) `cpu_mode = true`
  - (d) Runtime mit `PGXP` in `psxrecomp_add_game_runtime`, in eigenem Build-Ordner `build-pgxp`
  - Bei (d) zusätzlich prüfen, ob die statischen Shards weiter laufen (`overlay_loader_status`, Interpreter-Anteil < 1 %).
- [ ] **Step 2: Entscheiden** und ins Ledger:
  - Die Variante mit dem höchsten korrigierten Anteil, bei der der Interpreter-Anteil < 1 % bleibt und `sweep -Mission 1` OK ist.
  - `PGXP_MIN_CORRECTED` = gemessener Anteil minus 5 Prozentpunkte.
  - Bringt (d) nichts oder bricht die Shards: bei der Runtime ohne PGXP-Variante bleiben.
- [ ] **Step 3: Voreinstellung.**
  - PGXP standardmäßig an per Override-Manifest (`default_enabled = true`), wenn Step 2 keine Bildfehler zeigt (Screenshot-Vergleich in drei Levels: keine fehlenden Flächen, `mean_abs_diff` zum PGXP-losen Bild < 12).
  - Die interne Auflösung bleibt Wahl des Spielers (Launcher), bis 4K belegt.
- [ ] **Step 4: Test** `pgxp_smoke`: Mit Paket ist der korrigierte Anteil ≥ `PGXP_MIN_CORRECTED`. Bei 4K ist `video_info.effective_scale == 9` und `gl_clamp_reason == 0`. Erst rot, dann grün.
- [ ] **Step 5: Commit:** „M5: PGXP default and resolution check“.

### Task 6: Regression, Doku, Spec, Abnahme

**Files:**
- Modify: `docs/DEVELOPMENT.md` (Abschnitt „Breitbild“), `docs/PLAYTEST.md` (Abschnitt „M5“), Spec (Abschnitt 6.3, Risikozeile Native-Wide)

- [ ] **Step 1:** Mit Breitbild-Paket (`MOH_SMOKE_PAD_LAYER` nicht nötig, das Paket ändert keine Eingaben):
  - `-Test menu`, `-Test mp`, `-Test sweep -Mission 1`, `-Test widescreen`, alle OK
  - Ohne Paket `-Test intro` und `-Test coverage` OK
- [ ] **Step 2:** Unit-Tests komplett grün.
- [ ] **Step 3: Doku und Spec.** In `PLAYTEST.md` die Punkte für den Nutzer:
  1. Paket einschalten.
  2. 16:9 im Level, Menüs und Videos 4:3.
  3. Nichts verschwindet beim Drehen am Rand, in mehreren Levels.
  4. HUD in den Ecken, Fadenkreuz mittig.
  5. 4K einstellen, flüssig?
  6. PGXP an und aus: wackelt es noch?
  7. Splitscreen mit Paket startet.
  8. Mit dem Maus-Paket zusammen: alles wie gewohnt?
- [ ] **Step 4: Abschluss-Review:** frischer Reviewer über die M5-Commits.
- [ ] **Step 5: Commit:** „M5: docs, spec update and playtest checklist“.
- [ ] **Step 6:** Nutzer um Abnahme bitten. Der fps-Test mit 4K + Breitbild + PGXP (`-Test level` mit Paketen) läuft erst, wenn er den PC freigibt.
