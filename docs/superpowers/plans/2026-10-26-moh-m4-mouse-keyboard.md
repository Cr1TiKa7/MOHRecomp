# M4 Maus + Tastatur – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Mit der Maus dreht sich die Spielfigur frei, im Zielmodus des Spiels (rechte Maustaste) neigt die Maus den Blick. Empfindlichkeit und Y-Invertierung sind einstellbar. WASD bewegt, alle Tasten stehen in einer Konfigdatei. Das Gamepad funktioniert weiter.

**Architecture:**
- **Statisch gelinktes Plugin `moh.mouse-look`** im Mod-Paket `moh.input.mouse-keyboard`, schaltbar im Launcher (Mods).
- **Mausbewegungen:** kommen roh über die Maus-API der Runtime (`psx_mod_set_local_mouse_policy`). Klick fängt die Maus ein, Esc gibt sie frei. Ein Framework-Patch ist nicht nötig.
- **Winkel:** Zwei Instruktions-Hooks direkt vor den Speicherbefehlen, mit denen das Spiel Gier und Nick des Spielers schreibt, addieren den Mausversatz. Gier wirkt immer, Nick nur, solange das Spiel im Zielmodus selbst Nick schreibt.
- **Rechenlogik:** Umrechnung, Rundungsrest, Invertierung, Grenzen und Freigabe-Regel stecken in einer reinen C-Datei mit eigenen Unit-Tests.
- **Tasten:** über die `keybinds.ini` des Frameworks, die auch die Launcher-Seite Controls bearbeitet. Maustasten lassen sich dort als `Mouse1`…`Mouse5` belegen.

**Tech Stack:** wie M3. Neu:
- C11 im Spielprojekt (`src/mouse/`), registriert über `PSX_MOD_CONSTRUCTOR`
- `[recompiler] mod_instruction_sites`
- Mod-Manifest Format 11
- Debug-Befehle `mod_cmd`, `mod_counters`
- CTest für den C-Unit-Test

**Spec:** `docs/superpowers/specs/2026-10-25-moh-pc-port-design.md`, Meilenstein M4, Abschnitte 4.2, 6.2 und 7. Die Spec-Änderungen aus Task 6 braucht der Nutzer vor der Umsetzung (siehe „Abweichungen von der Spec“).

## Vorab offen (aus M3)

- **fps-Tests:** M3 Task 0 (`run-smoke -Test all` und `-Test save`) wartet weiter darauf, dass der Nutzer den PC freigibt.
- **Durchspielen:** Der Nutzer spielt die Kampagne nebenher weiter, erledigt sind Mission 1 Level 1–3. M3 wird abgeschlossen, sobald beides fertig ist. M4 blockiert das nicht: Ein Durchlauf mit dem M4-Build zählt auch für M3, weil M4 nur die Eingabe ändert.

## Fakten aus der Erkundung (2026-10-26, Dev-Build, M1L1)

Erhoben mit Wegwerf-Skripten (`m4_probe*.py`, nicht im Repo).

- **Spieler-Struct:**
  - `*(0x8009DC44)` = Besitzer-Objekt (`0x800EE860`), `*(Besitzer + 0x388)` = Spieler (`0x800EEC2C`).
  - Der Magazinzähler aus M2 (`0x800EEC92`) liegt bei Spieler + 0x66 und passt dazu.
  - Die Kamera kopiert die Werte pro Frame (`0x80047D78`, `0x80050760`). Schreiben in die Kamera-Kopie wäre wirkungslos.
- **Gier:**
  - 16.16-Festkomma bei Spieler + 0x184 (`0x800EEDB0`), der obere Halbwert ist der Winkel.
  - Er läuft über 4096 hinaus, ohne umzubrechen.
  - Rechts drehen erhöht ihn, mit Beschleunigung (+2, +6, +12, … pro Frame).
- **Gier-Schreibstelle:**
  - `0x800801E0`, Wort `0xAE020184` = `SW $v0, 388($s0)`, im Delay-Slot von `JAL 0x800762D8`.
  - Davor steht `LW $v0, 388($s0)` / `LW $v1, 16($sp)` / `ADDU $v0, $v0, $v1`, also Gier += Drehrate.
  - Läuft einmal pro Spiel-Frame (25 Hz). In 0,5 s Drehen schrieb die Stelle nur `0x800EEDB0`.
- **Nick gibt es nur im Zielmodus:**
  - R2 halten zeigt ein Fadenkreuz. Steuerkreuz hoch/runter neigt dann die Kamera, die Figur läuft nicht.
  - Steuerkreuz links/rechts dreht im Zielmodus langsamer.
  - R2 loslassen setzt den Blick sofort auf waagerecht zurück.
  - Außerhalb des Zielmodus zielt das Spiel vertikal selbst, wenn **EASY AIM** an ist (Options → Controller).
