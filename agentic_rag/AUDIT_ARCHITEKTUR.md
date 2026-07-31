# Agentic RAG — Audit & Provenance Engine, Phase 1 und 2

Abschlussbericht zur Umsetzung von `IMPLEMENTATION_SPEC.md` einschliesslich
der nachtraeglich verbindlichen Zusatzvorgaben.

---

## 1. Geaenderte und neue Dateien

### Neu

| Datei | Inhalt |
|---|---|
| `policy.py` | Statuswerte, Fehlerklassen, Eskalationsbereiche, Reparaturgrenzen, Exportmodus-Sperre |
| `audit_models.py` | Pydantic-Modelle: `RunContext`, alle Events, `EventEnvelope`, `AgentResult`, `Claim`, `EvidenceReference`, `ValidationFailure`, `RepairAttempt`, `PhaseMetricsEvent`, `WriterShutdownEvent` |
| `migrations.py` | **Alleinige Schema- und Migrationsautoritaet**: Registry, Deltas, Sicherung, Integritaetspruefung |
| `audit_writer.py` | Single Audit Writer: Queue-Empfang, Revalidierung, Idempotenz, Hash-Kette, Hard-Fail-Protokoll, geordneter Shutdown, Writer-Lock |
| `audit_client.py` | Producer-Fassade: Kontext aus Umgebung, deterministische `run_id`, Event-Erzeugung, Phasen-Timer, Reparaturfenster |
| `output_adapter.py` | Hybrider Output-Adapter (`native` / `prompt`), Injektionserkennung, deterministische Test-Provider |
| `reconciler.py` | Channel Reconciler, Registry-Statusregel, Neuberechnung aus der Datenbank |
| `repair.py` | Repair Engine mit den vier Verboten aus §8 |
| `renderer.py` | Dualer Export mit maschinenlesbarer Beilage |
| `audit_ctl.py` | CLI: `init`, `status`, `verify`, `recompute`, `export`, `metrics`, `dump-schema`, `selftest` |
| `conftest.py` | Testfixtures (eigene Datenbank je Test, keine Netzabhaengigkeit) |
| `test_audit.py` | 60 Tests zu §12.1–§12.24 und den Zusatzvorgaben |
| `test_hooks.py` | 23 End-to-End-Systemtests der drei Hooks, inklusive Fault Injection |
| `test_legacy_suites.py` | §12.25 — bestehende Suiten als Unterprozess |
| `pytest.ini` | Sammelregeln |

### Geaendert

| Datei | Aenderung |
|---|---|
| `audit_db.py` | Schreibsperre ausserhalb des Writers, echte Read-only-Verbindungen, Authorizer als Append-only-Schutz, `source_key()`, Kettenpruefung, Pfadfehler behoben |
| `repair.py` | `check_repair_guards()` — eine Implementierung der §8-Verbote fuer Engine und Hook-Pfad |
| `rag_start.py` | Kein Direktschreiben mehr; `RunStartEvent` ueber den Writer, vollstaendiger `RunContext`, modusabhaengiger Vertrag |
| `rag_stop.py` | Kanal B vor Abgleich, Output-Adapter, getrennte Format- und Evidenzreparatur, Hard Fails ohne Reparatur, Statuspersistenz |
| `protect_audit_db.py` | Verbotsliste durch Erlaubnisliste ersetzt, `provenance.db` mitgeschuetzt, Verweigerung wird protokolliert |
| `store.py` | Kein `executescript` mehr beim Verbinden; Migration ueber die Registry |
| `schema.sql`, `schema_provenance.sql` | Als **Baseline** gekennzeichnet, nicht mehr direkt ausfuehrbar |
| `settings.hooks.json` | Dokumentation der Pflicht-Umgebungsvariablen |

### Unveraendert (bewusst)

`identity.py`, `locators.py`, `canonicalize.py`, `chunker.py`,
`ipynb_parser.py`, `pptx_parser.py`, `omml.py`, `ingest.py`,
`test_chunker.py`, `test_acceptance.py` — Parser-, Chunking-, Locator- und
Identitaetslogik bleibt unberuehrt (§0.3).

---

## 2. Daten- und Kontrollfluss

