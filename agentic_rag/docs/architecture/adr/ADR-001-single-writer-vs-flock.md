# ADR-001 — Single Audit Writer: Writer-pro-Hook mit `flock` statt langlebigem Dienst

- **Status:** Proposed
- **Datum:** 2026-08-01
- **Betrifft:** `audit_trail.db`, Schreibpfad aller Audit-Ereignisse
- **Entscheidungsgate:** offen — siehe Abschnitt 8

---

## 1. Kontext

Die Zielarchitektur aus `IMPLEMENTATION_SPEC.md` §2 sieht **einen langlebigen
Single Audit Writer** vor, an den alle Producer über eine gemeinsame
`multiprocessing.Queue` senden.

Die aktuelle Implementierung weicht davon ab: Jeder Hook-Prozess startet
**seinen eigenen, kurzlebigen Writer**, sendet über eine prozesslokale Queue
und fährt ihn beim Prozessende geordnet herunter. Die Invariante „höchstens
eine schreibende SQLite-Verbindung" wird nicht durch die Queue hergestellt,
sondern durch ein exklusives `flock` auf `<db>.writer.lock`.

Auslöser der Abweichung: Die Hooks von Claude Code (`SubagentStart`,
`SubagentStop`, `PreToolUse`) sind voneinander unabhängige, kurzlebige
Prozesse. Eine `multiprocessing.Queue` existiert nur innerhalb der
Prozessgruppe, die sie erzeugt hat; ein per CLI gestarteter Dauerläufer wäre
für die Hooks nicht erreichbar, ohne einen Transportmechanismus einzuführen,
den §2 nicht vorsieht (Unix-Socket, Named Pipe, HTTP).

Diese ADR dokumentiert den **aktuellen Entscheidungsstand**. Sie ändert
keinen Code.

---

## 2. Bewertete Optionen

### Option 1 — Writer-pro-Hook mit `flock` *(aktueller Stand)*

Jeder Producer startet einen Writer-Kindprozess. Der Writer erwirbt vor dem
Öffnen der Schreibverbindung ein exklusives `flock`; ein zweiter Writer
**wartet** darauf, statt in SQLites `database is locked` zu laufen.
Ereignisse liegen ausschließlich im Arbeitsspeicher (Queue), bis der Writer
sie committet.

### Option 2 — Langlebiger lokaler Writer-Dienst

Ein dauerhaft laufender Prozess hält die einzige Schreibverbindung.
Producer senden über einen prozessübergreifenden Transport (Unix-Domain-Socket
oder Named Pipe). Ereignisse liegen bis zum Commit im Speicher des Dienstes.

### Option 3 — Persistenter Spool plus Writer-Dienst

Producer schreiben jedes Ereignis zunächst **fsync-fest** in ein
Append-only-Spool-Verzeichnis (eine Datei je Ereignis oder ein
Segment-Log). Ein langlebiger Writer liest den Spool, persistiert nach
SQLite und quittiert; quittierte Einträge werden erst danach entfernt.

---

## 3. Bewertung

| Kriterium | 1 — Writer-pro-Hook + `flock` | 2 — Langlebiger Dienst | 3 — Spool + Dienst |
|---|---|---|---|
| **Datenverlust bei Prozessabbruch** | Ereignisse in der Queue sind flüchtig; ein `SIGKILL` des Producers oder des Writers verliert alles, was noch nicht committet war. Der Verlust wird erkannt (siehe unten), aber nicht verhindert. | wie 1 für Ereignisse im Transportpuffer; der Dienst überlebt jedoch den Producer | Producer-seitiger `fsync` vor der Bestätigung; Verlust nur bei Medienfehler |
| **Datenverlust bei Host-Abbruch** | alles Nicht-Committete geht verloren | dito | Spool überlebt den Neustart, Wiederaufnahme möglich |
| **SQLite-Concurrency** | gelöst: `flock` serialisiert **vor** dem Verbindungsaufbau, WAL bleibt aktiv, Leser sind nicht blockiert | gelöst durch Konstruktion | gelöst durch Konstruktion |
| **Globale Ereignisreihenfolge** | innerhalb einer Writer-Sitzung streng; **zwischen** Sitzungen bestimmt die Lock-Reihenfolge, nicht die Entstehungszeit | streng global | streng global, zusätzlich über Spool-Sequenz rekonstruierbar |
| **Ack / Retry** | kein Ack: `send()` legt in die Queue und kehrt zurück. Fehlende Persistenz wird erst beim Shutdown geprüft, ein Retry findet nicht statt | Ack möglich, wenn der Transport ihn vorsieht | Ack ist konstitutiv; Retry ergibt sich aus dem nicht quittierten Spool-Eintrag |
| **Crash-Recovery** | keine Wiederaufnahme; ein abgebrochener Lauf wird als `blocked` markiert, seine verlorenen Ereignisse bleiben verloren | Neustart des Dienstes, Transportpuffer verloren | Wiederaufnahme aus dem Spool |
| **Integrationsaufwand (Hooks)** | **gering** — keine zusätzliche Infrastruktur, kein Lebenszyklus außerhalb des Hooks | hoch: Dienststart, Aufräumen verwaister Sockets, Fehlerbild „Dienst nicht erreichbar" | hoch: zusätzlich Spool-Verzeichnis, Rotation, Aufräumen |
| **Lokale Wartbarkeit** | **hoch** — ein Prozessbaum, ein Log, keine Hintergrunddienste | mittel: Dienst muss laufen und beobachtet werden | niedrig: zwei bewegliche Teile plus Spool-Zustand |
| **Eignung Evaluation** | **ausreichend** — Läufe sind kurz, Abbrüche sind selten und werden als Befund sichtbar | ausreichend | überdimensioniert |
| **Eignung Produktion** | **unzureichend** bei Durabilitätsanforderungen | grenzwertig | **geeignet** |