- **Nick-Wert:**
  - 32 Bit bei Spieler + 0x17C (`0x800EEDA8`), 0 = waagerecht.
  - R2+hoch macht ihn negativ (−61 440 pro 0,12-s-Tipp), R2+runter positiv.
  - Loslassen von R2 setzt ihn auf 0.
  - Noch unbekannt sind Grenzen, Schreibstelle und Skalierung (Task 1).
- **Controller-Menü** (Options → Controller):
  - PLAYER 1/2, CONFIGURE (Belegungs-Drehknopf)
  - INVERT Y-AXIS (aus), EASY AIM (an), ZOOM AIM, FAST AIM
- **Tasten in Belegung 1:**
  - X schießt, R2 = Zielmodus, L2 = Ducken (Augenhöhe `0x80000024`: 28 → 188).
  - L1/R1 verändern das Bild, ohne die Gier zu ändern. Vermutlich ist das Seitschritt, Task 1 belegt es.
  - Quadrat, Kreis, Dreieck und Select zeigten allein gedrückt keine eindeutige Wirkung.
- **Analoges Pad:** Mit `set_input pad_type=1` reagiert das Spiel auf beide Sticks (links läuft, rechts dreht). Steuerkreuz und Tasten wirken weiter.
- **Maus-API der Runtime** (`psx_mod_set_local_mouse_policy`, gepinnter Stand `7097d53`):
  - liefert MOTION-Ereignisse mit Bruchteil-dx/dy und RESET-Ereignisse
  - fängt die Maus nur ein, wenn Spieler 1 als **analoges** Pad gemeldet wird, das Fenster den Fokus hat und `eligible()` 1 liefert
  - `psx_mod_set_local_mouse_persistent_capture(1)`: Ein Klick fängt ein (dieser Klick erreicht das Spiel nicht), Esc gibt frei.
  - Debug-Eingaben (`set_input`/`press`), `--hidden-window`-Läufe ohne Fokus und Netplay schalten sie ab. Die Einfang-Strecke kann nur der Nutzer prüfen.
- **Savestates:** `savestate op=load` direkt nach dem Boot hat nicht gegriffen. Die Tests gehen wie bisher über NEW GAME ins Level.

## Abweichungen von der Spec (Task 6 trägt sie ein, Nutzer gibt frei)

1. **Kein Framework-Patch:** Die Runtime liefert rohe Mausbewegungen bereits (siehe oben). `patches/psxrecomp/` bleibt leer.
2. **Nick nur im Zielmodus:**
   - Das Spiel hat außerhalb des Zielmodus keinen Nickwinkel. Ein frei gehaltener Nick würde die Schusslogik ändern, denn Schüsse folgen dort der Zielhilfe, nicht dem Blick.
   - Deshalb dreht die Maus immer und neigt nur bei gehaltener rechter Maustaste (= R2).
   - Die Grenzen des Spiels gelten weiter.
3. **Tasten über `keybinds.ini`** statt `psx_mod_set_pad_transform` und einer Konfigdatei im Paket. Der Pad-Transform sieht keine Tasten, nur das fertige Pad. Die Launcher-Seite Controls bearbeitet dieselbe Datei.
4. **Analoges Pad bei aktivem Paket:** Spieler 1 wird als DualShock gemeldet (`psx_mod_set_controller_mode_override`), sonst verweigert die Maus-API das Einfangen.
   - Gamepad: Steuerkreuz und Tasten wirken wie bisher, zusätzlich die Sticks.
   - Ist das Paket aus, bleibt alles digital wie in M3.
5. **Zielhilfe:** Das Spiel hat sie als eigene Option (EASY AIM). Das Paket ändert daran nichts. Die Checkliste empfiehlt, sie für die Maus probeweise auszuschalten.

## Global Constraints

- **Alles aus M0–M3 gilt weiter:**
  - D: für alles
  - keine Spieldaten, Savestates, Speicherkarten oder Screenshots im Repo
  - `. D:\RecompDev\dev-env.ps1`
  - Commits mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  - kein Push
  - Python nur Standardbibliothek
  - `SDL_AUDIODRIVER=dummy`
  - Testinstanzen nur per PID beenden
  - Dateien mit LF (`newline=""`)