```
                    Umgebung (Kontrollvariablen)
                              │
SubagentStart ────────────────┼──────────────────────────────┐
  rag_start.py                │                              │
    context_from_env()  ──►  RunContext  ──► RunStartEvent    │
                                                 │            │
Subagent arbeitet                                │            │
  (Tool-Aufrufe im Transkript)                   │            │
                                                 ▼            │
SubagentStop                              ┌─────────────┐     │
  rag_stop.py                             │  Producer   │     │
    1. Injektionspruefung ── Hard Fail ──►│  validiert  │     │
    2. Transkript ──► ActionEvent (Kanal B)│  Pydantic  │     │
    3. Output-Adapter ──► AgentResult      └──────┬──────┘    │
       └─ Formfehler ──► Format-Reparatur (max 2) │           │
    4. Reconciler (A gegen B)                     │  JSON     │
       └─ fehlende Evidenz ──► Evidenz-Reparatur  │           │
    5. AssertionEvent + ClaimStatusEvent          ▼           │
                                          multiprocessing.Queue│
                                                  │           │
                                                  ▼           │
                                        ┌──────────────────┐  │
                                        │  Audit Writer    │◄─┘
                                        │  (EIN Prozess)   │
                                        │  flock(writer.lock)
                                        │  revalidiert     │
                                        │  Hash pruefen    │
                                        │  Idempotenz      │
                                        │  Hash-Kette      │
                                        └────────┬─────────┘
                                                 ▼
                                        audit_trail.db (WAL, FK an)
                                                 │
              audit_ctl.py verify / recompute / export (nur lesend)
```

`provenance.db` (Dokument-, Chunk- und Retrievalregister) bleibt der
Ingestionspfad: `ingest.py → store.py`. Beide Datenbanken werden von
derselben Migrationsregistry versioniert.

---

## 3. Schema- und Migrationsstand

| Datenbank | Version | Inhalt |
|---|---|---|
| `audit_trail.db` | **3** | `runs` (laufzentriert, Kontrollvariablen als Spalten), `run_agents`, `assertions`, `actions`, `evidence_registry`, `audit_events`, `claims`, `repairs`, `hard_fails`, `phase_metrics`, `writer_sessions`, `chain_head`, `schema_migrations` |
| `provenance.db` | **2** | Baseline v1.1 plus `run_id` in `retrieval_runs` und `assertion_evidence` |

### Migrationsverfahren

1. Bestehende Datenbank ohne `schema_migrations` wird als Version 1
   **gestempelt** (nicht neu ausgefuehrt).
2. **Sicherung** vor der ersten Aenderung ueber die SQLite-Backup-API,
   danach mit `PRAGMA integrity_check` geprueft. Dateiname:
   `<db>.backup-audit-<UTC-Zeitstempel>`.
3. Jede Migration laeuft als **eine** Transaktion (BEGIN/COMMIT im Skript —
   `executescript` committet sonst implizit vorher).
4. Danach `PRAGMA foreign_key_check` und `PRAGMA integrity_check`; schlaegt
   eines fehl, bricht die Migration mit `MigrationError` ab.
5. Wiederholter Aufruf ist folgenlos (`applied == []`, keine neue Sicherung).

### Migration 3 — Evidenzregistry

* `evidence_registry` (append-only, Teil der Hash-Kette) mit
  `UNIQUE (run_id, evidence_key)`.
* `actions` neu aufgebaut, um die zusammengesetzte Fremdschluesselbeziehung
  `(run_id, evidence_key)` → `evidence_registry(run_id, evidence_key)` zu
  ergaenzen. Bestandszeilen tragen `evidence_key IS NULL` und bleiben gueltig.
* `repairs.baseline_json` fuer die §8-Pruefung auf dem Hook-Pfad.
* Sichten: `run_overview` um `evidence_count` erweitert, `registered_evidence`
  neu.

### Behandlung der Altdaten

| Feld | Behandlung |
|---|---|
| `run_id` | `legacy:<agent_id>` |
| `is_legacy` | `1` |
| `context_state` | `context_incomplete` |
| Kontrollvariablen | `NULL` — werden **nicht** erfunden |
| `status` | v1.0-`verified` wird zu `legacy_unverified` |
| `legacy_status_v1` | Originalstatus unveraendert aufbewahrt |
| `assertions`, `actions` | Zeilen, Rohreferenzen und Hashes unveraendert uebernommen |
| `chain_head` | unveraendert |

Ein Trigger verhindert dauerhaft, dass ein Legacy-Lauf den Status
`verified` erhaelt.

