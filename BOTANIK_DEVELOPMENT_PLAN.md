# Botanik-App Development Plan

## 1. Verbindliche Grundlage

- AGENTS.md ist verbindlich.
- Branch TU ist der produktive Botanik-App-Zweig.
- Render/Produktiv-Verifikation läuft über origin/TU.
- Nicht auf claude/setup-project-infrastructure-JgYXS für Botanik-App-Patches arbeiten.
- Keine fachlichen botanischen Inhalte ohne Quellenstatus ändern.
- Keine Datenbankänderung ohne explizite separate Freigabe.
- Kein Commit ohne Freigabe.
- Kein Push ohne separate Freigabe.
- Kein Issue-Kommentar und kein Issue-Schluss ohne Freigabe.
- Beobachtung, Interpretation, Unsicherheit und Empfehlung immer trennen.

---

## 2. Bereits abgeschlossen

- P0.2 critical-Status wird aus Standardsuche ausgeschlossen.
- P0.1 fetch-Fehlerhandling ist produktiv aktiv.
- P1.1 Stub-Taxa werden als „vorläufig" gekennzeichnet und Jam-verifiziert.
- P1.2 Quellenlabels in Suchergebnissen:
  - Commit 6ff39d6 ist auf origin/TU gepusht.
  - Jam-/Produktiv-Verifikation steht noch aus.

---

## 3. Globale Gates

### Gate 0 — Umgebungskontrolle

Vor jedem neuen Punkt:

```
pwd
git branch --show-current
git status
git log --oneline --decorate -5
test -f AGENTS.md
git rev-parse HEAD
git rev-parse origin/TU
```

Erwartung:

- Branch ist TU.
- Working tree ist clean.
- AGENTS.md ist vorhanden.
- HEAD ist identisch mit origin/TU oder Abweichung wird erklärt.

**Stop:** Wenn Branch nicht TU ist oder Working Tree nicht clean ist, nicht weiterarbeiten.

---

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

Danach stoppen und Freigabe abwarten.

---

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

Danach stoppen und Freigabe abwarten.

---

### Gate 3 — Patch

Nach Freigabe:

- nur freigegebene Dateien ändern
- keine zusätzlichen Dateien
- keine Datenbankänderung
- keine neue Dependency
- keine fachlichen Datenänderungen
- keine Refactorings außerhalb des Patchziels

Danach:

```
git diff -- <betroffene Dateien>
git status
```

- statische Checkliste gegen Patchziel
- Tests ausführen
- Patch-Protokoll ausgeben
- auf Commit-Freigabe warten

---

### Gate 4 — Tests

Standard nach Codeänderung:

```
python3.13 -m pytest tests/ -v
```

Bei server.js:

```
node --check server.js
```

Bei botanik.html:

```
python3.13 -m pytest tests/test_frontend_workflow.py -v
```

Bei API-relevanten Änderungen nach Deploy:

```
./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
```

Wenn ein Test nicht läuft:
- Testname nennen
- Fehler nennen
- erklären, ob patchbezogen oder umgebungsbedingt
- Ersatzprüfung nennen

---

### Gate 5 — Commit

Vor Commit:

```
git diff -- <betroffene Dateien>
git status
```

- alle Akzeptanzkriterien explizit prüfen
- nur erlaubte Dateien geändert

Im Standardmodus: Commit nur nach Freigabe.

Im erweiterten teilautonomen Modus: Commit automatisch erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind. Andernfalls stoppen.

Output:

- Commit-Hash
- geänderte Dateien
- Tests vor Commit
- Kurzbegründung
- nächster Schritt: Push (automatisch oder nach Freigabe)

---

### Gate 6 — Push

Im Standardmodus: Push nur nach separater Freigabe.

Im erweiterten teilautonomen Modus: Push automatisch erlaubt, wenn alle Auto-Push-Bedingungen erfüllt sind. Andernfalls stoppen.

Vor Push:

```
git status
git branch --show-current
```

Dann:

```
git push origin TU
```

Output:

- Branch
- Commit-Hash
- Remote-Status
- geänderte Dateien
- Zweck
- erwartete Produktiv-/Jam-Verifikation

---

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

---

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

**Hinweis:** Der erweiterte teilautonome Modus gilt ausdrücklich nicht für Issue-Kommentare oder Issue-Schließungen.

---

## Erweiterter teilautonomer Gate-Modus

Claude Code darf für den jeweils aktuellen P-Punkt automatisch arbeiten bis einschließlich:

- Diagnose
- Patchplan
- Patch
- Tests
- Commit
- Push

Aber nur, wenn alle Auto-Freigabebedingungen erfüllt sind.

### Auto-Freigabebedingungen für Commit