- **Framework unverändert:** Submodul `psxrecomp` bleibt auf `7097d53`, keine Patches.
- **Bildraten-Tests** (`level`, `all`) nur, wenn der Nutzer den PC freigibt. Alle anderen Tests dürfen nebenher laufen.
- **Paket standardmäßig aus** (`default_enabled = false`). Ohne Paket verhalten sich Spiel und alle bisherigen Tests exakt wie in M3.
- **Keine Spielcode-Patches:** nur Register-Änderungen in den beiden Instruktions-Hooks, keine geänderten Code-Wörter.
- **Werte, die Task 1 festlegt**, stehen danach als Konstanten in `tests/smoke/moh.py` und `src/mouse/moh_addrs.h`, mit Fundstelle im Kommentar. Spätere Tasks benutzen nur diese Namen:
  - `PLAYER_OWNER_PTR_ADDR`, `PLAYER_PTR_OFFSET`, `PLAYER_YAW_OFFSET`, `PLAYER_PITCH_OFFSET`
  - `YAW_STORE_PC`, `YAW_STORE_WORD`
  - `PITCH_STORE_PC`, `PITCH_STORE_WORD`, `PITCH_STORE_REG`
  - `PITCH_MIN`, `PITCH_MAX`, `PITCH_SHIFT`
  - `YAW_UNITS_PER_TURN`
  - `PAUSE_FLAG_ADDR` (nur falls nötig, siehe Task 1 Step 5)

## Review Focus

1. **Falscher Empfänger:**
   - Gegner oder Splitscreen drehen sich mit der Maus mit, wenn die Schreibstelle mehrere Figuren bedient oder `LEVEL2P.BIN` dieselben Bytes an derselben Adresse hat.
   - Erwartet: Nur Spieler 1 im Einzelspieler-Level dreht sich.
   - Geprüft wird per Wächter auf Overlay-Wort 5 und `$s0 == Spieler-Zeiger` (Task 4, Splitscreen-Fall im Maus-Test).
2. **Aufgestaute Bewegung:**
   - Maus während Pause, Ladebild, Zwischensequenz oder ohne Zielmodus bewegt.
   - Erwartet: Beim Weiterspielen springt nichts.
   - Geregelt über `eligible()` und die Verfallsregel für Nick (Task 2 Unit-Tests, Task 4 Pause-Fall).
3. **Nick über die Grenze oder nach dem Loslassen:**
   - Erwartet: Nick bleibt in den Spielgrenzen und ist nach dem Loslassen von R2 wieder 0, wie mit dem Pad (Task 4).
4. **Langsame Maus und Extremwerte:**
   - Kleine Bewegungen dürfen sich nicht zu 0 abrunden.
   - Empfindlichkeit 1 und 200 sowie Invertierung wirken sofort, auch live geändert.
   - Kein Überlauf bei großen Sprüngen (Task 2).
5. **Paket an, Pad-Eingabe:**
   - Mit gemeldetem DualShock müssen Menü, Level und Splitscreen per Pad weiter funktionieren.
   - Erwartet wie in M3 (Task 6: `menu`, `mp`, `sweep -Mission 1` mit aktivem Paket).

---

### Task 1: Restliche Fakten belegen

Reine Erkundung im Dev-Build mit eigenem Skript im Scratchpad (Muster: `flows.boot_to_menu` → `flows.start_new_game` → `flows.wait_until_in_level`). Ergebnis sind Konstanten und Doku, kein Produktcode.

**Files:**
- Modify: `tests/smoke/moh.py` (Konstanten aus „Global Constraints“, Kommentar mit Fundweg)
- Create: `src/mouse/moh_addrs.h` (dieselben Werte als `#define MOH_…`)
- Modify: `docs/DEVELOPMENT.md` (neuer Abschnitt „Blickwinkel und Zielmodus“)

- [ ] **Step 1: Nick-Schreibstelle.**
  - R2 halten, `wtrace_range` auf Spieler + `0x17C` (4 Bytes), R2+hoch 0,3 s, `wtrace_dump`.
  - Die PC, deren Schreiben den Wert *verändert*, ist `PITCH_STORE_PC`. Dazu kommen `PITCH_STORE_WORD` (`disasm`) und das gespeicherte Register (`PITCH_STORE_REG`, Index in `gpr[]`).
  - Die Stelle, die beim Loslassen 0 schreibt, getrennt notieren. Sie wird nicht gehookt.
- [ ] **Step 2: Nick-Grenzen.**
  - R2+hoch 3 s halten, Wert lesen (= `PITCH_MIN`). R2+runter 3 s halten (= `PITCH_MAX`).
  - Liegt die Klemmung *vor* `PITCH_STORE_PC` im Code, notieren. Der Hook klemmt so oder so selbst auf diese Werte.