---

## 4. Ereignis- und Fehlerklassen

### Ereignisse

`run_started`, `agent_registered`, `action_recorded` (Kanal B),
`evidence_registered` (Kanal B, Retrieval-Phase), `assertion_declared`
(Kanal A), `claim_status`, `repair_attempt`, `hard_fail`, `run_attempt`,
`phase_metrics`, `run_finished`, `writer_shutdown` (typisiertes Sentinel).

Ereignisschemaversion: **2.1.0**. Der Writer prueft auf Gleichheit; ein
Producer mit abweichender Version loest §9.5 aus.

### Fehlerklassen und Eskalation

| Klasse | §9 | Scope | Wirkung |
|---|---|---|---|
| `PROMPT_INJECTION` | 1 | run | Run BLOCKED, keine Reparatur |
| `MISSING_RUN_ID` | 2 | run | Run BLOCKED |
| `INVALID_RUN_CONTEXT` | 3 | run | Kein Lauf wird angelegt |
| `CONTEXT_MUTATION` | 4 | run | Run BLOCKED, Kontext bleibt der erste |
| `SCHEMA_VERSION_CONFLICT` | 5 | run | Event verworfen, Run BLOCKED |
| `FOREIGN_RUN_REFERENCE` | 6 | run | Event verworfen, Run BLOCKED |
| `HOOK_ACCESS_DENIED` | 7 | agent | Tool-Call blockiert, Run degradiert |
| `CORRUPT_QUEUE_PAYLOAD` | 8 | run | Event verworfen, Rohpayload referenziert |
| `PAYLOAD_HASH_MISMATCH` | 9 | run | Event verworfen |
| `EVENT_ID_CONFLICT` | 10 | run | Erstfassung bleibt, Run BLOCKED |
| `CHANNEL_B_MUTATION` | 11 | run | Durch Trigger und Authorizer verhindert |
| `INTERNAL_NONREPRODUCIBLE` | 12 | run | Rollback, Run BLOCKED |
| `OUTPUT_ENFORCEMENT_SWITCH` | 13 | run | Run BLOCKED |
| `WRITER_FAILURE` | 14 | writer | Run BLOCKED, Recovery-Writer protokolliert |
| `UNKNOWN_EVIDENCE_ID` | 6 (spez.) | claim | Claim BLOCKED |
| `EVIDENCE_KEY_COLLISION` | 7 (spez.) | run | Registry des Laufs unbrauchbar, Run BLOCKED |
| `EVIDENCE_INTRODUCED_BY_REPAIR` | 1 (spez.) | claim | Claim BLOCKED |
| `CLAIM_MUTATED_BY_REPAIR` | 1 (spez.) | claim | Claim BLOCKED |
| `CHANNEL_B_WRITE_DURING_REPAIR` | — | run | Senden schlaegt fehl |
| `FORMAT_VALIDATION_EXHAUSTED` | **kein** Hard Fail | claim/run | UNVERIFIED |
| `EVIDENCE_INCOMPLETE` | **kein** Hard Fail | claim | PARTIALLY_VERIFIED / UNVERIFIED |
| `NO_REQUIRED_EVIDENCE` | **kein** Hard Fail | claim | UNVERIFIED |
| `EVIDENCE_UNREGISTERED` | **kein** Hard Fail | claim | PARTIALLY_VERIFIED (Uebergangspfad) |

---

## 4a. Evidenzregistry und Statusregel (§7)

Bis Schema v2 gab es keinen Ort, an dem ein AUSGELIEFERTER Beleg
protokolliert wurde. `actions` hielt fest, dass eine Quelle beruehrt
wurde; welcher Textausschnitt welcher Dokumentfassung dem Agenten vorlag,
stand nirgends. Gleichzeitig zeigt der Locator-Header dem Agenten einen
`evidence_key` — zitierte er ihn, war er per Definition unbekannt, weil
die Registry leer war. Ein korrekt belegtes Zitat wurde damit BLOCKED.

### Die Retrieval-Phase

`audit_client.record_retrieval(chunks)` bildet die Chunkstruktur des
Chunkers auf je ein `evidence_registered`-Ereignis **pro Segment** ab
(die Provenienzeinheit ist das Segment, nicht der Chunk). Jedes Ereignis
traegt `evidence_key`, `run_id`, Dokumentidentitaet
(`source_id`/`document_version_id`/`unit_id`/`chunk_id`), Locator
(`structure_anchor`, `label`, `locator_json`), `content_sha256` der
Einheit, `chunk_text_sha256` des tatsaechlich ausgelieferten Textes,
Retrieval-Zeitpunkt sowie Parser- und Chunker-Version.