---

## 4. Vorläufige Entscheidung

**Option 1 bleibt als Übergangsarchitektur der Phase 1 zulässig**, sofern
die in Abschnitt 7 genannten Tests die folgenden fünf Punkte belegen:

1. **Keine parallelen SQLite-Schreiber.** Zu keinem Zeitpunkt existiert mehr
   als eine schreibende Verbindung auf `audit_trail.db`.
2. **Lock-Timeouts werden explizit behandelt.** Ein nicht erhaltenes Lock
   führt zu einem definierten, protokollierten Fehlerzustand — nicht zu
   stillem Verlust und nicht zu einem als erfolgreich geltenden Lauf.
3. **Eventverluste werden erkannt.** Ein Producer stellt nach dem Shutdown
   fest, ob jedes gesendete Ereignis persistiert wurde, und eskaliert
   andernfalls.
4. **Hash-Kette und Commit-Reihenfolge bleiben konsistent.** Die Kette ist
   aus `audit_events` allein nachrechenbar, auch über mehrere
   Writer-Sitzungen hinweg.
5. **Keine direkten ungeschützten Schreibpfade.** Außerhalb des
   Writer-Prozesses existiert kein Weg, in `audit_trail.db` zu schreiben.

**Zielarchitektur für produktionsnahe Durabilität bleibt Option 3**
(persistenter Spool plus langlebiger Writer). Option 1 ist eine
Aufwandsentscheidung für die Evaluationsphase, keine Aussage darüber, dass
die Durabilitätslücke geschlossen wäre.

---

## 5. Was diese Architektur ausdrücklich **nicht** leistet

Diese Punkte sind nicht als Eigenschaft des Systems zu behaupten — weder in
der Dokumentation noch in einer Veröffentlichung:

- **Kein Exactly-once-Delivery.** Zugesichert ist *at-most-once* auf dem
  Transport plus *Idempotenz auf der Senke*: Doppelte Zustellung derselben
  `event_id` mit identischem Payload-Hash wird verworfen. Ein Ereignis, das
  die Queue nie verlässt, ist verloren; es gibt keinen Retry.
- **Keine vollständige Crash-Sicherheit.** Ein `SIGKILL` oder Stromausfall
  zwischen `send()` und Commit verliert das Ereignis. Erkannt wird der
  Verlust, verhindert nicht.
- **Keine Tamper-proof-Auditierung.** Die Hash-Kette erlaubt
  Manipulations-**Detektion**, nicht Manipulations-**Verhinderung**. Wer
  Schreibrechte auf die Datei besitzt, kann sie samt `chain_head` neu
  berechnen. Trigger und Authorizer erschweren das auf den regulären
  Zugriffswegen; ein externer Anker (signierte Kettenspitze, WORM-Medium,
  fremder Zeitstempeldienst) existiert nicht.

---

## 6. Konsequenzen

**Positiv.** Kein Hintergrunddienst, keine Socket-Verwaltung, kein
Spool-Zustand. Der Fehlerfall „Dienst läuft nicht" existiert nicht.
Parallele Agenten erzeugen keine Sperrfehler mehr, weil das Warten vor dem
Verbindungsaufbau stattfindet statt in SQLite.

**Negativ.** Jeder Hook-Aufruf zahlt Prozessstart, Lock-Erwerb und Migration
(letztere ist nach der ersten Ausführung ein No-op). Bei hoher Parallelität
serialisieren sich die Writer; das Lock-Timeout von 60 s ist eine
Obergrenze, die unter Last angehoben werden muss. Ereignisse sind bis zum
Commit flüchtig.