- [ ] **Step 3: Skalierung.**
  - Im Code den Leser von Spieler + `0x17C` finden: `disasm` rund um `PITCH_STORE_PC`, Muster `LW …, 380(…)`, dann `SRA`.
  - `PITCH_SHIFT` = Verschiebung, mit der Nick in 4096er-Winkeleinheiten umgerechnet wird. Ohne Verschiebung ist sie 0.
  - `YAW_UNITS_PER_TURN` prüfen: `write_ram` erhöht die Gier um `4096 << 16`. Der Screenshot muss dem Ausgangsbild gleichen (`pngcheck.mean_abs_diff` < 1). Mit `1024 << 16` muss er deutlich abweichen.
- [ ] **Step 4: Gier-Stelle prüfen.**
  - Steht in `LEVEL2P.BIN` an `YAW_STORE_PC` dasselbe Wort? Aus den Disc-Dateien lesen, Offset = `YAW_STORE_PC − 0x80039F28`. Ergebnis notieren.
  - Ein Durchlauf mit 10 s Wartezeit: `wtrace_dump pc_lo/pc_hi` auf `YAW_STORE_PC` darf nur `0x800EEDB0` liefern. Liefert er mehr Adressen, notieren. Der Wächter in Task 4 deckt beides ab.
- [ ] **Step 5: Tasten.**
  - L1/R1: Spielerposition (Struct-Felder, die sich bei L1 ändern, aber nicht bei Drehen) muss sich seitlich ändern, die Gier nicht. Dann gilt: L1/R1 = Seitschritt.
  - Quadrat, Kreis, Dreieck und Select je 1 s halten und loslassen, mit Screenshots vorher und nachher. Die Wirkung kommt in die Tabelle in `DEVELOPMENT.md`.
  - Start drücken (Pause): Schreibt die Gier-Stelle weiter (`wtrace`)? Darauf beruht `eligible()`.
    - Hört sie in der Pause auf: `paused` bleibt 0.
    - Läuft sie weiter: Pause-Zelle per `tools/ramdiff.py` suchen (Läufe vor, in und nach der Pause) und als `PAUSE_FLAG_ADDR` eintragen.
- [ ] **Step 6:** Konstanten eintragen. `py -3 -m unittest discover -s tests/smoke -p "test_*.py"` muss weiter alles grün melden.
- [ ] **Step 7: Commit:** `git add tests/smoke/moh.py src/mouse/moh_addrs.h docs/DEVELOPMENT.md`, Nachricht „M4: player view angles and aim mode facts“.

**Abbruch:**
- Gibt es keine einzelne Nick-Schreibstelle, etwa weil der Wert nur über `memcpy` entsteht: Stopp, dem Nutzer berichten.
- Bedient die Gier-Stelle Gegner *und* ist `$s0` kein verlässlicher Wächter: ebenso Stopp und Bericht.

### Task 2: Rechenlogik `mouselook` mit C-Unit-Test

**Files:**
- Create: `src/mouse/mouselook.h`, `src/mouse/mouselook.c` (keine Runtime-Header, nur `<stdint.h>`, `<math.h>`)
- Create: `tests/native/test_mouselook.c` (eigenes `main`, `assert`-frei: zählt Fehler, Rückgabe ≠ 0 bei Fehler)
- Modify: `CMakeLists.txt` (`enable_testing()`, `add_executable(moh_mouselook_test …)`, `add_test(NAME mouselook COMMAND moh_mouselook_test)`)

**Interfaces – Produces:**

```c
#define MOH_LOOK_SENS_MIN 1
#define MOH_LOOK_SENS_MAX 200
#define MOH_LOOK_FIXED_PER_COUNT 1024   /* 16.16 yaw per mouse count at sensitivity 1 */
#define MOH_LOOK_STALE_VBLANKS 4        /* hook older than this: not in gameplay */
typedef struct MohLook MohLook;         /* defined in the header, caller-allocated */
void    moh_look_init(MohLook *look, int sensitivity, int invert_y, int pitch_shift);
void    moh_look_set(MohLook *look, int sensitivity, int invert_y);   /* live option change */
void    moh_look_reset(MohLook *look);                                /* policy RESET */
void    moh_look_motion(MohLook *look, double dx, double dy);         /* policy MOTION */
int32_t moh_look_take_yaw(MohLook *look);   /* at the yaw store, once per game frame: 16.16 delta */
int32_t moh_look_apply_pitch(MohLook *look, int32_t pitch, int32_t lo, int32_t hi);
int     moh_look_eligible(uint32_t overlay_word, int paused, uint32_t vblank_now, uint32_t vblank_hook, int hook_seen);
```

Regeln, die die Tests festlegen:
- **Umrechnung:**
  - Gier = Zählimpulse × Empfindlichkeit × 1024.
  - Nick = derselbe Betrag × 2^`pitch_shift` / 2^16, gleich viel Winkel pro Impuls wie bei der Gier.
  - Rundung Richtung 0, der Rest wandert als `double` in den nächsten Aufruf.
