# Implementierungsauftrag für Claude Code
## Agentic RAG Audit & Provenance Engine — Phase 1 und 2

## 0. Auftrag und verbindlicher Arbeitsmodus

Arbeite im bereitgestellten Projekt **`Agentic RAG`**. Analysiere zuerst den vollständigen Ist-Zustand und implementiere danach die spezifizierte Audit-Architektur in den bestehenden Python-/SQLite-Code.

Diese Spezifikation ist verbindlich. Triff keine abweichenden Architekturentscheidungen. Falls eine Vorgabe technisch nicht mit dem vorhandenen Code vereinbar ist, stoppe den betroffenen Teil, dokumentiere den Konflikt präzise und implementiere keine stillschweigende Ersatzlösung.

### Verbindliche Arbeitsregeln

1. Beginne mit einer Bestandsaufnahme der vorhandenen Dateien, Datenflüsse, Datenbankschemata und Tests.
2. Erstelle vor Änderungen einen kurzen Implementierungsplan mit betroffenen Dateien und Migrationsrisiken.
3. Bewahre bestehende funktionierende Parser-, Chunking-, Locator- und Identitätslogik.
4. Ändere keine wissenschaftlichen Inhalte und keine fachlichen Prompting-Strategien außerhalb des Audit-Outputs.
5. Implementiere produktiven, ausführbaren Code; kein Pseudocode und keine isolierten Demonstrationsdateien.
6. Arbeite inkrementell und führe nach jedem Teilbereich die relevanten Tests aus.
7. Bestehende Daten dürfen nicht verloren gehen oder stillschweigend umgedeutet werden.
8. Externe LLM-Aufrufe dürfen in automatisierten Tests nicht erforderlich sein.
9. Jede Abweichung, Blockade oder verbleibende Unsicherheit muss im Abschlussbericht genannt werden.

---

## 1. Verifizierter Projektbestand

Der bereitgestellte Quellstand enthält mindestens:

- `rag_start.py` — aktueller `SubagentStart`-Hook; erzeugt den Run und injiziert einen Freitext-`<<<AUDIT>>>`-Vertrag.
- `rag_stop.py` — Auswertung und Persistierung des Subagentenabschlusses.
- `protect_audit_db.py` — Schutzmechanismus gegen unzulässige Datenbankmutation.
- `audit_db.py` — SQLite-Verbindung, Zeitstempel, Quellen-Normalisierung und Hash-Kette.
- `schema.sql` — Audit-Schema v1.0 mit `runs`, `assertions`, `actions` und `chain_head`.
- `schema_provenance.sql` — erweitertes Provenienzschema; vor Änderungen vollständig prüfen und konsolidieren.
- `store.py` — Persistenz der Ingestion-/Provenienzdaten.
- `ingest.py`, `chunker.py`, `canonicalize.py`, `identity.py`, `locators.py` — Ingestion-, Chunking-, Identitäts- und Locator-Pipeline.
- `ipynb_parser.py`, `pptx_parser.py`, `omml.py` — Dokumentparser.
- `test_chunker.py`, `test_acceptance.py` — bestehende Invarianten- und Akzeptanztests.
- `settings.hooks.json` — aktuelle Hook-Konfiguration.

Prüfe zusätzlich alle Importe, relativen Pfade und tatsächlichen Datenbankzugriffe. Insbesondere ist zu klären, wie `schema.sql` und `schema_provenance.sql` aktuell gemeinsam oder getrennt verwendet werden.

---

## 2. Zielarchitektur: Single Audit Writer

### Ziel

Alle konkurrierenden SQLite-Schreibzugriffe aus Hooks, Agentenprozessen und sonstigen Produzenten werden durch genau einen schreibenden Prozess ersetzt. Dadurch sollen parallele Agenten keine `database is locked`-Fehler mehr verursachen.

### Verbindliche Anforderungen

- Kommunikation über eine lokale `multiprocessing.Queue`.
- Queue-Payloads ausschließlich als UTF-8-kompatible JSON-Strings.
- Jeder Producer validiert ein Event vor dem Senden mit Pydantic.
- Der Audit Writer validiert dieselbe Payload nach Empfang erneut.
- Nur der Audit Writer besitzt eine schreibende Verbindung zu `audit_trail.db`.
- Andere Komponenten dürfen höchstens lesende Verbindungen öffnen.
- Der Writer ist ein regulärer Prozess, ausdrücklich **nicht** `daemon=True`.
- Geordnetes Herunterfahren über ein typisiertes Sentinel-/Shutdown-Event; kein untypisiertes magisches Objekt.
- Shutdown-Reihenfolge:
  1. Annahme neuer fachlicher Events stoppen,
  2. bereits akzeptierte Queue-Events vollständig abarbeiten,
  3. offene Transaktion committen oder kontrolliert zurückrollen,
  4. SQLite-Verbindung schließen,
  5. Writer-Prozess mit `join()` beenden.
