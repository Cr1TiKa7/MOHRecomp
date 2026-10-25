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
| `RETCOMM_TOOLCHAIN_CACHE` / `RETCOMM_DATA_HOME` / `CCACHE_DIR` | Caches auf D: statt `%LOCALAPPDATA%` |
| `PATH` | Toolchain-`bin` und Git-Bash vorangestellt |
| `MOH_CUE` | Pfad zur Disc (PAL, SLES-02470) |

Im Repo ist `core.autocrlf=false` gesetzt. Sonst bricht Windows PowerShell 5.1 in Framework-Skripten an Gits LF/CRLF-Warnungen ab.

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

# Boot-Smoke-Test: startet build-dev versteckt, prüft Bildzähler und Bildinhalt, beendet das Spiel
pwsh -File tools/run-smoke.ps1 -Build dev
```

- Der Smoke-Test legt Log, Screenshots und Speicherkarten unter `D:\RecompDev\Temp\smoke-<Zeitstempel>\` ab.
- Ist Port 4370 schon belegt, bricht er ab. Dann läuft noch eine andere Instanz.

## Debug-Port

Nur im Dev-Build. Pro TCP-Verbindung geht genau eine JSON-Zeile hin und eine zurück, z. B. `{"id":1,"cmd":"ping"}`. Python-Client: `tests/smoke/psxdbg.py` (`send(cmd, port=4370, **params)`).

## Was nie ins Repo gehört

Disc-Images, BIOS-Dumps, Logs, `overlay_captures.json` (enthält Spielcode), Savestates und Speicherkarten. Die `.gitignore` deckt das ab. Vor jedem Commit trotzdem `git status` prüfen.