- **Nick-Ablauf:**
  - `take_yaw` verschiebt das aufgelaufene dy in einen Nick-Vorrat und ersetzt dabei einen nicht abgeholten alten Vorrat.
  - `apply_pitch` holt den Vorrat ab, addiert in 64 Bit und klemmt auf `[lo, hi]`.
  - Ohne Zielmodus läuft die Nick-Stelle nicht. Der Vorrat verfällt dann beim nächsten `take_yaw`.
- **Invertierung:** Mit `invert_y` dreht sich das Vorzeichen von dy um. Ohne Invertierung bedeutet Maus nach oben (dy < 0) Nick negativ, also nach oben schauen wie R2+hoch.
- **Grenzen der Empfindlichkeit:** Werte außerhalb von 1…200 werden auf die Grenze gesetzt.
- **`eligible`:** 1 genau dann, wenn `overlay_word == 5`, `paused == 0`, `hook_seen` gilt und `(uint32_t)(vblank_now − vblank_hook) <= MOH_LOOK_STALE_VBLANKS`. Der Ausdruck ist auch beim Zählerüberlauf richtig. `paused` liefert das Plugin aus `PAUSE_FLAG_ADDR`, falls Task 1 eine Pause-Zelle braucht, sonst immer 0.

- [ ] **Step 1: Failing tests** in `tests/native/test_mouselook.c` (je eine Funktion, `CHECK(cond)` zählt Fehler):

```c
/* sens 40, no invert, pitch_shift 16 unless noted */
yaw_exact:            motion(100,0); take_yaw()==4096000; take_yaw()==0
fraction_carries:     sens 1; 10x { motion(0.0001,0); sum+=take_yaw(); } sum==1
negative_carries:     sens 1; 10x { motion(-0.0001,0); sum+=take_yaw(); } sum==-1
reset_drops:          motion(50,50); reset(); take_yaw()==0; apply_pitch(7,-1<<30,1<<30)==7
pitch_after_take:     motion(0,10); take_yaw()==0; apply_pitch(100,-1<<30,1<<30)==100+409600;
                      apply_pitch(5,-1<<30,1<<30)==5
pitch_stale_dropped:  motion(0,10); take_yaw(); take_yaw(); apply_pitch(0,-1<<30,1<<30)==0
invert:               init(40,1,16); motion(0,10); take_yaw(); apply_pitch(0,-1<<30,1<<30)==-409600
clamp:                motion(0,1e6); take_yaw(); apply_pitch(0,-500,700)==700;
                      motion(0,-1e6); take_yaw(); apply_pitch(0,-500,700)==-500;
                      motion(0,1e6); take_yaw(); apply_pitch(INT32_MAX-1,INT32_MIN,INT32_MAX)==INT32_MAX
sens_bounds:          init(0,0,16); motion(1,0); take_yaw()==1024;
                      init(500,0,16); motion(1,0); take_yaw()==200*1024
pitch_shift:          init(1,0,12); motion(0,16); take_yaw(); apply_pitch(0,-1<<30,1<<30)==1024
live_set:             motion(1,0); set(2,0); take_yaw()==2048
eligible:             (5,0,100,98,1)==1; (5,0,100,95,1)==0; (6,0,100,99,1)==0; (5,0,100,99,0)==0;
                      (5,1,100,99,1)==0; (5,0,2,0xFFFFFFFE,1)==1
```

- [ ] **Step 2:** Bauen und laufen lassen: `cmake --build build-dev --target moh_mouselook_test` → Linkfehler (Funktionen fehlen) = erwarteter Fehlschlag.
- [ ] **Step 3:** `mouselook.c` implementieren.
- [ ] **Step 4:** `ctest --test-dir build-dev -R mouselook --output-on-failure` → `100% tests passed`.
- [ ] **Step 5: Commit:** „M4: mouse look arithmetic with unit tests“.

### Task 3: Mod-Paket und Plugin-Gerüst

**Files:**
- Create: `mods/preloaded/packages/moh.input.mouse-keyboard/1.0.0/manifest.toml`
- Create: `src/mouse/moh_mouse_plugin.c`
- Create: `tests/smoke/modstate.py`, `tests/smoke/test_modstate.py`
- Modify: `CMakeLists.txt` (`target_sources(psx-runtime PRIVATE src/mouse/mouselook.c src/mouse/moh_mouse_plugin.c)`)