- Keine LLM-Aufrufe, Dateiparsings oder sonstigen lang laufenden Arbeiten innerhalb einer offenen SQLite-Transaktion.
- WAL-Modus und Foreign Keys bleiben aktiviert.
- Der Writer muss Start-, Betriebs-, Fehler- und Shutdown-Zustände eindeutig protokollieren.
- Ein Writer-Ausfall darf nicht als erfolgreicher Run erscheinen.

### Transportintegrität

Jedes Event benötigt mindestens:

- `event_id`
- `event_type`
- `schema_version`
- `run_id`, soweit das Event zu einem Run gehört
- UTC-Zeitstempel
- kanonisch serialisierbare Payload
- Integritätswert oder deterministischen Payload-Hash

Doppelte Zustellung desselben Events muss idempotent behandelt werden. Dieselbe `event_id` mit abweichendem Payload-Hash ist eine Integritätsverletzung und führt zu `BLOCKED`.

---

## 3. Unveränderlicher RunContext

Definiere einen strikt validierten und zur Laufzeit unveränderlichen `RunContext`.

### Pflichtfelder

- `experiment_id`
- `workflow_condition`: exakt `A`, `B` oder `C`
- `domain`: exakt `physics`, `biology` oder `chemistry`
- `model_version`
- `output_enforcement`: exakt `native` oder `prompt`
- `provider`
- `schema_version`

### RunStartEvent

Das `RunStartEvent` enthält zusätzlich mindestens:

- `event_type = "run_started"`
- eindeutige `event_id`
- eindeutige `run_id`
- `agent_id`
- `parent_session_id`
- `agent_type`
- `cwd`
- UTC-Zeitstempel `started_at`
- vollständigen `RunContext`

Der Kontext wird genau einmal erzeugt. Nach erfolgreicher Persistierung dürfen seine Kontrollvariablen nicht geändert werden. Ein späteres Event mit derselben `run_id`, aber abweichendem Kontext, ist ein Hard Fail.

### Identitätsmodell

Trenne semantisch:

- `experiment_id`: gesamte Evaluierung oder Experimentserie,
- `parent_session_id`: übergeordnete Claude-Code-Sitzung,
- `run_id`: ein einzelner auswertbarer Lauf,
- `agent_id`: konkreter Subagent innerhalb dieses Laufs.

Prüfe, ob das bestehende Schema `agent_id` fälschlich als alleinigen Primärschlüssel des Runs verwendet. Migriere auf ein Modell, in dem `run_id` die primäre Evaluierungseinheit ist und `agent_id` eindeutig innerhalb des vorgesehenen Geltungsbereichs bleibt.

---

## 4. Datenbankschema und Migration

### Runs

Persistiere den vollständigen `RunContext` als kanonisches JSON und zusätzlich folgende Felder als eigene indizierte Spalten:

- `experiment_id`
- `workflow_condition`
- `domain`
- `provider`
- `model_version`
- `output_enforcement`
- `schema_version`

Alle Actions, Assertions, Claims, Chunks, Reparaturen und Audit-Events müssen eindeutig auf `run_id` zurückführbar sein. Wo eine Agentenzuordnung relevant ist, wird zusätzlich `agent_id` gespeichert.

### Migrationsanforderungen

- Prüfe `schema.sql` und `schema_provenance.sql` vollständig und definiere eine einzige eindeutige Schema-Wahrheit.
- Erstelle eine idempotente, versionierte Migration.
- Lege vor jeder Migration eine überprüfbare Sicherung der vorhandenen Datenbank an.
- Bestehende Datensätze dürfen nicht gelöscht werden.
- Fehlende historische Kontrollvariablen dürfen nicht erfunden werden.
- Alte Datensätze werden explizit als `legacy` beziehungsweise `context_incomplete` markiert.
- Nach Migration müssen `PRAGMA foreign_key_check` und ein Integritätscheck erfolgreich sein.
- Häufig ausgewertete Kontrollvariablen sind über normale SQLite-Indizes abfragbar; ein JSON-Feld allein genügt nicht.

---

## 5. Hybrider Output-Adapter

Implementiere eine providerunabhängige Adapter-Schnittstelle für strukturierte Modellausgaben.

### Priorität

