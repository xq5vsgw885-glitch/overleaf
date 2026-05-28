# AGENTS.md — Jam-gestützter Entwicklungsworkflow

Dieses Dokument beschreibt den validierten Agentenprozess für dieses Repository.
Alle Claude-Code-Sessions verwenden diesen Ablauf.

---

## Rollen

| Rolle | Aufgabe |
|-------|---------|
| **Jam** | Empirische Beobachtungsquelle: UI-Verhalten, Netzwerk-Traffic, Console Logs, User Events, Reproduktionsschritte |
| **Claude Code** | Lokaler Implementierungsagent: Repository-Analyse, Diagnose, Patch, Tests, Git |
| **ChatGPT** | Externe Instanz: Architektur-, Methodik- und Qualitätskontrolle |

---

## Ablauf

Bei jedem GitHub Issue, Nutzerbericht oder Jam-Link gilt diese Reihenfolge verbindlich:

1. GitHub Issue oder Nutzerbericht lesen
2. Jam-Link auswerten — Metadaten, User Events, Console Logs, Network Requests, Video
3. Beobachtung strikt von Interpretation trennen — sichtbares Verhalten / Logs / Vermutungen getrennt halten
4. Reproduktionsschritte rekonstruieren — chronologisch, erwarteter vs. beobachteter Zustand, fehlende Infos explizit markieren
5. Repository-Befund rein lesend erheben — betroffene Dateien lesen, kleinste plausible Ursache suchen
6. Patchplan formulieren — Änderung, Begründung, betroffene Dateien, Risiken
7. Freigabe abwarten
8. Minimalen Patch durchführen — nur die notwendigen Stellen, kein stilles Refactoring
9. Projektspezifische Tests ausführen (siehe unten)
10. Commit nur nach expliziter Freigabe
11. Push nur nach separater, expliziter Freigabe
12. Produktiv- oder UI-Verifikation durchführen
13. Issue schließen erst nach erfolgreicher Verifikation

---

## Sicherheitsregeln

- Kein Commit ohne explizite Freigabe
- Kein Push ohne separate Freigabe
- Keine stillen Refactorings
- Keine Dependency-Änderungen ohne Freigabe
- Keine erfundenen Logs, Testergebnisse oder Dateiinhalte
- Fehlende Jam-Daten immer als Unsicherheit markieren, nie raten
- Kein Patch, wenn kein Repository-Bezug besteht
- Keine Architekturänderungen ohne vorherige Begründung und Freigabe
- Keine Änderungen an wissenschaftlichen Inhalten ohne ausdrückliche fachliche Begründung

---

## Projektspezifische Verifikation

Repository-Pfad: `/Users/franzschmidt/overleaf`

| Situation | Befehl |
|-----------|--------|
| Immer | `python3 -m pytest tests/ -v` |
| `server.js` geändert | `node --check server.js` |
| `server.js` / API geändert | `./scripts/check_botanik_api.sh` (nur wenn lokaler oder produktiver Server erreichbar; sonst Grund protokollieren) |
| `index.html` geändert | `python3 -m pytest tests/test_frontend_workflow.py -v` |
| `server.py` oder Analyse-Logik geändert | `python3 -m pytest tests/test_analyze.py -v` |
| TypeScript-Check | `npx tsc --strict --noEmit` **nicht verwenden** — kein `tsconfig.json` vorhanden |

Falls ein Test nicht ausführbar ist: Grund explizit im Protokoll nennen. Keine Testergebnisse erfinden.

---

## Ausgabeformat

Nach jedem Arbeitszyklus wird dieses Protokoll ausgegeben:

```
Beobachtung:
- Was wurde in Jam, Logs oder UI tatsächlich gesehen?

Reproduktionsschritte:
- Welche Schritte führen zum Verhalten?

Ursache:
- Welche technische Ursache wurde im Repository gefunden?
- Welche Annahmen bleiben unsicher?

Patch:
- Welche Dateien wurden geändert?
- Was wurde geändert?
- Warum ist die Änderung minimal?

Tests:
- Welche Tests wurden ausgeführt?
- Ergebnis jedes Tests.
- Falls nicht ausgeführt: Grund.

Restrisiken:
- Welche Unsicherheiten bleiben?
- Welche Fälle sind noch nicht abgedeckt?

Nächster Schritt:
- Was soll als nächstes geprüft oder freigegeben werden?
```

---

## Referenzfall

**GitHub Issue #2 — Falsches Suchergebnis bei botanischem Begriff**

| | |
|---|---|
| Issue | [xq5vsgw885-glitch/overleaf#2](https://github.com/xq5vsgw885-glitch/overleaf/issues/2) |
| Jam | `0b786c0d-0a1e-49dc-ad59-36967a35be3b` |
| Commit | `881bfca` — `fix(botanik): prevent stale default search results` |
| Ergebnis | Jam-Befund → Diagnose → Patch → Tests (26/26) → Commit → Push → Produktiv-Verifikation → Issue geschlossen |

**Ursache:** `value="Acer"` im Suchfeld und automatischer `searchTaxa()`-Aufruf beim Seitenaufruf führten zu irreführenden Vorlageergebnissen; kein `oninput`-Handler verhinderte automatische Aktualisierung bei Eingabe.

**Patch:** `botanik.html` — Startwert entfernt, neutraler Placeholder gesetzt, 300 ms Debounce via `oninput` ergänzt, leerer Guard in `searchTaxa()` hinzugefügt, initialer Aufruf entfernt.