Der Writer erzeugt daraus **zwei Projektionen in einer Transaktion und mit
demselben Kettenglied**: den Registryeintrag und die zugehoerige
`actions`-Zeile (`phase='retrieval'`). Kanal B bleibt damit eine einzige
Zugriffswahrheit; jede vorhandene Abfrage sieht den Retrieval-Zugriff,
ohne die Registry kennen zu muessen.

### Idempotenz und Kollision

| Fall | Verhalten |
|---|---|
| gleiche `event_id`, gleicher Payload | bestehende Deduplizierung |
| gleicher `(run_id, evidence_key)`, gleicher `chunk_text_sha256` | idempotent, keine zweite Zeile |
| gleicher `(run_id, evidence_key)`, **anderer** `chunk_text_sha256` | `EVIDENCE_KEY_COLLISION`, Scope `run`, Hard Fail |

Die Kollision ist laufweit, nicht claimweit: Steht derselbe Schluessel fuer
zwei Inhalte, ist die Evidenzidentitaet des ganzen Laufs nicht mehr
eindeutig.

### Statusregel

```
registry      = registrierte evidence_keys dieses Runs
registry_mode = registry ist nicht leer

ev:-ID  → in registry          : bestaetigt (Registry)
        → in fremder registry  : BLOCKED / UNKNOWN_EVIDENCE_ID (fremder Run)
        → sonst                : BLOCKED / UNKNOWN_EVIDENCE_ID
lokales Label
        → registry_mode        : NICHT bestaetigt (Uebergangspfad abgeschaltet)
        → sonst                : source_key-Treffer = Uebergangsbestaetigung
```

| Lage | Status |
|---|---|
| alle erforderlichen Belege ueber die Registry bestaetigt | `VERIFIED` |
| vollstaendig bestaetigt, mindestens einer nur ueber den Uebergangspfad | `PARTIALLY_VERIFIED` |
| teils bestaetigt, teils fehlend | `PARTIALLY_VERIFIED` |
| nichts bestaetigt / leere Liste / evidenzfrei | `UNVERIFIED` |

Der `source_ref`-Uebergangspfad ist im Code als solcher markiert und kann
**nie** `VERIFIED` ergeben (`EVIDENCE_UNREGISTERED`). Sobald ein Lauf auch
nur einen registrierten Beleg hat, ist der Pfad abgeschaltet — sonst
koennte ein Agent die Registrierung umgehen, indem er statt des
Schluessels den Dateinamen nennt.

**Wirkung:** Laeufe, deren Kanal B ausschliesslich aus dem Transkript-Scan
stammt, erreichen hoechstens `PARTIALLY_VERIFIED` und den Laufstatus
`degraded`; ihr Produktionsexport ist leer. Das ist beabsichtigt — die
Registrierung ist der einzige Weg zu einer produktionsfaehigen Aussage.

---

## 5. Umgesetzte Invarianten

