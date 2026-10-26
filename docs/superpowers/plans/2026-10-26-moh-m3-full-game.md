# M3 Ganzes Spiel – Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Jedes Einzelspieler-Level lädt nachweislich, läuft ohne Absturz und weitgehend nativ. Die Overlays sind vollständig aus Disc-Daten vorab kompiliert. Der Splitscreen startet. Der Nutzer spielt die Kampagne einmal ganz durch.

**Architecture:**
- **Level-Sprung:** Ein Level-Durchlauf (`sweep_smoke`) springt per RAM-Schreibzugriff in die dauerhafte Spielstand-Struktur direkt in jedes Level. Pro Level prüft er CD-Zugriffe, Bild, Stabilität und Interpreter-Anteil.
- **Splitscreen:** `LEVEL2P.BIN` kommt als drittes Image ins Rezept. Ein Splitscreen-Test braucht einen zweiten Controller, das Einstecken über die Debug-Schnittstelle muss erst gelöst werden. Rückfall: Der Nutzer prüft manuell.
- **Langzeit-Abdeckung:** Messungen über je 10 Minuten in Menü, Level und Videos, wie in der Spec gefordert.

**Tech Stack:** wie M2. Neu: `write_ram` (ein Byte pro Aufruf), `pad_status`, `wtrace_add`/`wtrace_dump` (Erkundung).

**Spec:** `docs/superpowers/specs/2026-10-25-moh-pc-port-design.md`, Meilenstein M3, Abschnitte 6.1 und 7.

## Vorab offen (aus M2)

Die Live-Prüfung der M2-Review-Korrekturen (Commit `23f0460`) steht noch aus: `run-smoke -Test all` und `-Test save` auf einem freien PC. Sie kommt als Task 0 vor allem anderen, sobald der Nutzer den PC freigibt.

## Fakten aus der Erkundung (2026-10-26, Dev-Build)

- **Einzelspieler-Levels auf der Disc** (`/DATA/MSNm/LVLl/`, LBA-Bereiche aus dem ISO-Verzeichnis):

| Mission | Levels | LBA-Bereich |
|---|---|---|
| MSN1 | 1, 2, 3 | 1713–15208 |
| MSN2 | 1, 2, 3, 4 | 24692–41864 |
| MSN3 | 1, 2, 3, 4 | 41866–60950 |
| MSN4 | 1, 2, 3 | 60952–74810 |
| MSN5 | 1, 2, 3, 4 | 74812–92105 |
| MSN7 | 1, 2, 3 | 92107–108050 |
| MSN9 | 1, 2, 4 | 108052–118326 |
| MSN12 | 1–7 (nur 3 Dateien je Level, vermutlich Bonus/Geheim) | 15210–24690 |

- **Splitscreen-Daten** liegen unter `/DATA/TWOPLAYR/`.
- **Pfadaufbau:** `LEVEL.BIN` baut den Pfad mit `data\msn%ld\lvl%ld\…` (`0x8003D574`, `0x8003D5A8`).
  - Die Ladefunktion `0x800878D8` bekommt Mission und Level von ihrem einzigen Aufrufer (`0x80062640`) aus `0x80093FD4`/`0x80093FD8`.
  - Diese Zellen überschreibt der CD-Transfer von `LEVEL.BIN` mit 0.
  - Code bei `0x8004A874`/`0x8004A884` setzt sie danach neu, aus der **dauerhaften Spielstand-Struktur `0x80038764`** (Boot-EXE-Speicher): Missionsindex bei +148 = `0x800387F8`, Levelindex bei +152 = `0x800387FC`. Beide sind 0-basiert, Ordnernummer = Index + 1.
- **Level-Sprung belegt:**
  1. NEW GAME, 3 s warten
  2. `write_ram 0x800387F8 = 1`, `0x800387FC = 0`
  3. X durch das Briefing
  4. Ergebnis: Das Level lädt ausschließlich `MSN2/LVL1`-Daten (LBA 24976), keine von `MSN1/LVL1`. Im Level stehen Mission/Level auf 2/1, das Bild zeigt ein Treppenhaus.
  5. Das Briefing ist weiter das von Mission 1, das ist nur kosmetisch.