**Neutral.** Die globale Ereignisreihenfolge folgt der Lock-Reihenfolge. Für
die Auswertung ist das unerheblich, weil jede Zeile ihren eigenen
UTC-Zeitstempel trägt und die Kette die Persistenzreihenfolge dokumentiert —
nicht die Entstehungsreihenfolge. Wer beides verwechselt, liest die Kette
falsch.

---

## 7. Erforderliche Nachweise vor Annahme

| # | Nachweis | Vorhandener Test | Stand |
|---|---|---|---|
| 1 | Parallele Hook-Prozesse ohne `database is locked` | `test_audit.py::test_04_parallel_producers_without_database_locked` (4 Prozesse, 84 Ereignisse) | **belegt** |
| 2 | Lock-Timeout | `test_audit.py::test_05b_writer_sessions_do_not_overlap` prüft, dass das Lock exklusiv ist und nach dem Shutdown freigegeben wird — **nicht**, wie sich ein Writer verhält, der es nicht bekommt | **offen** |
| 3 | Hook-Abbruch vor dem Commit | — | **offen** |
| 4 | Writer-Abbruch während der Persistierung | `test_audit.py::test_07_writer_crash_is_not_a_successful_run` (harter `kill`, danach Erkennung und `WRITER_FAILURE`) — der Abbruch trifft den Writer jedoch nicht nachweislich *innerhalb* einer offenen Transaktion | **teilweise** |
| 5 | Doppelte Eventzustellung | `test_audit.py::test_08_duplicate_delivery_is_idempotent`, `test_registry_duplicate_registration_is_idempotent` | **belegt** |
| 6 | Konsistente Hash-Kette | `audit_db.verify_chain()` in 6 Testzusicherungen, u. a. `test_24_foreign_key_and_integrity_check_pass` — jeweils innerhalb **einer** Writer-Sitzung | **teilweise** |
| 7 | Wiederanlauf nach unvollständigem Lauf | — | **offen** |

Ergänzend belegt: keine ungeschützten Schreibpfade
(`test_05_only_the_writer_process_may_write`, `test_17b_writer_authorizer_blocks_update`),
Eventverlusterkennung (`AuditWriterHandle._verify_persistence`, geprüft in
`test_06_ordered_shutdown_drains_queue` und `test_07`).

---

## 8. Entscheidungsgate

Nach Vorliegen der Nachweise 2, 3, 6 (sitzungsübergreifend) und 7 gilt:

- **Alle Nachweise erbracht** → diese ADR wird auf **Accepted** gesetzt und
  Option 1 bleibt für die Evaluationsphase gültig.
- **Ein Nachweis scheitert** → diese ADR wird durch eine neue ADR
  (*ADR-002 — Persistenter Spool und langlebiger Writer*) ersetzt und auf
  **Superseded** gesetzt.

Unabhängig vom Ausgang: Für den Produktivbetrieb mit Durabilitätsanforderung
bleibt Option 3 die Zielarchitektur. Diese ADR ist kein Freibrief, Option 1
dorthin mitzunehmen.

---

## 9. Verweise

**Architektur**
- `../../../AUDIT_ARCHITEKTUR.md` — Abschnitt 2 (Daten- und Kontrollfluss),
  Abschnitt 7 (Betrieb, „Warum es kein `start` und `stop` gibt"),
  Abschnitt 8 K2 (Konflikt „Writer je Hook-Prozess"), Abschnitt 9 Punkt 4
  (Writer-Lock unter Last)
- `../../../IMPLEMENTATION_SPEC.md` §2 — ursprüngliche Zielarchitektur

**Implementierung**
- `../../../audit_writer.py`
  - `_WriterLock` — exklusives `flock`, Standard-Timeout 60 s
  - `_writer_main()` — Lock-Erwerb, Migration, Schreibverbindung,
    Ereignisschleife, geordneter Drain
  - `AuditWriterHandle.start()` — Bereitschaftssignal, Timeout 30 s
  - `AuditWriterHandle.shutdown()` — Shutdown-Reihenfolge nach §2
  - `AuditWriterHandle._verify_persistence()` — Verlusterkennung
  - `_escalate_writer_failure()` / `record_writer_failure()` — Eskalation
- `../../../audit_db.py` — `connect_write()` (Schreibsperre außerhalb des
  Writers), `connect_read()` (`mode=ro`), `_append_only_authorizer()`,
  `advance()` / `verify_chain()` (Hash-Kette)
- `../../../migrations.py` — Append-only-Trigger der Kanal-B-Tabellen

**Tests**
- `../../../test_audit.py` — `test_04`, `test_05`, `test_05b`, `test_06`,
  `test_06b`, `test_06c`, `test_07`, `test_07b`, `test_08`, `test_17`,
  `test_17b`, `test_24`
- `../../../test_hooks.py` — End-to-End über echte Prozessgrenzen