| Nr. | Invariante | Ort | Test |
|---|---|---|---|
| 1 | Kanonische Serialisierung deterministisch | `identity.canonical_json` | `test_01*` |
| 2 | `RunContext` laufzeit-unveraenderlich | `RunContext(frozen)` + Trigger | `test_02*` |
| 3 | Vier getrennte Identitaetsebenen | Schema, `make_run_id` | `test_03*` |
| 4 | Parallele Producer ohne `database is locked` | Writer-Lock | `test_04` |
| 5 | Genau ein schreibender Prozess | `connect_write`, `mode=ro` | `test_05*` |
| 6 | Geordneter Shutdown mit Queue-Drain | `AuditWriterHandle.shutdown` | `test_06*` |
| 7 | Writer-Abbruch ist kein erfolgreicher Run | `_verify_persistence` | `test_07` |
| 8 | Doppelzustellung idempotent | `event_id` UNIQUE | `test_08` |
| 9 | Gleiche `event_id`, anderer Inhalt → BLOCKED | `handle_raw` (5) | `test_09*` |
| 10 | Beschaedigte Payload → BLOCKED | `handle_raw` (1) | `test_10` |
| 11 | Unbekannte/fremde Evidence-ID → BLOCKED | `reconciler._verdict` | `test_11*` |
| 12 | Hoechstens zwei Formatreparaturen | `MAX_FORMAT_REPAIRS` | `test_12*` |
| 13 | Reparatur fuehrt keine Evidenz ein | `repair.baseline_of` | `test_13*` |
| 14 | Formatreparatur ohne Kanal-B-Aktion | `block_channel_b` | `test_14*` |
| 15 | Alle vier Status reproduzierbar | `reconcile` | `test_15*` |
| 16 | Leere Evidenzliste nie VERIFIED | `_verdict` (2) | `test_16*` |
| 17 | Kanal B unveraenderlich | Trigger + Authorizer | `test_17*` |
| 18 | Schemaversionskonflikt → BLOCKED | `handle_raw` (2) | `test_18` |
| 19 | Enforcement-Wechsel → BLOCKED | `_on_run_started` | `test_19*` |
| 20 | Evaluationsexport markiert Fehler | `renderer.render` | `test_20` |
| 21 | BLOCKED gibt keinen Fachtext aus | `renderer.render` | `test_21` |
| 22 | Produktionsexport nur VERIFIED | `renderer.render` | `test_22*` |
| 23 | Migration wiederholbar und verlustfrei | `migrations` | `test_23*` |
| 24 | FK- und Integritaetspruefung bestehen | `integrity_report` | `test_24*` |
| 25 | Bestehende Suiten bleiben gruen | — | `test_legacy_suites` |
| Z1 | Kontrollvariablen vollstaendig und indiziert | Schema v2 | `test_03`, `test_context_from_env*` |
| Z2 | Metrikphasen getrennt | `phase_metrics` | `test_metrics_*` |
| Z3 | Legacy nie verifiziert | Trigger | `test_23c` |
| Z4 | Sicherung vor Migration pruefbar | `backup_database` | `test_23b` |
| Z5 | Quellenidentitaet kollisionsfrei | `source_key` | `test_source_key_*` |
| Z6 | Registrierter Beleg → VERIFIED | `evidence_registry` | `test_registry_valid_key_*` |
| Z7 | Unbekannter/fremder/kollidierender Key | Writer + Reconciler | `test_registry_*` |
| Z8 | Uebergangspfad nie VERIFIED | `_verdict` | `test_fallback_*` |
| Z9 | §8-Verbote auch im Hook-Retry | `check_repair_guards` | `test_repair_*_via_hook` |
| Z10 | Metriken im Betrieb erfasst | `rag_stop`, `record_retrieval` | `test_hook_records_phase_metrics` |

---

## 6. Testergebnisse

```
python3 -m pytest                    101 passed
  test_audit.py                       71 passed
  test_hooks.py                       28 passed
  test_legacy_suites.py                2 passed

python3 test_chunker.py               20 Pruefungen, 0 Fehler
python3 test_acceptance.py            17 Kriterien, 0 Fehler, 1 nicht pruefbar
```

Die beiden bestehenden Suiten liefern exakt dasselbe Ergebnis wie vor der
Umstellung. Kein Test benoetigt Netz-, API- oder LLM-Zugang.

---

## 7. Betrieb

```bash
export AUDIT_DB_PATH=.audit/audit_trail.db
export AUDIT_EXPERIMENT_ID=exp-2026-01  AUDIT_WORKFLOW_CONDITION=A
export AUDIT_DOMAIN=physics             AUDIT_MODEL_VERSION=claude-x
export AUDIT_OUTPUT_ENFORCEMENT=prompt  AUDIT_PROVIDER=anthropic
export AUDIT_TASK_ID=task-01            AUDIT_REPLICATE=1
export AUDIT_SEED=42                    AUDIT_BATCH_ID=pilot     # optional

python3 audit_ctl.py init            # migrieren (mit Sicherung)
python3 audit_ctl.py selftest        # Writer starten, schreiben, stoppen
python3 audit_ctl.py status
python3 audit_ctl.py verify --run <RUN_ID>
python3 audit_ctl.py recompute --run <RUN_ID>
python3 audit_ctl.py metrics --run <RUN_ID>
python3 audit_ctl.py dump-schema
```