- **Multiplayer:**
  - Hauptmenü → MULTIPLAYER → Raum mit „START GAME“ und der Meldung „NOT ALL CONTROLLERS PLUGGED IN…“.
  - Weder `set_input port=2` noch `press port=2 connected=1` lassen `pad_status.slot1.connected` auf `true` springen. `game.toml`/`settings.toml` haben `multitap = true`.
- **`LEVEL2P.BIN`:** Ladeadresse noch nicht im RAM belegt. Es gibt einen einzigen Lader-Code, der `0x80039F28` baut (`0x8003728C`). Deshalb ist dieselbe Basis zu erwarten. Die Byte-Guards verhindern eine falsche Auswahl, falls nicht.
- **`psxdbg.send`:** Der Parameter `port` meint dort den TCP-Port. Debug-Befehle mit eigenem Feld `port` (Controller-Anschluss) sind damit nicht erreichbar.
- **Messbedingungen:** Bildraten-Prüfungen sind nur auf einem freien PC aussagekräftig. Mit Rainbow Six im Hintergrund fiel das Level auf 35 fps bei 28 ms Emulationszeit pro Frame.

## Global Constraints

- **Alles aus M0–M2 gilt weiter:**
  - D: für alles
  - keine Spieldaten, Savestates, Speicherkarten oder Screenshots im Repo
  - `. D:\RecompDev\dev-env.ps1`
  - Commits mit `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`
  - kein Push
  - nur Python-Standardbibliothek
  - `SDL_AUDIODRIVER=dummy`
- **Tests mit Bildraten-Prüfung** (`level`, `all`) laufen nur, wenn der Nutzer den PC freigibt. Funktionale Tests (Sweep, Splitscreen, Abdeckung) dürfen nebenher laufen, melden aber keine fps-Fehler.
- **Level-Sprung nur über die Spielstand-Struktur** (`0x800387F8`/`0x800387FC`). Kein Patchen von Spielcode, keine geänderten Speicherkarten.
- **Sweep-Dauer:** etwa 3 Minuten pro Level. Der Sweep läuft nicht in `all`, sondern als eigener Test `-Test sweep`, optional auf eine Mission eingeschränkt.

## Review Focus

1. **Sprung, der nicht springt:** Nur „Level läuft“ zu prüfen reicht nicht. Pro Level müssen CD-Zugriffe im LBA-Bereich *dieses* Levels liegen und keine im Bereich von M1L1 (Task 2).
2. **Helle Levels und das Warten:** Die Schwelle 10 für „Ladeplakat weg“ ist nur an M1L1/M1L2 belegt. Bricht `wait_until_in_level` in einem Level ab, wird die Schwelle nicht blind gesenkt. Erst Plakat und Level des Falls messen, dann entscheiden (Task 2).
3. **Ein abgestürztes Level stoppt den Sweep:** Ein Fehler in einem Level darf die übrigen nicht verhindern. Der Sweep startet pro Level neu und berichtet am Ende alle Ergebnisse (Task 2).
4. **Splitscreen „startet“ nur scheinbar:** Ein Erfolg verlangt das Overlay-Wort 6 an `0x80039F28` und einen weiterlaufenden Bildzähler, nicht nur einen Menüwechsel (Task 3).
5. **Abdeckung durch kurze Fenster geschönt:** Die 10-Minuten-Messungen müssen Differenzen über genau ihr Fenster sein, nicht Werte seit Boot (Task 4).

---

### Task 0: Live-Prüfung aus M2 nachholen