1. Native Structured Outputs oder erzwungenes Tool Calling, sofern der Provider dies zuverlässig unterstützt.
2. Prompt-basiertes Schema-Enforcement als dokumentierter Fallback.

### Autorität

Unabhängig vom Generierungsmodus sind ausschließlich folgende Komponenten autoritativ:

1. Pydantic-Validierung,
2. referenzielle Validierung,
3. Channel Reconciler,
4. Hard-Fail-Policy.

Syntaktisch valides Provider-JSON ist allein kein Akzeptanzkriterium.

### Evaluierungsinvariante

Innerhalb desselben experimentellen Vergleichs beziehungsweise Runs darf `output_enforcement` nicht wechseln. Ein Wechsel ist ein Konfigurations- und Integritätsfehler und führt zu `BLOCKED`.

Die bestehende Freitextausgabe mit `<<<AUDIT>>>` darf nur als explizit dokumentierter Legacy-/Prompt-Fallback weiterbestehen. Sie darf nicht länger der primäre Audit-Transport sein.

---

## 6. Typisierte Ergebnis- und Claim-Modelle

Definiere Pydantic-Modelle für mindestens:

- `AgentResult`
- `Claim`
- `EvidenceReference`
- `ValidationFailure`
- `RepairAttempt`
- `AuditEvent`
- `WriterShutdownEvent`

Verwende strikte Feldtypen, verbiete unbekannte Felder, wo dies mit Rückwärtskompatibilität vereinbar ist, und versioniere die Schemas.

Jeder Claim und jeder daraus erzeugte Text-Chunk erhält genau einen Status:

- `VERIFIED`
- `PARTIALLY_VERIFIED`
- `UNVERIFIED`
- `BLOCKED`

### Statusregeln

- `VERIFIED`: Alle für den Claim erforderlichen und deklarierten Quellen wurden im selben Run in Kanal B tatsächlich aufgerufen und stimmen referenziell mit Kanal A überein.
- `PARTIALLY_VERIFIED`: Mindestens eine erforderliche Quelle ist bestätigt, mindestens eine weitere erforderliche Evidenz fehlt oder ist ungültig.
- `UNVERIFIED`: Keine erforderliche Evidenz konnte bestätigt werden oder eine reine Formatvalidierung scheitert nach Ausschöpfung der zulässigen Reparaturen.
- `BLOCKED`: Mindestens eine Hard-Fail-Bedingung liegt vor.

Ein Claim ohne erforderliche Evidenz darf nicht allein aufgrund einer leeren Deklarationsliste als `VERIFIED` gelten. Definiere hierfür eine explizite evidenzfreie Claim-Kategorie oder setze ihn auf `UNVERIFIED`, abhängig vom bestehenden fachlichen Modell. Dokumentiere die gewählte, minimal-invasive Lösung.

`PARTIALLY_VERIFIED` ist im Produktionsmodus nicht zulässig.

---

## 7. Channel Reconciler

### Zwei-Kanal-Prinzip

- Kanal A: vom Agenten deklarierte Claims und Evidenzreferenzen.
- Kanal B: tatsächlich protokollierte physische Tool-, Datei- und Quellenzugriffe.

### Verbindliche Regeln

- Kanal B ist die historische Zugriffswahrheit.
- Eine Quelle wird nur bestätigt, wenn sie im selben `run_id` physisch protokolliert wurde.
- Falls Agenten innerhalb eines Runs getrennte Evidenzräume besitzen, muss zusätzlich der zulässige `agent_id`-Scope geprüft werden.
- Unbekannte Evidence-IDs, fremde Run-IDs und nachträglich konstruierte Referenzen werden nicht akzeptiert.
- Die bestehende Funktion zur Quellen-Normalisierung in `audit_db.py` ist kritisch zu prüfen. Eine aggressive Normalisierung darf nicht zwei unterschiedliche Quellen kollidieren lassen.
- Ein Format-Retry darf fehlenden physischen Zugriff nicht nachträglich legitimieren.
- Neue Evidenzbeschaffung ist eine separate Retrieval-Phase mit neuen Kanal-B-Events.
- Reconciliation-Ergebnisse müssen reproduzierbar und erneut berechenbar sein.

---

## 8. Repair Engine

Erlaube maximal zwei Reparaturversuche ausschließlich für Syntax- und Formatfehler.

### Zulässiger Reparaturkontext

Die Reparatur erhält nur:

- ursprüngliche Modellausgabe,
- erwartetes Schema,
- konkreten Validatorfehler,
- bereits zulässige Evidence-IDs.

### Verbotene Änderungen

Die Reparatur darf:

- keine fachliche Aussage ergänzen,
- keinen Claim semantisch verändern,
- keine neue Quelle oder Evidence-ID einführen,
- keine Retrieval-Aktion starten,
- keinen Kanal-B-Datensatz erzeugen oder verändern.

### Protokollierung

Tracke pro repariertem Objekt mindestens:

- `repair_count`
- stabile Fehlerklasse
- UTC-Zeitstempel
- Hash der ursprünglichen Ausgabe
- Hash der reparierten Ausgabe
- Validierungsergebnis

Nach zwei erfolglosen reinen Format-Reparaturen lautet der Status `UNVERIFIED`, sofern keine Hard-Fail-Bedingung vorliegt.

Format-Reparatur und Evidenz-Reparatur müssen getrennte Zustände, Events und Kontrollflüsse besitzen.

---

## 9. Hard-Fail Policy

Setze einen Run, Claim oder Chunk ohne Reparaturversuch sofort auf `BLOCKED`, wenn mindestens eine der folgenden Bedingungen eintritt:

1. erkannte Prompt-Injection oder Manipulation,
2. fehlende, leere oder ungültige `run_id`,
3. fehlender oder ungültiger `RunContext`,
4. Kontextmutation innerhalb desselben Runs,
5. Schema- oder Versionskonflikt zwischen Producer und Audit Writer,
6. Referenzierung nicht existierender oder fremder Run-Daten,
7. sicherheitsrelevante Zugriffsverweigerung durch einen Hook,
8. beschädigte, nicht parsebare oder nicht vertrauenswürdige Queue-Payload,
9. Payload-Hash stimmt nicht mit dem Eventinhalt überein,
10. identische `event_id` mit abweichendem Inhalt,
11. Versuch, historische Kanal-B-Daten zu ändern oder zu löschen,
12. nicht reproduzierbarer interner Ausnahmezustand,
13. Wechsel des Output-Enforcement-Modus innerhalb desselben Runs,
14. Writer-Ausfall oder unvollständiger kontrollierter Shutdown, sofern die Persistenzvollständigkeit nicht bewiesen werden kann.

Jeder Hard Fail muss mit stabiler Fehlerklasse, Ursache, Scope und unverändert referenzierter Rohpayload protokolliert werden. Sensible Rohdaten dürfen dabei nicht unkontrolliert in Enddokumente gelangen.

Definiere explizit, ob ein Hard Fail nur einen Claim/Chunk, einen Agenten oder den gesamten Run blockiert. Die Eskalation muss deterministisch aus der Fehlerklasse folgen.

---

## 10. Append-only Audit-Integrität

Kanal-B-Daten und sicherheitsrelevante Audit-Events sind logisch append-only.

Verhindere über Anwendungscode und Datenbankschutz:

- `UPDATE` historischer Zugriffsevents,
- `DELETE` historischer Zugriffsevents,
- Überschreiben bestehender Event-Payloads,
- Wiederverwendung einer Event-ID mit anderem Inhalt,
- nachträgliche Umdeutung eines Kanal-B-Zugriffs.

Prüfe und erweitere `protect_audit_db.py` so, dass der Schutz mit dem Single-Writer-Modell kompatibel ist. Der Writer selbst darf nur die ausdrücklich erlaubten append-only Operationen ausführen.

Erhalte beziehungsweise migriere die vorhandene Hash-Kette. Prüfe, ob die aktuelle globale `chain_head` bei mehreren Ereignistypen und Transaktionen deterministisch bleibt. Dokumentiere und behebe erkannte Race-, Reihenfolge- oder Wiederanlaufprobleme, ohne die forensische Nachvollziehbarkeit zu reduzieren.

---

## 11. Dualer Exportmodus

Implementiere zwei strikt getrennte Rendering-Modi.

### `evaluation`

- `VERIFIED`: fachlichen Text normal rendern.
- `PARTIALLY_VERIFIED`: Text erhalten und stabil maschinenlesbar markieren.
- `UNVERIFIED`: Text erhalten und stabil maschinenlesbar markieren.
- `BLOCKED`: keinen fachlichen Text rendern; nur Status, Fehlerklasse und nicht-sensitive Referenzdaten ausgeben.

Verwende stabile Tags:

- `> [!WARNING] PARTIALLY_VERIFIED`
- `> [!DANGER] UNVERIFIED`
- `> [!ERROR] BLOCKED`

Die Markierung muss zusätzlich strukturiert auswertbar sein; verlasse dich nicht ausschließlich auf visuelles Markdown.

### `production`

