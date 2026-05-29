# Botanik-App Development Plan

## 1. Zweck und Rollen

Dieses Dokument ist die stabile Steuerungsdatei für die weitere Entwicklung der Botanik-App im Repository `overleaf`.

Rollenmodell:

- **ChatGPT** schreibt und aktualisiert Plan-, Handoff- und Review-Anweisungen auf GitHub.
- **Claude Code** arbeitet lokal nach `AGENTS.md`, diesem Plan und `BOTANIK_HANDOFF.md`.
- **Claude Code** führt Codeänderungen, Tests, Commits und Pushes aus, sofern die Auto-Gates erfüllt sind.
- **Der Nutzer** wird nur bei wichtigen Entscheidungen, Risiken, fachlichen Fragen oder Issue-Abschluss einbezogen.

GitHub dient als Synchronisationsfläche zwischen ChatGPT, Claude Code und Nutzer.

---

## 2. Verbindliche Grundlage

- `AGENTS.md` ist verbindlich.
- Branch `TU` ist der produktive Botanik-App-Zweig.
- Render-/Produktiv-Verifikation läuft über `origin/TU`.
- Nicht auf `claude/setup-project-infrastructure-JgYXS` für Botanik-App-Patches arbeiten.
- Keine fachlichen botanischen Inhalte ohne Quellenstatus ändern.
- Keine Datenbankänderung ohne explizite separate Freigabe.
- Keine Dependency-Änderung ohne explizite separate Freigabe.
- Keine Branch-Wechsel, Merges oder Rebases ohne explizite Freigabe.
- Issue-Kommentare und Issue-Schließungen bleiben immer freigabepflichtig.
- Beobachtung, Interpretation, Unsicherheit und Empfehlung immer trennen.

---

## 3. Source-of-truth-Dateien

- `AGENTS.md` — allgemeine Arbeitsregeln.
- `BOTANIK_DEVELOPMENT_PLAN.md` — stabile Roadmap, Gates und Autonomie-Regeln.
- `BOTANIK_WORKLOG.md` — chronologisches Arbeitsprotokoll.
- `BOTANIK_HANDOFF.md` — aktueller kompakter Übergabezustand und nächster ausführbarer Auftrag.

Regel:

- Planung gehört in `BOTANIK_DEVELOPMENT_PLAN.md`.
- Historie gehört in `BOTANIK_WORKLOG.md`.
- Nächste konkrete Aktion gehört in `BOTANIK_HANDOFF.md`.

---

## 4. Abgeschlossene und laufende Punkte

Details stehen in `BOTANIK_WORKLOG.md`.

| Punkt | Status | Commit | Verifikation |
|---|---|---:|---|
| P1.2 Quellenanzeige in Suchergebnissen | abgeschlossen | `6ff39d6` | Jam `68cb929f`, Issue #4 geschlossen |
| P1.3 Sichere Taxon-Auswahl ohne inline onclick | abgeschlossen | `28ec2fa` | Jam `23d49de8`, Issue #5 geschlossen |
| P1.4 API-Check robuster machen | implementiert und gepusht | `dd4ae15` | Live-API-Verifikation empfohlen |
| P2.1 Modusindikator für `#results` | implementiert und gepusht | `ea5fa6e` | Jam-Verifikation ausstehend |

Aktueller offener Entwicklungsblock laut Handoff: **P2.2 — Statuslabels übersetzen**.

---

## 5. Gate-Modell

### Gate 0 — Umgebungskontrolle

Vor jedem neuen Punkt:

```bash
pwd
git branch --show-current
git status
git log --oneline --decorate -5
test -f AGENTS.md
git rev-parse HEAD
git rev-parse origin/TU
```

Erwartung:

- Branch ist `TU`.
- Working tree ist clean.
- `AGENTS.md` ist vorhanden.
- HEAD ist identisch mit `origin/TU` oder Abweichung wird erklärt.

Stop:

