# Durchspiel-Checkliste (M3)

Die automatischen Tests springen in jedes Level und laufen dort eine halbe Minute herum. Ob sich ein Level bis zum Ende spielen lässt, zeigt nur ein echter Durchlauf. Gespielt wird im Release-Build (`build-release\Medal_of_Honor_Recompiled.exe`), in beliebig vielen Sitzungen.

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

## M4: Maus und Tastatur (Abnahme)

Im Release-Build (`build-release\Medal_of_Honor_Recompiled.exe`). Die neue Tastenbelegung liegt schon neben der `.exe`, die alte als `keybinds.ini.bak-m3`. Hinter jeden Punkt `ok` oder was dir auffällt.

1. **Einschalten:** Launcher → Mods → Input → „Mouse Look“ an. ______
2. **Einfangen:** Ein Klick ins Spiel fängt die Maus ein, dieser Klick schießt nicht. Esc gibt sie frei. Nach Pause oder Zwischensequenz genügt ein Klick. Wie oft musst du neu klicken, stört das? ______
3. **Drehen:** Fühlt es sich direkt an? Empfindlichkeit im Launcher (Mods → Mouse Look) anpassen, bis es passt. Welcher Wert? ______
4. **Zielen:** Rechte Maustaste halten zeigt das Fadenkreuz. Die Maus bewegt es, an seinem Rand dreht bzw. kippt die Ansicht. Passen die Grenzen oben und unten? ______
5. **Nach dem Zielen** bleibt die Neigung der Kamera stehen. So verhält sich das Original mit einem Analog-Pad, mit einem Digital-Pad kippt sie zurück. Stört dich das? ______
6. **Y-Invertierung** im Launcher umschalten: wirkt? ______
7. **Tasten:** W/S laufen, A/D Seitschritt, Pfeile drehen, Z ducken, Linksklick und E schießen, R Waffe wechseln, F Blick nach oben, Return Pause. Passt etwas nicht? ______
8. **Menüs mit der Tastatur:** Ein Tastendruck = genau ein Schritt im Menü? ______
9. **EASY AIM** (Options → Controller) einmal an und einmal aus. Was ist dir lieber? ______
10. **Gamepad:** ein paar Minuten nur mit dem Pad, bei eingeschaltetem Paket. Das Pad verhält sich dann wie ein DualShock am Original: Die Sticks wirken zusätzlich, im Zielmodus zielt nur noch der linke Stick (nicht das Steuerkreuz), und die Neigung bleibt nach dem Zielen stehen. Ist das für dich in Ordnung? ______
11. **Maus verloren?** Gibt das Spiel die Maus mitten im Spiel frei, ohne Pause, Menü oder Zwischensequenz, sodass der nächste Klick nicht schießt? Wenn ja: wo und wie oft? ______
12. **Freies Hoch/Runter** (neu, Launcher → Mods → Mouse Look → „Free vertical look“, Standard an): Ohne rechte Maustaste neigt die Maus jetzt die Ansicht, und Schüsse gehen in die Bildmitte. Fühlt sich das richtig an? Ist die Geschwindigkeit hoch/runter passend zur Drehung? Triffst du Gegner auf Treppen oder Türmen? ______

## M5: Breitbild und Bildqualität (Abnahme)

Im Release-Build (`build-release\Medal_of_Honor_Recompiled.exe`). Breitbild, Auflösung und PGXP schaltest du selbst im Launcher ein. Hinter jeden Punkt `ok` oder was dir auffällt.

1. **Einschalten:** Launcher → Mods → Visual → „Widescreen 16:9“ an. ______
2. **Nur im Spiel breit:** Im Level füllt das Bild 16:9. Menüs, Briefing, Ladebild, Pause, Missionsauswertung und Videos bleiben 4:3 mit schwarzen Seitenbalken, nichts ist gestreckt oder halb schwarz. Wo stimmt das nicht? ______
3. **Ränder beim Drehen:** Schnell drehen, auch in Innenräumen und mit Gegnern am Bildrand, in mehreren Levels. Verschwinden am linken oder rechten Rand Wände, Boden oder Gegner, oder bleibt dort Schwarz stehen? Wo? ______
4. **HUD:** Der Kompass sitzt links oben am Rand, die Munition rechts oben. Fadenkreuz (rechte Maustaste bzw. R2), Meldungen und Untertitel bleiben in der Mitte. Passt das? ______
5. **4K:** Launcher → Mods → „Internal Resolution“ auf 4K stellen und ein Level spielen. Läuft es flüssig, ohne Ruckler? ______
6. **PGXP an und aus:** Launcher → Mods → „PGXP Precision“ einmal an, einmal aus (Voreinstellung). Wackeln Wände und Boden mit PGXP weniger? Siehst du mit PGXP Risse, Lücken oder flackernde Flächen? Zittert der Kompass oben links? Willst du PGXP standardmäßig an haben? ______
7. **Splitscreen mit Breitbild-Paket:** Multiplayer starten. Er läuft in 4:3, das ist so gewollt. Startet er und lässt er sich spielen? ______
8. **Zusammen mit der Maus:** Maus-Paket und Breitbild-Paket gleichzeitig an. Funktioniert alles wie gewohnt (Einfangen, Drehen, Zielen)? ______
9. **Zielfernrohr mit Breitbild:** Sobald du ein Gewehr mit Zielfernrohr hast, einmal hindurchsehen. Ist die Fläche neben dem runden Ausschnitt auch in den breiten Seitenstreifen abgedeckt, oder sieht man dort die Welt ohne Maske? ______