**Interfaces:**
- **Consumes:** `MohLook`-API (Task 2), `moh_addrs.h` (Task 1).
- **Produces:**
  - Plugin-ID `moh.mouse-look`, Debug-Befehl `mod_cmd name=moh_mouse args="move <dx> <dy>"`
  - Zähler `moh_mouse.activate`, `moh_mouse.yaw_hook`, `moh_mouse.pitch_hook`, `moh_mouse.dropped`
  - Python: `modstate.enabled(build_dir, values)`, ein Kontextmanager. Er schreibt `<build_dir>/mods/state.toml` mit aktivem Feature und stellt die Originaldatei danach Byte für Byte wieder her (fehlte sie vorher, wird sie gelöscht).

**Manifest** (Format 11, `resolver = "declarative"`, `save_compatibility = "shared"`, `[[target]] game_id = "SLES-02470"`):
- Feature `mouse-look`, Gruppe „Input“, `default_enabled = false`
- Option `sensitivity`: integer, 1…200, Schritt 1, Standard 40 (≈ 6 550 Impulse pro Umdrehung, bei 800 DPI etwa 21 cm)
- Option `invert_y`: boolean, Standard false
- `[[plugin]] feature = "mouse-look"`, `id = "moh.mouse-look"`

**Plugin** (`PSX_MOD_CONSTRUCTOR` registriert alles unter `moh.mouse-look`):
- **Aktivierung:**
  - Zähler `activate`; Optionen lesen (`psx_mod_option_value`) → `moh_look_init`
  - `psx_mod_set_controller_mode_override(0, 1)` (1 = `PAD_MODE_ANALOG`, 2 = digital; die Enum ist C++ und nur in `main.cpp`)
  - Maus-Policy registrieren (`hold_control = PSX_MOD_MOUSE_HOLD_NONE`), danach `psx_mod_set_local_mouse_persistent_capture(1)`
- **Policy-Rückrufe:**
  - `event`: RESET → `moh_look_reset`, MOTION → `moh_look_motion`
  - `sample`: `override_right = 0`
  - `eligible`: `moh_look_eligible(psx_mod_read_word(0x80039F28), paused, vblanks, last_hook_vblank, hook_seen)`
- **VBlank:** zählt `vblanks` hoch und leert die Debug-Inbox: bei `eligible` → `moh_look_motion`, sonst verwerfen und `moh_mouse.dropped` zählen.
- **Debug-Befehl:** `move` addiert in zwei `_Atomic long long` (Tausendstel-Impulse). Er läuft auf dem Debug-Thread und fasst sonst nichts an.
- **Optionen live:** `psx_mod_register_option_changed_plugin` → `moh_look_set`, Rückgabe 1.

- [ ] **Step 1: Failing test** `test_modstate.py`:
  - Feature-Eintrag mit `package_id`, `id`, `enabled = true` und `[feature.values] sensitivity = 40`
  - Wiederherstellung bei vorhandener und bei fehlender Datei
  - Ausnahme im `with`-Block stellt trotzdem wieder her
- [ ] **Step 2:** `modstate.py` schreiben, Unit-Tests grün.
- [ ] **Step 3:** Manifest und Plugin schreiben, Dev-Build neu bauen (Befehl aus `DEVELOPMENT.md`, „Code erzeugen und bauen“).
- [ ] **Step 4: Prüfung mit Skript im Scratchpad**, Dev-Build bootet ins Hauptmenü:
  - Mit `modstate.enabled(...)`: `mod_counters` zeigt `moh_mouse.activate = 1`, `pad_status.slot0.analog == true`.
  - Ohne: kein `moh_mouse.*`-Zähler, `analog == false`.
  - Liest die Runtime mit `--no-launcher` die `state.toml` nicht: Stopp, dem Nutzer berichten.
- [ ] **Step 5:** `run-smoke -Test menu` (ohne Paket) muss weiter OK melden.
- [ ] **Step 6: Commit:** „M4: mouse-keyboard package and plugin skeleton“.

### Task 4: Gier- und Nick-Hooks, Maus-Smoke-Test

**Files:**
- Modify: `game.toml` (`[recompiler] mod_instruction_sites = ["<YAW_STORE_PC>", "<PITCH_STORE_PC>"]`)
- Modify: `generated/` (neu erzeugt)
- Modify: `src/mouse/moh_mouse_plugin.c`
- Create: `tests/smoke/mouse_smoke.py`, `tests/smoke/test_mouse.py`
- Modify: `tools/run-smoke.ps1` (`-Test mouse`; nicht Teil von `all`, Dauer im Kommentar)

**Hooks** (`psx_mod_register_instruction_plugin(id, PC, WORD, cb)`), beide mit Wächter:
- Overlay-Wort an `0x80039F28` == 5
- `cpu->gpr[16]` (`$s0`) == `*( *(PLAYER_OWNER_PTR_ADDR) + PLAYER_PTR_OFFSET )`
- Sonst unverändert lassen und nichts zählen.