- Wenn Branch nicht `TU` ist: stoppen.
- Wenn Working tree nicht clean ist und die Änderungen nicht zum aktuellen Auftrag gehören: stoppen.

### Gate 1 — Diagnose

Nur lesen. Keine Datei ändern.

Output:

- Beobachtung
- betroffene Komponenten
- aktueller Code-/Datenbefund
- technische Ursache oder Lücke
- fachliches Risiko
- Unsicherheiten
- Patchoptionen
- Empfehlung
- betroffene Dateien
- notwendige Tests
- Jam nötig: ja/nein

### Gate 2 — Patchplan

Vor jedem Patch:

- Ziel
- Nicht-Ziele
- betroffene Dateien
- nicht betroffene Dateien
- exakte Änderung
- Tests
- Verifikation
- Restrisiken

### Gate 3 — Patch

Nach erfülltem Gate 2:

- nur erlaubte Dateien ändern
- keine zusätzlichen Dateien
- keine Datenbankänderung
- keine neue Dependency
- keine fachlichen Datenänderungen
- keine Refactorings außerhalb des Patchziels

Danach:

```bash
git diff -- <betroffene Dateien>
git status
```

Zusätzlich:

- statische Checkliste gegen Patchziel
- Tests ausführen
- Patch-Protokoll ausgeben

### Gate 4 — Tests

Standard nach Codeänderung:

```bash
python3.13 -m pytest tests/ -v
```

Bei `server.js`:

```bash
node --check server.js
```

Bei `botanik.html`:

```bash
python3.13 -m pytest tests/test_frontend_workflow.py -v
```

Bei API-relevanten Änderungen nach Deploy:

```bash
./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
```

Wenn ein Test nicht läuft:

- Testname nennen.
- Fehler nennen.
- erklären, ob patchbezogen oder umgebungsbedingt.
- Ersatzprüfung nennen.

### Gate 5 — Commit

Vor Commit:

```bash
git diff -- <betroffene Dateien>
git status
```

Prüfen:

- alle Akzeptanzkriterien erfüllt.
- nur erlaubte Dateien geändert.
- Tests bestanden oder nicht ausführbare Tests sind sauber begründet und nicht patchbezogen.

Im erweiterten teilautonomen Modus ist Commit automatisch erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind.

### Gate 6 — Push

Im erweiterten teilautonomen Modus ist Push automatisch erlaubt, wenn alle Auto-Push-Bedingungen erfüllt sind.

Vor Push:

```bash
git status
git branch --show-current
```

Dann:

```bash
git push origin TU
```

Output:

- Branch
- Commit-Hash
- Remote-Status
- geänderte Dateien
- Zweck
- erwartete Produktiv-/Jam-Verifikation

### Gate 7 — Produktiv-/Jam-Verifikation

CLI-Verifikation reicht für:

- reine API-Änderungen
- reine Shell-/Check-Skript-Änderungen
- nicht-visuelle Backendlogik

Jam-Verifikation ist nötig für:

- UI-Darstellung
- visuelle Labels
- Klickverhalten
- Moduswechsel
- Fehlerzustände im Browser
- Nutzerverständlichkeit

Jam-Verifikationsoutput:

- Jam-ID
- Produktiv-URL
- Reproduktionsschritte
- Beobachtung
- Ergebnis gegen Erwartung
- Network-/Console-Befund
- Unsicherheiten
- Freigabeempfehlung: bestanden / Nacharbeit nötig / unklar

### Gate 8 — Issue-Abschluss

Issue-Kommentar nur nach Freigabe.

Kommentar enthält:

- Commit
- Jam-ID oder CLI-Verifikation
- was wurde behoben
- wie wurde verifiziert
- Restrisiken
- Statusvorschlag

Issue nur nach Freigabe schließen.

Der erweiterte teilautonome Modus gilt ausdrücklich nicht für Issue-Kommentare oder Issue-Schließungen.

---

## 6. Erweiterter teilautonomer Gate-Modus

Claude Code darf für den jeweils aktuellen P-Punkt automatisch arbeiten bis einschließlich:

- Diagnose
- Patchplan
- Patch
- Tests
- Commit
- Push
- Worklog-/Handoff-Aktualisierung

Das gilt nur, wenn alle Auto-Freigabebedingungen erfüllt sind.

### Auto-Freigabebedingungen für Commit

- Branch ist `TU`.
- Working tree war vor Beginn clean.
- Nur die für den aktuellen P-Punkt erlaubten Dateien sind geändert.
- Keine Änderung an `AGENTS.md`.
- Keine Änderung an `BOTANIK_DEVELOPMENT_PLAN.md`, außer der aktuelle Auftrag ist ausdrücklich Dokumentation.
- `BOTANIK_WORKLOG.md` und `BOTANIK_HANDOFF.md` dürfen aktualisiert werden, wenn sie nur die aktuelle Arbeit dokumentieren.
- Keine Änderung an `database/`.
- Keine Änderung an `package.json`, `package-lock.json`, `requirements.txt` oder anderen Dependency-Dateien.
- Keine fachlichen botanischen Daten geändert.
- Kein Refactoring außerhalb des Patchziels.
- Alle vorgesehenen Tests sind bestanden.
- Falls ein Test nicht ausführbar ist:
  - Fehler exakt protokollieren.
  - Begründung muss eindeutig umgebungsbedingt sein.
  - Der Test darf keinen direkten Bezug zum aktuellen Patch haben.
- `git diff` entspricht exakt dem Patchziel.
- Commit-Message entspricht diesem Plan oder dem aktuellen Auftrag.

### Auto-Freigabebedingungen für Push

- Commit wurde gerade für den aktuellen P-Punkt erstellt.
- Branch ist weiterhin `TU`.
- `git status` ist clean.
- `origin/TU` ist erreichbar.
- Es gibt keinen ungeprüften zweiten Commit.
- Kein Merge/Rebase nötig.
- Push ist ein normaler Fast-Forward-Push auf `origin TU`.

### Harte Stopppunkte

Claude Code muss stoppen und die Lage in `BOTANIK_WORKLOG.md` und `BOTANIK_HANDOFF.md` dokumentieren, wenn einer dieser Fälle eintritt:

- Issue-Kommentar nötig
- Issue-Schließung nötig
- Branch-Wechsel nötig
- Merge/Rebase nötig
- Datenbankänderung nötig
- Dependency-Änderung nötig
- Änderung an `AGENTS.md` nötig
- Änderung an `BOTANIK_DEVELOPMENT_PLAN.md` nötig, außer ausdrücklich beauftragt
- fachliche Änderung botanischer Inhalte nötig
- größere UI-/Architekturentscheidung nötig
- unklare oder rote Tests
- fehlende oder widersprüchliche API-/Jam-Daten
- Änderung außerhalb des aktuellen P-Punkts nötig

Bei Stopppunkt:

- nicht raten.
- keine riskante Ersatzhandlung ausführen.
- Beobachtung, Unsicherheit und benötigte Entscheidung dokumentieren.
- nächsten sicheren Vorschlag in `BOTANIK_HANDOFF.md` eintragen.

---

## 7. ChatGPT-Handoff-Regel

ChatGPT darf auf GitHub nur Steuerungs- und Dokumentationsdateien aktualisieren:

- `BOTANIK_DEVELOPMENT_PLAN.md`
- `BOTANIK_WORKLOG.md`
- `BOTANIK_HANDOFF.md`

ChatGPT schreibt keine App-Code-Patches direkt nach GitHub.

Regelablauf:

1. ChatGPT aktualisiert `BOTANIK_HANDOFF.md` mit dem nächsten geprüften Auftrag.
2. Claude Code führt lokal aus:

```bash
git pull origin TU
cat BOTANIK_HANDOFF.md
```

3. Claude Code bearbeitet den Auftrag nach `AGENTS.md` und diesem Plan.
4. Claude Code aktualisiert Worklog und Handoff.
5. Claude Code committet und pusht automatisch, wenn Auto-Gates erfüllt sind.
6. Bei Stopppunkten dokumentiert Claude Code die Lage und wartet.