- Branch ist TU.
- Working tree war vor Beginn clean.
- Nur die für den aktuellen P-Punkt erlaubten Dateien sind geändert.
- Keine Änderung an AGENTS.md.
- Keine Änderung an BOTANIK_DEVELOPMENT_PLAN.md, außer der aktuelle Auftrag ist ausdrücklich Dokumentation.
- Keine Änderung an database/.
- Keine Änderung an package.json, package-lock.json, requirements.txt oder Dependency-Dateien.
- Keine fachlichen botanischen Daten geändert.
- Kein Refactoring außerhalb des Patchziels.
- Alle vorgesehenen Tests sind bestanden.
- Falls ein Test nicht ausführbar ist:
  - Fehler exakt protokollieren.
  - Begründung muss eindeutig umgebungsbedingt sein.
  - Der Test darf keinen direkten Bezug zum aktuellen Patch haben.
- git diff entspricht exakt dem Patchziel.
- Commit-Message entspricht BOTANIK_DEVELOPMENT_PLAN.md oder dem aktuellen Auftrag.

### Auto-Freigabebedingungen für Push

- Commit wurde gerade für den aktuellen P-Punkt erstellt.
- Branch ist weiterhin TU.
- git status ist clean.
- origin/TU ist erreichbar.
- Es gibt keinen ungeprüften zweiten Commit.
- Kein Merge/Rebase nötig.
- Push ist ein normaler Fast-Forward-Push auf origin TU.

### Harte Stopppunkte

Claude Code muss weiterhin stoppen und Freigabe einholen vor:

- Issue-Kommentar
- Issue-Schließung
- Branch-Wechsel
- Merge/Rebase
- Datenbankänderung
- Dependency-Änderung
- Änderung an AGENTS.md
- Änderung an BOTANIK_DEVELOPMENT_PLAN.md, außer ausdrücklich beauftragt
- fachlicher Änderung botanischer Inhalte
- größerem Refactoring
- unklarem Testergebnis
- fehlenden oder widersprüchlichen API-/Jam-Daten
- Änderung außerhalb des aktuellen P-Punkts

---

## 4. Restlicher Entwicklungsplan

### P1.2 — Quellenanzeige in Suchergebnissen

**Status:**
- Implementiert und gepusht: 6ff39d6.
- Nächster Schritt: Jam-Verifikation.

**Erwartung:**
- Produktivseite: https://overleaf-tdkd.onrender.com/botanik.html
- Suche „Chelidonium" zeigt Quellenlabel.
- Suche „Acer" ohne Stubs zeigt 2 Treffer mit Quellenlabel.
- Suche „Acer" mit Stub-Toggle zeigt 5 Treffer.
- Stub-Taxa zeigen weiterhin „vorläufig".
- Quellenwerte sind normalisiert:
  - Rothmaler
  - Strasburger
  - Rothmaler + Strasburger
- source_note erscheint nicht in der Trefferliste.
- Kein doppeltes Trennzeichen.

Wenn bestanden:
- Issue-Kommentar entwerfen.
- Freigabe abwarten.
- Issue schließen erst nach Freigabe.

---

### P1.3 — Sichere Taxon-Auswahl ohne inline onclick

**Ziel:**
`onclick="loadTaxon('${row.taxon_id}')"` aus Suchergebnissen entfernen.

**Diagnose:**
- botanik.html lesen.
- Vorkommen von `onclick="loadTaxon"` suchen.
- Vorkommen von taxon_id in HTML-Attributen prüfen.
- bestehende Stub- und Quellenlabel-Logik prüfen.

**Empfohlene Patchrichtung:**
- Nur botanik.html ändern.
- `data-taxon-id` verwenden.
- inline onclick entfernen.
- nach Rendern Event Listener binden.
- `loadTaxon(id)` bleibt bestehen.
- Stub-Kennzeichnung und Quellenlabel bleiben erhalten.

**Tests:**
```
python3.13 -m pytest tests/ -v
python3.13 -m pytest tests/test_frontend_workflow.py -v
```

**Jam:** Ja.

Jam-Ablauf:
- Suche Acer.
- Klicke aktives Taxon.
- Details laden.
- Stub-Toggle aktivieren.
- Suche Acer.
- Klicke Stub-Taxon.
- Details laden.

**Commit-Message:**
```
fix(botanik): replace inline taxon click handler with event binding
```

---

### P1.4 — API-Check robuster machen

**Ziel:**
`scripts/check_botanik_api.sh` soll robuste Relationen statt fragiler fester Counts prüfen.

**Diagnose:**
- `scripts/check_botanik_api.sh` lesen.
- hart codierte Counts identifizieren.
- stabile Health-Checks identifizieren.
- Checks für critical-Taxa prüfen.

