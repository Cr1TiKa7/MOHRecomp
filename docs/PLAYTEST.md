# Durchspiel-Checkliste (M3)

Die automatischen Tests springen in jedes Level und laufen dort eine halbe Minute herum. Ob sich ein Level bis zum Ende spielen lässt, zeigt nur ein echter Durchlauf. Gespielt wird im Release-Build (`build-release\MOH_Recompiled.exe`), in beliebig vielen Sitzungen.

## So trägst du ein

- **Gespielt:** Datum, an dem du das Level gespielt hast
- **Abschluss:** `ja`, wenn das nächste Level oder die Missionsauswertung kam, sonst `nein`
- **Auffälligkeiten:** alles, was anders wirkt als auf der PlayStation, zum Beispiel:
  - Ton: fehlt, knackt, falsche Musik
  - Gegner: stehen still, schießen nicht, laufen durch Wände
  - Ruckler: wo genau und wie lange
  - Absturz: Fenster weg oder Bild eingefroren

Du kannst die Tabelle selbst ausfüllen oder mir die Punkte diktieren.

## Levels

Die Nummern sind die Ordner auf der Disc (`DATA\MSN<m>\LVL<l>`). Im Spiel heißen die Missionen 1 bis 7. Die Ordner MSN7 und MSN9 sind vermutlich die Spielmissionen 6 und 7 (bitte korrigieren, falls nicht).

| Level | Gespielt | Abschluss | Auffälligkeiten |
|---|---|---|---|
| MSN1 LVL1 | 2026-10-26 | ja | zuerst im M2-Build, dann erneut im M3-Release-Build: keine, Ton in Ordnung; ohne Maus schwer zu navigieren (M4) |
| MSN1 LVL2 | 2026-10-26 | ja | keine, Ton in Ordnung; ohne Maus schwer zu navigieren (M4) |
| MSN1 LVL3 | 2026-10-26 | ja | keine, Ton in Ordnung; ohne Maus schwer zu navigieren (M4) |
| MSN2 LVL1 | | | |
| MSN2 LVL2 | | | |
| MSN2 LVL3 | | | |
| MSN2 LVL4 | | | |
| MSN3 LVL1 | | | |
| MSN3 LVL2 | | | |
| MSN3 LVL3 | | | |
| MSN3 LVL4 | | | |
| MSN4 LVL1 | | | |
| MSN4 LVL2 | | | |
| MSN4 LVL3 | | | |
| MSN5 LVL1 | | | |
| MSN5 LVL2 | | | |
| MSN5 LVL3 | | | |
| MSN5 LVL4 | | | |
| MSN7 LVL1 | | | |
| MSN7 LVL2 | | | |
| MSN7 LVL3 | | | |
| MSN9 LVL1 | | | |
| MSN9 LVL2 | | | |
| MSN9 LVL4 | | | |

Die MSN12-Ordner sind sehr wahrscheinlich die Mehrspieler-Karten und gehören nicht zur Kampagne.

## Splitscreen (einmal, optional)

Der automatische Test steckt den zweiten Controller nur über den Debug-Port ein. Mit echten Geräten:

1. Im Launcher unter Controls Spieler 1 = Tastatur, Spieler 2 = Gamepad wählen.
2. MULTIPLAYER → START GAME.
3. Beide Hälften steuern sich getrennt (Spieler 1 oben), ein paar Minuten ohne Absturz.

Ergebnis: ______

## Wenn etwas schiefgeht

1. Mission und Level notieren und kurz beschreiben, was passiert ist und was du davor gemacht hast.
2. Das Spiel speichert nur zwischen den Levels. Kopiere deshalb den letzten Spielstand vor dem betroffenen Level (`saves\card1.mcd`) nach `D:\RecompDev\fixtures\`. Den Namen so wählen, dass das Level drinsteht, z. B. `moh-vor-msn3-lvl2.mcd`. Dazu die Stelle im Level beschreiben, an der es passiert.
3. Die Karte bleibt lokal und kommt nie ins Repo.

Jedes gefundene Problem wird eine eigene Aufgabe. Es wird erst die Ursache gesucht und dann repariert.