Hook-Verhalten:
- **Gier:** `cpu->gpr[2] += moh_look_take_yaw(...)`, `last_hook_vblank = vblanks`, `hook_seen = 1`, Zähler `yaw_hook`.
- **Nick:** `gpr[PITCH_STORE_REG] = moh_look_apply_pitch(..., gpr[PITCH_STORE_REG], PITCH_MIN, PITCH_MAX)`, Zähler `pitch_hook`.

**Hilfen in `mouse_smoke.py` (rein, Unit-Tests in `test_mouse.py`):**
- `yaw_fixed(port)` und `pitch(port)` lesen über die Zeigerkette, vorzeichenbehaftet.
- `expected_yaw(counts, sens) = counts * sens * 1024`
- `expected_pitch(counts, sens, shift) = int(counts * sens * 1024 * 2**shift / 2**16)`

**Ablauf `mouse_smoke.py`** (Paket an, `sensitivity = 40`, `invert_y = false`; M1L1 über NEW GAME):
1. **Ruhe:** Gier 1 s ohne Eingabe stabil.
2. **Gier:** `mod_cmd moh_mouse move 100 0`, 1 s warten. Die Gier ist um genau `expected_yaw(100, 40)` gewachsen.
3. **Nick im Zielmodus:**
   - R2 per `set_input` halten, 0,5 s warten, `move 0 -20`.
   - Nick == `max(PITCH_MIN, expected_pitch(-20, 40, PITCH_SHIFT))`.
   - Dann `move 0 100000`: Nick == `PITCH_MAX`.
4. **Loslassen:** `clear_input` → nach 0,5 s Nick == 0.
5. **Ohne Zielmodus:** `move 0 50`, 1 s warten, dann R2 halten. Nick bleibt 0, Gier unverändert.
6. **Pause:** Start drücken, `move 300 0` während der Pause, `moh_mouse.dropped` steigt. Nach dem Weiterspielen ist die Gier unverändert.
7. **Abdeckung:** `dirty_ram_stats` `per_pc` mit `lo/hi` um beide Hook-Stellen: keine Einträge. Die Hooks laufen nativ.
8. **Splitscreen:**
   - Neustart mit Paket an, dann der Weg aus `mp_smoke.check_mp` bis `flows.wait_until_in_level` (Pad 2 über `mp_smoke.plug_in_pad2`).
   - `move 500 0`, 1 s warten: `yaw_hook` bleibt 0, `moh_mouse.dropped` steigt.
9. **Paket aus:**
   - Neustart. Der Befehl bleibt registriert, denn die Debug-Befehle hängen nicht am Paket.
   - `move 300 0`: Die Gier bleibt, und es gibt keinen `moh_mouse.*`-Zähler.

- [ ] **Step 1: Failing tests** `test_mouse.py`:
  - `expected_yaw(100, 40) == 4096000`
  - `expected_pitch(-20, 40, 16) == -819200`
  - Vorzeichen-Lesen: `0xFFFF0000` → `-65536`
- [ ] **Step 2:** Hilfen schreiben, Unit-Tests grün.
- [ ] **Step 3:** `game.toml` ergänzen, `generate` (Befehl aus `DEVELOPMENT.md`). Im Diff von `generated/` stehen Hook-Aufrufe (`psx_mod_instruction`) nur an diesen beiden Adressen, je Image, das dort Code hat. Sonst ändern sich höchstens Hashes und Metadaten.
- [ ] **Step 4:** Hooks im Plugin, Dev- und Release-Build neu bauen.
- [ ] **Step 5:** `pwsh -File tools/run-smoke.ps1 -Build dev -Test mouse` → `mouse_smoke: OK …` mit allen neun Fällen in der Ausgabe.
- [ ] **Step 6:** `-Test coverage` und `-Test mp` ohne Paket weiter OK.
- [ ] **Step 7: Commit:** „M4: mouse yaw and aim-mode pitch hooks“. `generated/` gehört mit in den Commit, wie bei M3.

### Task 5: Tastenbelegung für Maus und Tastatur

**Files:**
- Modify: `config/keybinds.ini` (`[player1]`)
- Create: `cmake/copy_if_missing.cmake`
- Modify: `CMakeLists.txt` (POST_BUILD: `config/keybinds.ini` neben die `.exe` kopieren, nur wenn dort keine liegt)
- Modify: `docs/DEVELOPMENT.md` (Abschnitt Tastaturbelegung)

**Belegung** (QWERTZ, SDL-Namen = US-Positionen; Wünsche des Nutzers vom 2026-10-26 bleiben, wo sie nicht kollidieren):