Der Writer hat bewusst kein `start`/`stop`: Er haengt an einer
`multiprocessing.Queue` und existiert nur innerhalb der Prozessgruppe, die
ihn erzeugt. Die Hooks starten ihn je Aufruf und beenden ihn geordnet;
`<db>.writer.lock` stellt sicher, dass nie zwei Writer gleichzeitig
schreiben.

### Retrieval-Phase

Damit ein Zitat `VERIFIED` werden kann, muss die Komponente, die dem
Agenten Chunks ausliefert, sie registrieren:

```python
import audit_client
session = audit_client.open_session(agent_id, parent_session_id)
with session:
    session.record_retrieval(chunks, retrieval_run_id="rr:…")
```

`chunks` ist die Ausgabe von `chunker.chunk_units()`. Ohne diesen Aufruf
bleibt der Lauf im Uebergangsmodus und erreicht hoechstens
`PARTIALLY_VERIFIED`.

### Export

```bash
# Evaluation — Pflicht fuer Pilot und Hauptlauf
python3 audit_ctl.py export --run <RUN_ID> --mode evaluation \
        --purpose pilot --out lauf.md --sidecar lauf.json

# Produktion — nur VERIFIED, alles andere kommentarlos ausgeschlossen
python3 audit_ctl.py export --run <RUN_ID> --mode production --out final.md
```

`--purpose pilot|main|evaluation|study` verweigert den Produktionsmodus:
dort waeren `PARTIALLY_VERIFIED`, `UNVERIFIED` und `BLOCKED` nicht mehr
messbar. Die Beilage (`--sidecar`) enthaelt Status, Fehlerklasse,
Evidenzlisten und Zeichenbereiche je Claim — sie ist die maschinenlesbare
Wahrheit des Exports, nicht das Markdown.

---

## 8. Entscheidungen bei Konflikten mit dem Bestand

Jede dieser Stellen war ein Konflikt zwischen Spezifikation und
vorhandenem Code. Keine wurde stillschweigend geloest.

**K1 — Zwei Datenbanken statt einer Schema-Wahrheit.**
§4 verlangt „eine einzige eindeutige Schema-Wahrheit". `audit_trail.db`
darf nur der Writer beschreiben (§2), und in einer offenen Transaktion
darf kein Dateiparsing laufen (§2). Beides zusammen schliesst aus, das
Provenienzregister in dieselbe Datei zu legen — die Ingestion muesste
sonst durch den Writer laufen. Umsetzung: Die Schema-Wahrheit ist
`migrations.py` und deckt beide Datenbanken ab; die Dateien bleiben zwei.

**K2 — Writer je Hook-Prozess.**
§2 verlangt eine `multiprocessing.Queue` und genau einen Schreiber. Hooks
sind kurzlebige, unabhaengige Prozesse ohne gemeinsame Queue. Umsetzung:
Jeder Producer bringt seinen Writer mit; ein exklusives `flock` serialisiert
sie. Zu jedem Zeitpunkt existiert hoechstens eine schreibende Verbindung,
und ein zweiter Writer wartet, statt an SQLite zu scheitern.

**K3 — `<<<AUDIT>>>` als Kanal A.**
§5 erlaubt den Freitextblock nur noch als Prompt-Fallback. Claude Code
liefert Agentenausgaben aber ausschliesslich als Text
(`last_assistant_message`). Umsetzung: Der Adapter liest im Modus `native`
die gesamte Nachricht als JSON, im Modus `prompt` den `<<<AUDIT>>>`-Block.
Der Legacy-Pfad ist damit ein dokumentierter Modus, kein Standard.

**K4 — Evidenzfreie Claims.**
§6 laesst die Wahl zwischen eigener Kategorie und `UNVERIFIED`. Umsetzung:
beides — `evidence_free` als deklariertes Feld, Status trotzdem
`UNVERIFIED` mit `NO_REQUIRED_EVIDENCE`. Die leere Liste aus Nachlaessigkeit
bleibt so von der bewusst quellenfreien Aussage unterscheidbar, ohne dass
eine davon als belegt gilt.

**K5 — `PARTIALLY_VERIFIED` im Produktionsmodus.**
§6 verbietet den Status dort. Umsetzung: `reconcile(production=True)` stuft
ihn mit Begruendung auf `UNVERIFIED` ab; der Produktionsexport schliesst
beide aus. Der gespeicherte Evaluationsstatus bleibt unveraendert.