- ausschließlich `VERIFIED` rendern,
- `PARTIALLY_VERIFIED`, `UNVERIFIED` und `BLOCKED` vollständig und kommentarlos ausschließen.

Der Exportmodus darf weder gespeicherte Statuswerte noch Audit-Daten verändern.

---

## 12. Tests und Akzeptanzkriterien

Erweitere die vorhandenen Tests, ohne die bestehenden Chunking-, Locator- und Identitätsinvarianten zu schwächen.

Mindestens folgende Tests sind verpflichtend:

1. deterministische kanonische JSON-Serialisierung und Revalidierung,
2. Laufzeit-Unveränderlichkeit des `RunContext`,
3. eindeutige Trennung von `experiment_id`, `run_id`, `session_id` und `agent_id`,
4. parallele Producer ohne `database is locked`,
5. ausschließlich ein schreibender SQLite-Prozess,
6. geordneter Writer-Shutdown mit vollständigem Queue-Drain,
7. Writer-Abbruch wird erkannt und nicht als erfolgreicher Run gewertet,
8. doppelte Eventzustellung ist idempotent,
9. gleiche Event-ID mit anderem Payload führt zu `BLOCKED`,
10. beschädigte Queue-Payload führt sofort zu `BLOCKED`,
11. unbekannte oder fremde Evidence-ID führt gemäß Hard-Fail-Policy zu `BLOCKED`,
12. reine Syntaxfehler erhalten höchstens zwei Reparaturversuche,
13. Reparatur kann keine neue Evidence-ID einführen,
14. Format-Reparatur erzeugt keine Kanal-B-Aktion,
15. Kanal-A-/Kanal-B-Abgleich erzeugt reproduzierbar alle vier Status,
16. leere Assertion-Liste wird nicht automatisch als evidenzgesicherter Claim interpretiert,
17. nachträgliche Mutation von Kanal B wird verhindert,
18. Schema-Versionskonflikt führt sofort zu `BLOCKED`,
19. Wechsel von `output_enforcement` innerhalb eines Runs führt zu `BLOCKED`,
20. Evaluationsexport erhält korrekt markierte Fehlerpassagen,
21. Evaluationsexport gibt bei `BLOCKED` keinen fachlichen Text aus,
22. Produktionsexport enthält ausschließlich `VERIFIED`,
23. Migration ist wiederholbar, verlustfrei und kennzeichnet Legacy-Daten,
24. Foreign-Key- und Datenbankintegritätsprüfung bestehen,
25. bestehende Tests in `test_chunker.py` und `test_acceptance.py` bleiben erfolgreich.

Verwende deterministische Fixtures und simulierte Provider-Adapter. Keine Tests dürfen Netz- oder API-Zugang voraussetzen.

---

## 13. Erwartete Umsetzungsschritte

Arbeite in dieser Reihenfolge:

1. Ist-Analyse und Datenflussdiagramm.
2. Schema- und Migrationsentwurf.
3. Typisierte Event- und Kontextmodelle.
4. Queue-Transport und Single Audit Writer.
5. Umstellung bestehender direkter Schreibzugriffe in `rag_start.py`, `rag_stop.py`, `store.py` und weiteren Fundstellen.
6. Hybrider Output-Adapter.
7. Validator und Channel Reconciler.
8. Repair Engine und Hard-Fail Policy.
9. Dualer Renderer.
10. Schutz- und Append-only-Regeln.
11. Tests, Migrationstest und vollständige Regression.
12. Dokumentation und Abschlussbericht.

Führe nach jedem Schritt die jeweils relevanten Tests aus. Beginne keine großflächige Umstrukturierung, bevor die Bestandsaufnahme und das Migrationskonzept vorliegen.

---

## 14. Abschlussbericht

Liefere nach Abschluss:

- vollständige Liste geänderter und neuer Dateien,
- Beschreibung des finalen Daten- und Kontrollflusses,
- finalen Schema- und Migrationsstand,
- dokumentierte Ereignis- und Fehlerklassen,
- Tabelle aller umgesetzten Invarianten,
- vollständige Testergebnisse,
- Nachweis, dass bestehende Tests weiterhin bestehen,
- verbleibende Risiken und bewusst nicht umgesetzte Punkte,
- lokale Befehle zum Initialisieren, Starten, Stoppen und Testen des Audit Writers,
- kurze Anleitung für Evaluationsexport und Produktionsexport.

## Startanweisung

Beginne jetzt ausschließlich mit der vollständigen Bestandsaufnahme. Zeige danach den konkreten Implementierungs- und Migrationsplan. Führe anschließend die Implementierung selbstständig in der festgelegten Reihenfolge vollständig aus.