- [ ] **Step 1:** Nutzer fragen, ob der PC frei ist. Erst bei Ja weiter.
- [ ] **Step 2:** `pwsh -File tools/run-smoke.ps1 -Build dev -Test all`, danach `-Test save`.
  Expected: beide Exit 0. `level_smoke` mit `shots=≥3` und `soak_diffs` alle ≥ 1, `save_smoke` mit `lvl2_reads` nicht leer.
- [ ] **Step 3:** Bei Fehlschlag mit superpowers:systematic-debugging klären, besonders ob `M1L1_MAGAZINE_ADDR` über Läufe stabil ist und ob NEXT MISSION vorgewählt ist. Dann das Ledger der M2-Ausführung abschließen und `.superpowers/sdd/2026-10-25-moh-m2-level` löschen.

### Task 1: `psxdbg` für Felder namens `port`, Level-Sprung in `flows`

**Files:**
- Modify: `tests/smoke/psxdbg.py`, `tests/smoke/test_helpers.py`
- Modify: `tests/smoke/flows.py`, `tests/smoke/moh.py`, `tests/smoke/test_flows.py`, `tests/smoke/test_moh.py`

**Interfaces:**
- Produces:
  - `psxdbg.send(cmd, port=4370, timeout=5.0, payload=None, **params) -> dict`
    - `payload` (dict) wird ins JSON gemischt und darf `port` enthalten. Bei gleichen Schlüsseln gewinnt `payload`.
  - `moh.LEVELS`: Tupel der 24 Einzelspieler-Levels als `(mission, level, (lba_lo, lba_hi))`, in Kampagnen-Reihenfolge. Die Bereiche stammen aus dem ISO-Verzeichnis, Ende **inklusiv** wie bei `M1_LVL1_LBAS` und dem Filter `lba_hi` von `cd_read_log`, ohne den Verzeichnissektor.
  - `moh.BONUS_LEVELS`: dasselbe für MSN12/LVL1–7
  - `moh.STATE_MISSION_ADDR = 0x800387F8`, `moh.STATE_LEVEL_ADDR = 0x800387FC`
  - `flows.start_level(port, base, mission, level, deadline) -> int`
    - NEW GAME, 3 s warten
    - `write_ram` Index = Nummer − 1 auf beide Zellen
    - beide Zellen zurücklesen (Abweichung → `SmokeFailure`)
    - CD-Marke setzen
    - `advance_until_level`
    - gibt die CD-Marke zurück
- Steps:
  - [ ] **Failing Tests:**
    - `test_payload_may_carry_port`: FakeServer sieht `"port": 2` im JSON und TCP-Port bleibt der des FakeServers
    - `test_levels_table_has_24_entries_without_overlap`: Bereiche aufsteigend und disjunkt, MSN1/LVL1 = `(1713, 6290)` = `moh.M1_LVL1_LBAS`
    - `test_start_level_writes_zero_based_indexes`: FakeServer protokolliert `write_ram` an `0x800387F8` mit `val` 1 und `0x800387FC` mit `val` 0 für `(2, 1)`. Rücklesen liefert diese Werte.
  - [ ] **Ausführen:** muss mit `AttributeError`/`TypeError` fehlschlagen.
  - [ ] **Implementieren:** Tests grün, gesamte Suite grün.
  - [ ] **Commit:** `git commit -m "Add level jump via the persistent game state and payload support in psxdbg"`

### Task 2: Level-Durchlauf `sweep_smoke`

**Files:**
- Create: `tests/smoke/sweep_smoke.py`
- Modify: `tools/run-smoke.ps1`: `-Test sweep`, optional `-Mission <n>`. Nicht Teil von `all`.

**Interfaces:**
- Produces: `sweep_smoke.py --exe --cue [--port] [--out] [--mission N] [--bonus] [--per-level-timeout 300]`
  - Exit 0, wenn alle gewählten Levels bestehen. Sonst Exit 1 mit einer Zeile pro fehlgeschlagenem Level und einer Abschlusszeile `sweep: N/M levels OK`.