Der Nutzer wird nur bei Design-, Fach-, Risiko- oder Issue-Entscheidungen einbezogen.

---

## 8. Worklog- und Handoff-Synchronisation

Nach jedem P-Punkt oder Verifikationsblock aktualisiert Claude Code:

- `BOTANIK_WORKLOG.md` mit chronologischen Details.
- `BOTANIK_HANDOFF.md` mit dem aktuellen kompakten Stand.

Diese Dateien dürfen zusammen mit dem jeweiligen P-Punkt committed werden, wenn:

- sie nur die aktuelle Arbeit beschreiben.
- `BOTANIK_WORKLOG.md` keine spekulative Planung enthält.
- `BOTANIK_HANDOFF.md` kompakt bleibt.
- `AGENTS.md` nicht geändert wird.

Issue-Kommentare und Issue-Schließungen bleiben immer freigabepflichtig.

---

## 9. Aktive Roadmap

### P2.2 — Statuslabels übersetzen

Ziel:
Technische Statuswerte nutzerverständlich machen.

Diagnose:

- Statuswerte aus SQLite ermitteln.
- Statuswerte in Standardsuche prüfen.
- Anzeige in `botanik.html` prüfen.
- bestehende `stub`-Sonderlogik prüfen.

Empfohlene Patchrichtung:

- Nur `botanik.html` ändern.
- Funktion `statusLabel(status)` einführen.
- Mapping:
  - `active` → `geprüft`
  - `stub` → `vorläufig`
  - `context` → `Kontext`
  - `structured_paraphrase` → `strukturierte Paraphrase`
- Unbekannte Statuswerte escaped als Rohwert anzeigen.
- `.taxon-stub`-Logik erhalten.
- Keine Daten ändern.
- Keine Backend-Änderung.

Tests:

```bash
python3.13 -m pytest tests/test_frontend_workflow.py -v
python3.13 -m pytest tests/ --ignore=tests/test_analyze.py -v
```

Jam:
Optional; empfohlen, wenn die visuelle Statusdarstellung unklar ist.

Commit-Message:

```text
feat(botanik): translate taxon status labels
```

Auto-Commit/Auto-Push:
Erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind.

### P2.3 — Hinweis bei LIMIT-Erreichen

Ziel:
Bei potenziell abgeschnittenen Suchergebnissen Hinweis anzeigen.

Diagnose:

- `server.js` LIMIT 50 prüfen.
- API-Response von `/api/botanik/taxa` prüfen.
- `botanik.html` Darstellung von `data.count` / `data.rows` prüfen.
- Suchbegriffe mit 50 Treffern identifizieren.

Empfohlene Patchrichtung:

- `server.js`:
  - `limit: 50` im Response ergänzen.
  - `maybe_truncated: rows.length === 50` ergänzen.
- `botanik.html`:
  - bei `maybe_truncated` Hinweis anzeigen:
    „Es werden maximal 50 Treffer angezeigt. Bitte Suche verfeinern.“
- Keine Pagination.
- Keine DB-Änderung.

Tests:

```bash
node --check server.js
python3.13 -m pytest tests/ --ignore=tests/test_analyze.py -v
./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
```

Jam:
Ja, weil UI-Hinweis sichtbar geprüft werden muss.

Commit-Message:

```text
feat(botanik): warn when search results may be truncated
```

Auto-Commit/Auto-Push:
Erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind. Jam-Verifikation bleibt danach separat erforderlich.

### P2.4 — API_BASE konfigurierbar machen

Ziel:
Lokale Entwicklung soll gegen lokale API laufen können.

Diagnose:

- `API_BASE` in `botanik.html` prüfen.
- prüfen, ob `window.location.origin` als Default möglich ist.
- prüfen, ob URL-Parameter `api_base` sinnvoll ist.

Empfohlene Patchrichtung:

- Nur `botanik.html` ändern.
- Default `API_BASE = window.location.origin`.
- Optionaler Override per `?api_base=http(s)://...`.
- Ungültige Werte fallback auf `window.location.origin`.
- Keine Backend-Änderung.

Tests:

```bash
python3.13 -m pytest tests/test_frontend_workflow.py -v
python3.13 -m pytest tests/ --ignore=tests/test_analyze.py -v
```

Produktiv:
Suche muss weiterhin funktionieren.

Jam:
Optional, empfohlen bei lokaler Prüfung.

Commit-Message:

```text
chore(botanik): make API base configurable
```

Auto-Commit/Auto-Push:
Erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind.

---

## 10. P3-Strategiepunkte

P3-Punkte sind zunächst Diagnose-/Strategiepunkte. Auto-Commit/Auto-Push ist nicht automatisch erlaubt, außer der Auftrag ist ausdrücklich Dokumentation.

### P3.1 — `botanik_vocabulary` prüfen

Ziel:
Klären, ob `botanik_vocabulary` produktiv genutzt wird.

Nur Diagnose:

- SQLite-Schema lesen.
- Zeilenzahl prüfen.
- Beispielzeilen anzeigen.
- Code-Nutzung via grep prüfen.
- Keine DB-Änderung.

Output:
Strategieprotokoll mit Empfehlung:

- ungenutzt lassen
- Migration planen
- entfernen

Kein Patch ohne neue Freigabe.

### P3.2 — `app_scope`-Normalisierung planen

Ziel:
Pipe-separierte Mehrfachwerte langfristig in sauberes Datenmodell überführen.

Nur Diagnose:

- `app_scope`-Werte in `botanik_taxa` prüfen.
- `app_scope`-Werte in `botanik_features` prüfen.
- Pipe-getrennte Mehrfachwerte prüfen.
- Nutzung in `server.js` prüfen.

Output:
Migrationsplan in Phasen:

- Ist-Zustand
- Risiko
- Zielmodell
- Migrationsschritte
- Tests
- nicht jetzt patchen

### P3.3 — Florenliste Deutschland konzeptionell einordnen

Ziel:
Florenliste Deutschland als Plausibilitätsquelle planen, ohne Rothmaler/Strasburger zu ersetzen.

Nur Konzeptdiagnose:

- `AGENTS.md` lesen.
- Quellenregeln prüfen.
- Vorkommen von „Florenliste“ im Repo suchen.
- Keine Webabfrage ohne Freigabe.

Florenliste darf:

- Deutschland-Plausibilität prüfen.
- taxonomischen Status/Vorkommen plausibilisieren.
- als separate Quellenebene markiert werden.

Florenliste darf nicht:

- morphologische Merkmale aus Rothmaler/Strasburger ersetzen.
- neue Bestimmungsmerkmale unbelegt erzeugen.
- Quellenstatus vermischen.

### P3.4 — E2E-Teststrategie

Ziel:
Entscheiden, ob Jam als manuelle visuelle Verifikation reicht oder Playwright/Puppeteer eingeführt werden soll.

Nur Diagnose:

- `package.json` lesen.
- vorhandene Tests prüfen.
- Playwright/Puppeteer-Verfügbarkeit prüfen.
- lokale Server-Startbarkeit prüfen.
- bisherige Jam-Fälle dokumentieren.

Optionen:

- A Playwright
- B Jam als manuelle E2E-Verifikation
- C jsdom/minimal

Keine Dependency ohne separate Freigabe.

---

## 11. Abschnittsabschluss

Wenn alle Punkte P2.2 bis P3.4 erledigt oder bewusst vertagt sind:

Abschlussprotokoll erstellen:

- erledigte Punkte
- Commits
- Jam-verifizierte Fälle
- CLI-verifizierte Fälle
- offene Risiken
- bewusst vertagte P3-Themen
- empfohlene nächste Release-Version
- ob `AGENTS.md` aktualisiert werden sollte

Keine Datei ändern, außer Dokumentation wird separat freigegeben.