**Empfohlene Patchrichtung:**
- Nur `scripts/check_botanik_api.sh` ändern.
- Starre Acer-Counts durch relationale Checks ersetzen:
  - Standard-Acer-Count > 0
  - include_stubs_count >= standard_count
  - falls Stubs vorhanden: include_stubs_count > standard_count
- P0.2-Checks ergänzen:
  - Festuca rubra erscheint nicht in Standardsuche
  - ranunculus_auricomus erscheint nicht in Standardsuche
- Health muss version/release_stage prüfen.

**Tests:**
```
bash -n scripts/check_botanik_api.sh
./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
python3.13 -m pytest tests/ -v
```

**Jam:** Nein.

**Commit-Message:**
```
test(botanik): make API check resilient to data changes
```

---

### P2.1 — Modusindikator für #results

**Ziel:**
Nutzer sollen erkennen, ob #results Suchtreffer oder Foto-Merkmale zeigt.

**Diagnose:**
- botanik.html lesen.
- Funktionen identifizieren, die #results beschreiben.
- prüfen, ob Zustände einander überschreiben.

**Empfohlene Patchrichtung:**
- Nur botanik.html ändern.
- `searchTaxa` rendert Überschrift „Suchergebnisse".
- `loadPhotoFeatures` rendert Überschrift „Foto-diagnostische Merkmale".
- Leer- und Fehlerzustände bleiben sinnvoll.
- Keine neuen Container.
- Kein Refactoring.

**Tests:**
```
python3.13 -m pytest tests/ -v
```

Statisch prüfen:
- „Suchergebnisse" in searchTaxa
- „Foto-diagnostische Merkmale" in loadPhotoFeatures
- Fehlertexte erhalten

**Jam:** Ja.

**Commit-Message:**
```
feat(botanik): add result mode headings
```

**Auto-Commit/Auto-Push:**
- erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind
- Jam-Verifikation bleibt danach separat erforderlich, falls im Punkt als nötig markiert

---

### P2.2 — Statuslabels übersetzen

**Ziel:**
Technische Statuswerte nutzerverständlich machen.

**Diagnose:**
- Statuswerte aus SQLite ermitteln.
- Statuswerte in Standardsuche prüfen.
- Anzeige in botanik.html prüfen.
- stub-Sonderlogik prüfen.

**Empfohlene Patchrichtung:**
- Nur botanik.html ändern.
- Funktion `statusLabel(status)` einführen.
- Mapping:
  - active → geprüft
  - stub → vorläufig
  - context → Kontext
  - structured_paraphrase → strukturierte Paraphrase
- Unbekannte Statuswerte escaped als Rohwert anzeigen.
- `.taxon-stub`-Logik erhalten.
- Keine Daten ändern.
- Keine Backend-Änderung.

**Tests:**
```
python3.13 -m pytest tests/ -v
```

Statisch:
- `statusLabel` existiert
- bekannte Statuswerte gemappt
- Fallback escaped
- Stub-Kennzeichnung erhalten

**Jam:** Optional, bei sichtbarer UI-Abnahme empfohlen.

**Commit-Message:**
```
feat(botanik): translate taxon status labels
```

**Auto-Commit/Auto-Push:**
- erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind
- Jam-Verifikation bleibt danach separat erforderlich, falls im Punkt als nötig markiert

---

### P2.3 — Hinweis bei LIMIT-Erreichen

**Ziel:**
Bei potenziell abgeschnittenen Suchergebnissen Hinweis anzeigen.

**Diagnose:**
- server.js LIMIT 50 prüfen.
- API-Response von `/api/botanik/taxa` prüfen.
- botanik.html Darstellung von data.count/data.rows prüfen.
- Suchbegriffe mit 50 Treffern identifizieren.

**Empfohlene Patchrichtung:**
- server.js:
  - `limit: 50` im Response ergänzen
  - `maybe_truncated: rows.length === 50` ergänzen
- botanik.html:
  - bei `maybe_truncated` Hinweis anzeigen:
    „Es werden maximal 50 Treffer angezeigt. Bitte Suche verfeinern."
- Keine Pagination.
- Keine DB-Änderung.

**Tests:**
```
node --check server.js
python3.13 -m pytest tests/ -v
```

Nach Deploy:
```
./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
```

**Jam:** Ja.

**Commit-Message:**
```
feat(botanik): warn when search results may be truncated
```

**Auto-Commit/Auto-Push:**
- erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind
- Jam-Verifikation bleibt danach separat erforderlich, falls im Punkt als nötig markiert

---

### P2.4 — API_BASE konfigurierbar machen

**Ziel:**
Lokale Entwicklung soll gegen lokale API laufen können.

**Diagnose:**
- API_BASE in botanik.html prüfen.
- prüfen, ob `window.location.origin` als Default möglich ist.
- prüfen, ob URL-Parameter `api_base` sinnvoll ist.