- **Pro Level** (eigene Instanz, Autocompile aus, DLL-Cache gelöscht wie bei `coverage_smoke`):
  1. `boot_to_menu`, `start_level`, `wait_until_in_level`
  2. Zähler `c0`
  3. 30 s Eingabeschleife wie im Dauerlauf, ohne Munitionsprüfung, denn Waffe und Magazinadresse unterscheiden sich je Level
  4. Prozess lebt, Bildzähler steigt, aufeinanderfolgende Screenshots unterscheiden sich (`looks_frozen`)
  5. `cd_reads_in(mark, Level-Bereich)` nicht leer, `cd_reads_in(mark, M1L1)` leer (außer beim Level M1L1 selbst)
  6. `window_share(c0, c1)` < 0,01
  7. Screenshot `<mission>_<level>.png` in `<out>`
  8. Ergebniszeile `M<m>L<l>: OK|FAIL <grund> interp=… lbas=…`
- Steps:
  - [ ] **Failing Test:** `test_sweep_reports_each_level`. `sweep_smoke.run_all` mit gepatchtem `check_one` (ein Level wirft `SmokeFailure`) liefert alle Zeilen und Exit 1 (Review Focus 3).
  - [ ] **Ausführen:** Test schlägt fehl. Implementieren, Test grün.
  - [ ] **Erst Mission 1 live:** `-Test sweep -Mission 1`. Expected: 3/3 OK. Die Screenshots ansehen, es müssen drei verschiedene Levels sein.
  - [ ] **Dann alle 24 Levels** (läuft lange, im Hintergrund). Fehlschläge einzeln mit superpowers:systematic-debugging untersuchen. Das Ergebnis jedes Levels kommt ins Ledger. Für `wait_until_in_level` gilt Review Focus 2.
  - [ ] **MSN12 einmal mit `--bonus`:** Das Ergebnis (lädt / lädt nicht / stürzt ab) wird nur dokumentiert. Bonus-Levels sind kein M3-Kriterium.
  - [ ] **Commit:** `git commit -m "Add level sweep: jump into every single-player level and check it"`

### Task 3: `LEVEL2P.BIN` und Splitscreen

**Files:**
- Modify: `aot/overlays.json`: drittes Image `LEVEL2P.BIN` an `0x80039F28`, `allow_missing`, `expected_records: 3`
- Create: `tests/smoke/mp_smoke.py`, falls Step 3 gelingt

**Steps:**
- [ ] **Step 1: Rezept.** `extract` → `Verified 3 images / 3 recipes`. Dann `generate` und beide Builds bauen. Die Audit-Datei nennt drei Images. Regression: `coverage` und `sweep -Mission 1`.
- [ ] **Step 2: Zweiten Controller einstecken** (Erkundung, Wegwerfskript):
  1. `debug_server.c` lesen: Wie wirkt `s_pad_connected_override` auf `pad_status`/SIO? Braucht es `multitap = false`?
  2. Danach in dieser Reihenfolge probieren:
     a. `press`/`set_input` mit `payload={"port": 2, "connected": 1}` (Task 1) und `pad_type`
     b. `--game`-Kopie bzw. `settings.toml` mit `[controller] multitap = false` im Testausgabeordner
     c. `p2_device = "keyboard"` in einer Test-`settings.toml`

  Erfolg heißt: `pad_status.slot1.connected == true` und die Meldung „NOT ALL CONTROLLERS PLUGGED IN“ ist weg (Bildvergleich gegen den Screenshot aus der Erkundung im selben Lauf).
- [ ] **Step 3, wenn Step 2 gelingt: `mp_smoke`.**
  1. MULTIPLAYER → START GAME → X durch die Auswahl, bis das Overlay-Wort `6` ist.
  2. `LEVEL2P.BIN` im RAM an `0x80039F28` belegen (wie bei `SHELL`).
  3. 60 s Eingabeschleife für beide Spieler.
  4. Prozess lebt, Bildzähler steigt, Bild friert nicht ein.
  5. CD-Zugriffe unter `/DATA/TWOPLAYR/`.