| PS1 | Taste(n) | Wirkung im Spiel |
|---|---|---|
| up / down | W, Up / S, Down | laufen |
| left / right | Left / Right | drehen (Maus dreht auch) |
| l1 / r1 | A, U / D, I | Seitschritt (laut Task 1) |
| cross | E, Mouse1 | schießen |
| r2 | O, Mouse3 | Zielmodus halten |
| l2 | Y (= Z auf QWERTZ) | ducken |
| circle / square / triangle | R / Q / Escape | laut Task 1; Esc gibt bei eingefangener Maus erst die Maus frei |
| start / select | Return / Right Shift | Pause / laut Task 1 |
| ls_* / rs_* | None | Sticks nur vom Gamepad, sonst doppelte Eingabe |

Hat Dreieck im Level eine Wirkung (Task 1), bekommt es zusätzlich eine zweite Taste (Vorschlag `F`), weil Esc beim Spielen zuerst die Maus freigibt.

- [ ] **Step 1:** Ein Test in `test_helpers.py` liest `config/keybinds.ini` mit `configparser`:
  - `[player1]` hat für `cross` `Mouse1`, für `r2` `Mouse3`, für `l1` `A`, für `r1` `D`.
  - Alle `ls_*`/`rs_*` sind `None`.
  - Keine Taste ist in `[player1]` zwei verschiedenen PS1-Eingaben zugeordnet.
  - Der Test schlägt zuerst fehl.
- [ ] **Step 2:** `keybinds.ini` anpassen, Test grün.
- [ ] **Step 3:** `copy_if_missing.cmake` (`if(NOT EXISTS "${DST}") file(COPY_FILE "${SRC}" "${DST}")`) und POST_BUILD einbinden.
  - Prüfen: frischer Ordner `build-tmp` bekommt die Datei.
  - Vorhandene `build-release/keybinds.ini` bleibt unangetastet (Zeitstempel).
  - `build-tmp` danach löschen.
- [ ] **Step 4:** Die Nutzer-Datei `build-release/keybinds.ini` nach `keybinds.ini.bak-m3` sichern und durch die neue ersetzen. Im Abschlussbericht erwähnen.
- [ ] **Step 5:** `DEVELOPMENT.md`: Tabelle ersetzen, Hinweis auf die Launcher-Seite Controls und auf Esc.
- [ ] **Step 6: Commit:** „M4: keyboard and mouse button layout“.

### Task 6: Regression, Doku, Spec, Abnahme

**Files:**
- Modify: `docs/superpowers/specs/2026-10-25-moh-pc-port-design.md` (Abschnitt 6.2 und Risikotabelle nach „Abweichungen von der Spec“; M4-Zeile: „im Zielmodus“ ergänzen)
- Modify: `docs/DEVELOPMENT.md` (Abschnitt „Maus“: Paket einschalten, Optionen, Debug-Befehl, Zähler, `-Test mouse`)
- Modify: `docs/PLAYTEST.md` (Abschnitt „M4: Maus und Tastatur“)

- [ ] **Step 1: Mit aktivem Paket** (Skript setzt `modstate.enabled` um die Läufe):
  - `run-smoke -Test menu`, `-Test mp`, `-Test sweep -Mission 1`, jeweils OK
  - Danach ohne Paket `-Test intro`, `-Test coverage`, beide OK
- [ ] **Step 2:** Unit-Tests komplett (`unittest discover` und `ctest`), alle grün.
- [ ] **Step 3: Doku und Spec** schreiben. In `PLAYTEST.md` die Abnahmepunkte für den Nutzer:
  1. Paket im Launcher (Mods → Input) einschalten.
  2. Klick fängt die Maus ein, Esc gibt sie frei. Nach der Pause genügt ein Klick.
  3. Drehen fühlt sich direkt an. Empfindlichkeit im Launcher ändern, bis es passt (Wert notieren).
  4. Rechte Maustaste: Fadenkreuz, Maus neigt den Blick, Grenzen oben und unten passen.
  5. Y-Invertierung umschalten wirkt.
  6. WASD, Ducken, Schießen mit Linksklick.
  7. EASY AIM aus und an ausprobieren, Vorliebe notieren.
  8. Gamepad: ein paar Minuten nur mit Pad, alles wie vorher.
  9. Wie oft fängt sich die Maus nach Zwischensequenzen nicht von selbst ein? Stört das?
- [ ] **Step 4: Abschluss-Review:** frischer Reviewer über die M4-Commits gegen diesen Plan und die Spec. Funde nach `receiving-code-review` bearbeiten.
- [ ] **Step 5: Commit:** „M4: docs, spec update and playtest checklist“.
- [ ] **Step 6:** Den Nutzer um die Abnahme nach `PLAYTEST.md` bitten. Der Bildraten-Test (`-Test all` mit aktivem Paket) läuft erst, wenn er den PC freigibt.