**Empfohlene Patchrichtung:**
- Nur botanik.html ändern.
- Default `API_BASE = window.location.origin`.
- Optionaler Override per `?api_base=http(s)://...`
- Ungültige Werte fallback auf `window.location.origin`.
- Keine Backend-Änderung.

**Tests:**
```
python3.13 -m pytest tests/ -v
```

Statisch:
- kein hardcoded Production-Default
- `window.location.origin` Default
- Override validiert

Produktiv:
- Suche funktioniert weiterhin.

**Jam:** Optional, empfohlen bei lokaler Prüfung.

**Commit-Message:**
```
chore(botanik): make API base configurable
```

**Auto-Commit/Auto-Push:**
- erlaubt, wenn alle Auto-Freigabebedingungen erfüllt sind
- Jam-Verifikation bleibt danach separat erforderlich, falls im Punkt als nötig markiert

---

## 5. P3-Strategiepunkte

### P3.1 — botanik_vocabulary prüfen

**Ziel:**
Klären, ob botanik_vocabulary produktiv genutzt wird.

Nur Diagnose:
- SQLite-Schema lesen.
- Zeilenzahl prüfen.
- Beispielzeilen anzeigen.
- Code-Nutzung via grep prüfen.
- Keine DB-Änderung.

Output: Strategieprotokoll mit Empfehlung:
- ungenutzt lassen
- Migration planen
- entfernen

Kein Patch ohne neue Freigabe.

**Auto-Commit/Auto-Push:** Nicht erlaubt. Strategie-/Diagnosepunkt. Dokumentationsänderungen nur nach explizitem Auftrag.

---

### P3.2 — app_scope-Normalisierung planen

**Ziel:**
Pipe-separierte Mehrfachwerte langfristig in sauberes Datenmodell überführen.

Nur Diagnose:
- app_scope-Werte in botanik_taxa prüfen.
- app_scope-Werte in botanik_features prüfen.
- Pipe-getrennte Mehrfachwerte prüfen.
- Nutzung in server.js prüfen.

Output: Migrationsplan in Phasen:
- Ist-Zustand
- Risiko
- Zielmodell
- Migrationsschritte
- Tests
- nicht jetzt patchen

**Auto-Commit/Auto-Push:** Nicht erlaubt. Strategie-/Diagnosepunkt. Dokumentationsänderungen nur nach explizitem Auftrag.

---

### P3.3 — Florenliste Deutschland konzeptionell einordnen

**Ziel:**
Florenliste Deutschland als Plausibilitätsquelle planen, ohne Rothmaler/Strasburger zu ersetzen.

Nur Konzeptdiagnose:
- AGENTS.md lesen.
- Quellenregeln prüfen.
- Vorkommen von „Florenliste" im Repo suchen.
- Keine Webabfrage ohne Freigabe.

Florenliste darf:
- Deutschland-Plausibilität prüfen.
- Taxonomischen Status/Vorkommen plausibilisieren.
- Als separate Quellenebene markiert werden.

Florenliste darf nicht:
- morphologische Merkmale aus Rothmaler/Strasburger ersetzen.
- neue Bestimmungsmerkmale unbelegt erzeugen.
- Quellenstatus vermischen.

**Auto-Commit/Auto-Push:** Nicht erlaubt. Strategie-/Diagnosepunkt. Dokumentationsänderungen nur nach explizitem Auftrag.

---

### P3.4 — E2E-Teststrategie

**Ziel:**
Entscheiden, ob Jam als manuelle visuelle Verifikation reicht oder Playwright/Puppeteer eingeführt werden soll.

Nur Diagnose:
- package.json lesen.
- vorhandene Tests prüfen.
- Playwright/Puppeteer-Verfügbarkeit prüfen.
- lokale Server-Startbarkeit prüfen.
- bisherige Jam-Fälle dokumentieren.

Optionen:
- A Playwright
- B Jam als manuelle E2E-Verifikation
- C jsdom/minimal

Keine Dependency ohne separate Freigabe.

**Auto-Commit/Auto-Push:** Nicht erlaubt. Strategie-/Diagnosepunkt. Dokumentationsänderungen nur nach explizitem Auftrag.

---

## 6. Abschnittsabschluss

Wenn alle Punkte P1.2 bis P3.4 erledigt oder bewusst vertagt sind:

Abschlussprotokoll erstellen:

- erledigte Punkte
- Commits
- Jam-verifizierte Fälle
- CLI-verifizierte Fälle
- offene Risiken
- bewusst vertagte P3-Themen
- empfohlene nächste Release-Version
- ob AGENTS.md oder BOTANIK_DEVELOPMENT_PLAN.md aktualisiert werden sollte

Keine Datei ändern, außer Dokumentation wird separat freigegeben.