**K6 — `normalize_source()`.**
Die Funktion kollidiert (Basename und Endung entfernt). Sie zu aendern
wuerde historische `source_id`-Werte umdeuten (§10). Umsetzung: Sie bleibt
unveraendert und ist als Legacy markiert; neue Zeilen tragen den stabilen
`source_key`.

**K7 — Reparaturbaseline bei unparsebarer Ausgabe.**
Im haeufigsten Reparaturfall liefert `json.loads` nichts — die Verbote aus
§8 waeren gegen eine leere Referenzmenge wirkungslos. Umsetzung:
`baseline_of()` gewinnt die Baseline notfalls lexikalisch. Neue Quellen
sind dadurch immer ausgeschlossen; neue `claim_id`s nur dann, wenn die
Baseline nachweislich vollstaendig war.

---

## 9. Verbleibende Risiken

1. **Transkriptschema.** `channel_b()` sucht schema-agnostisch nach
   Dateireferenzen und DOIs. Das interne JSONL-Format ist nicht Teil des
   Hook-Kontrakts. Vor dem Produktivlauf einmal gegen ein echtes
   Transkript kalibrieren; ein nicht erkannter Zugriff fuehrt zu einem
   falsch-negativen Befund (Claim gilt als unbelegt).
2. **Konservative Quellenschluessel.** `./doc/x.pdf` und `/abs/doc/x.pdf`
   gelten als verschieden. Das meldet zu viel statt zu wenig, erzeugt aber
   Evidenzreparaturen, wo Evidenz vorliegt. Wer relative und absolute Pfade
   mischt, sollte vorher normalisieren — ausserhalb des Audits.
3. **Injektionserkennung.** Bewusst wenige, eindeutige Muster. Ein
   entschlossener Angreifer umgeht sie; sie ersetzt weder den
   Schreibschutz noch den Zwei-Kanal-Abgleich, sondern ergaenzt beide.
4. **Writer-Lock unter Last.** Bei sehr vielen gleichzeitigen Hooks
   serialisieren sich die Writer. Das ist korrekt, aber es ist eine
   Wartezeit; das Lock-Timeout (60 s) ist bei extremer Parallelitaet
   anzuheben.
5. **Token- und Kostenmetrik fehlt im Hook-Pfad.** Dauern werden aus
   persistierten Zeitstempeln gemessen (`initial_generation`,
   `format_repair`, `evidence_retrieval`, `total`). Tokens und Kosten
   bleiben `NULL`, weil der Hook-Kontrakt sie nicht liefert — geschaetzte
   Werte waeren im Ergebnisbericht von gemessenen nicht unterscheidbar.
6. **Die Retrieval-Komponente muss `record_retrieval()` aufrufen.** Die
   API existiert und ist getestet, aber sie ruft sich nicht selbst auf. Wer
   sie vergisst, bekommt keinen Fehler — sondern einen Lauf, der im
   Uebergangsmodus bleibt und nie `VERIFIED` erreicht. Der leere
   Produktionsexport ist das Signal dafuer.
7. **`agent_scoped` ist standardmaessig aus.** Evidenz gilt runweit. Wer
   agentweise getrennte Evidenzraeume braucht, setzt
   `reconcile(agent_scoped=True)` — die Pruefung ist implementiert und
   getestet, aber nicht der Standard.

## 10. Bewusst nicht umgesetzt

- **Kein dauerhafter Writer-Dienst.** Begruendung siehe K2 und §7.
- **Keine Zusammenlegung der Datenbanken.** Begruendung siehe K1.
- **Keine Zusammenlegung von Registry und `provenance.db`.** Die Registry
  liegt im Audit, weil sie Kanal B ist und append-only sein muss;
  `retrieval_run_id` verweist lediglich auf das Provenienzregister. Eine
  dateiuebergreifende Fremdschluesselbeziehung ist in SQLite nicht
  moeglich — eine nicht aufloesbare `retrieval_run_id` ist deshalb ein
  Auditbefund und kein Konsistenzfehler.
- **Keine Rueckrechnung der Altdaten** auf den neuen Quellenschluessel:
  `assertions.source_id` und `actions.source_id` aus v1.0 bleiben stehen.
  Eine Neuberechnung waere eine Umdeutung historischer Daten (§10). Alte
  Laeufe sind dadurch nicht mit dem neuen Reconciler auswertbar — sie sind
  als `legacy` / `context_incomplete` gekennzeichnet.