- [ ] **Step 4, wenn Step 2 scheitert:**
  - Ruling ins Ledger, mit den Ergebnissen aller drei Versuche.
  - Den Splitscreen-Nachweis übernimmt der Nutzer in Task 5: Tastatur als Spieler 1, Gamepad als Spieler 2, über die Controls-Seite des Launchers.
  - `LEVEL2P.BIN` bleibt trotzdem im Rezept, die Byte-Guards sichern es ab.
- [ ] **Commit(s):**
  - `git commit -m "Precompile LEVEL2P.BIN"`
  - ggf. `git commit -m "Add split-screen smoke test"`

### Task 4: Abdeckung über je 10 Minuten (Spec-Kriterium M3)

**Files:**
- Create: `tests/smoke/coverage_long.py`
- Modify: `tools/run-smoke.ps1`: `-Test coverage-long`

**Interfaces:**
- Produces: `coverage_long.py --exe --cue [--minutes 10]`
- Drei Fenster, je mit eigenen Zählern `c0`/`c1` (Review Focus 5):
  1. **Menü:** Ring im Kreis, OPTIONS, WAR RECORDS, GALLERY öffnen und schließen
  2. **Videos:** Boot ohne Turbo bis ins Menü, danach BRIEFING mehrfach abspielen, bis 10 Minuten voll sind
  3. **Level:** Sprünge in M1L1, M3L1, M7L1 mit Eingabeschleife, zusammen 10 Minuten
- Kriterium: Anteil < 0,01 je Fenster. Ausgabe von `insns` je Fenster.
- Steps:
  - [ ] Unit-Test für die Fenster-Aufteilung, z. B. `test_windows_accumulate_per_phase` mit Fake-Zählern
  - [ ] Implementieren, Live-Lauf (~35 min, Hintergrund)
  - [ ] Bleibt ein Fenster ≥ 1 %: die meistgenutzten interpretierten PCs aus `dirty_ram_stats per_pc` bestimmen und klären, zu welchem Overlay oder welcher Datei sie gehören, bevor etwas geändert wird
  - [ ] **Commit**

### Task 5: Durchspielen durch den Nutzer, Doku, Spec

- [ ] **Step 1: `docs/PLAYTEST.md` anlegen.** Tabelle aller 24 Levels mit den Spalten Gespielt / Abschluss / Auffälligkeiten (Ton, Gegner, Ruckler, Abstürze), dazu wie man Probleme meldet (Mission/Level, Speicherstand nach `D:\RecompDev\fixtures\`).
- [ ] **Step 2: Nutzer-Schritt.**
  - Der Nutzer spielt die Kampagne im Release-Build, in beliebig vielen Sitzungen, und füllt die Tabelle aus oder diktiert sie.
  - Splitscreen manuell, falls Task 3 Step 4 gilt.
  - Gefundene Probleme werden eigene Aufgaben (systematic-debugging), kein Blind-Fix.
- [ ] **Step 3: Doku und Spec.**
  - `DEVELOPMENT.md`: Sweep, Splitscreen, Langzeit-Abdeckung, Level-Sprung-Adressen
  - Spec 6.1: drei Images
  - Spec 8: Risikozeile zu `LEVEL2P` schließen oder aktualisieren
- [ ] **Step 4:** Gesamtlauf `all` + `save` (freier PC), `sweep` und `coverage-long`. Alle grün.
- [ ] **Commit:** `git commit -m "M3: playtest checklist, docs and spec update"`

---

**M3 ist fertig, wenn:**
- alle 24 Einzelspieler-Levels im Sweep bestehen,
- `coverage-long` in allen drei Fenstern < 1 % meldet,
- `LEVEL2P.BIN` im Rezept ist und der Splitscreen startet (automatisch oder vom Nutzer bestätigt),
- der Nutzer die Kampagne einmal durchgespielt hat und keine offenen Abstürze in `PLAYTEST.md` stehen.
