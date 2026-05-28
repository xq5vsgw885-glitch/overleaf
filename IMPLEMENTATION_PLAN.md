# Implementation Plan – Pflanzenbestimmungs-App

## Grundregel

Claude Code setzt ausschließlich technisch um, was fachlich vorgegeben wurde.
Keine eigenen botanischen Merkmale, Gewichtungen, Taxa, Scoring-Regeln, Bildanalyse oder UI.

---

## Universelle Verbote (gelten für alle Phasen und Schritte)

- Keine echten Taxa oder Artenlisten ergänzen (bis Phase 3 explizit freigegeben)
- Keine Bildanalyse implementieren
- Keinen visuellen Fotoabgleich implementieren
- Keine finale sichere Artbestimmung behaupten
- `finalSpeciesIdentificationImplemented: false` bleibt in allen Schritten `false`
- `imageAnalysisImplemented: false` bleibt in allen Schritten `false`
- `realTaxaImplemented: false` bleibt `false`, solange keine produktive, breit nutzbare Taxon-Datenbasis vorliegt; einzelne später kontrollierte Seed-Einträge sind noch keine vollständige Taxon-Datenbank
- `PLANT_TAXON_SEED_DATA` bleibt leer bis Phase 3 explizit gestartet wird
- Keine UI
- Keine JavaScript-Artefakte erzeugen

## Universelle Pflichtprüfungen nach jedem Schritt

1. `tsc --strict --noEmit` erfolgreich
2. `npm test`: alle Tests bestanden (Gesamtzahl steigt oder bleibt gleich)
3. `PLANT_TAXON_SEED_DATA.length === 0` (bis Phase 3)

---

## PHASE 0 — Synchronisierung nach Germany-Consistency-Härtung

*Sofort durchzuführen. Aktueller Teststand: 178/178.*

### Step 0.1 — domainQualityReport.ts

| Feld | Inhalt |
|---|---|
| **Ziel** | `passingUnitTests` auf 178 setzen; `openNextSteps` auf Stand nach `checkTaxonSeedGermanyConsistency` aktualisieren |
| **Erlaubte Dateien** | `src/domain/plant-identification/domainQualityReport.ts` |
| **Verboten** | Alle anderen TS-Dateien, Testdateien, README.md, HANDOFF.md, Taxa, Seed-Daten, Bildanalyse |
| **Erwarteter Output** | domainQualityReport.ts mit `passingUnitTests: 178` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; `npm test` erwartet 3 Fehler in domainQualityReport.test.ts (akzeptiert in diesem Schritt) |
| **Abbruchkriterium** | `tsc` schlägt fehl |
| **Commit-Kriterium** | `tsc` erfolgreich |
| **Nächster Schritt** | Step 0.2 |

### Step 0.2 — domainQualityReport.test.ts

| Feld | Inhalt |
|---|---|
| **Ziel** | `passingUnitTests`-Erwartung auf 178; `openNextSteps`-Erwartungen auf neue Liste anpassen |
| **Erlaubte Dateien** | `src/domain/plant-identification/domainQualityReport.test.ts` |
| **Verboten** | Alle produktiven TS-Dateien, README.md, HANDOFF.md |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; `npm test` 178/178 ✓ |
| **Abbruchkriterium** | `tsc` fehlerhaft oder `npm test` < 178/178 |
| **Commit-Kriterium** | 178/178 Tests bestanden |
| **Nächster Schritt** | Step 0.3 |

### Step 0.3 — README.md synchronisieren

| Feld | Inhalt |
|---|---|
| **Ziel** | Teststand auf 178/178 aktualisieren; `checkTaxonSeedGermanyConsistency` dokumentieren; `taxonSeedPolicy.test.ts`-Testumfang auf 17 aktualisieren |
| **Erlaubte Dateien** | `src/domain/plant-identification/README.md` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; `npm test` 178/178 ✓ |
| **Abbruchkriterium** | Tests schlagen fehl |
| **Commit-Kriterium** | Tests grün |
| **Nächster Schritt** | Step 0.4 |

### Step 0.4 — HANDOFF.md synchronisieren

| Feld | Inhalt |
|---|---|
| **Ziel** | Teststand auf 178 aktualisieren; erweiterte Tests zur `checkTaxonSeedGermanyConsistency` erwähnen |
| **Erlaubte Dateien** | `HANDOFF.md` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; `npm test` 178/178 ✓ |
| **Abbruchkriterium** | Tests schlagen fehl |
| **Commit-Kriterium** | Tests grün |
| **Nächster Schritt** | Phase 1 oder fachliche Entscheidung |

---

## PHASE 1 — Morphologische Mindestbindung

*Technische Härtung: Sicherstellen, dass ein Taxon-Seed-Eintrag mindestens ein morphologisches Merkmal enthält.*

### Step 1.1 — checkTaxonSeedMorphologyPresent (taxonSeedPolicy.ts)

| Feld | Inhalt |
|---|---|
| **Ziel** | Neue Funktion: gibt `allowed` zurück wenn `taxon.morphology.length > 0`, sonst `blocked` mit `reason: "morphology_required"` |
| **Erlaubte Dateien** | `src/domain/plant-identification/taxonSeedPolicy.ts` |
| **Verboten** | Taxa, Seed-Daten, Bildanalyse, UI, alle anderen Dateien |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓ |
| **Commit-Kriterium** | `tsc` erfolgreich |
| **Nächster Schritt** | Step 1.2 |

### Step 1.2 — Integration in validateTaxonSeedEntry (taxonSeedSchema.ts)

| Feld | Inhalt |
|---|---|
| **Ziel** | `checkTaxonSeedMorphologyPresent` als 5. Check in `validateTaxonSeedEntry`; `toHaveLength(4)→5` in bestehenden Tests anpassen |
| **Erlaubte Dateien** | `src/domain/plant-identification/taxonSeedSchema.ts`, `src/domain/plant-identification/taxonSeedSchema.test.ts` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; alle Tests bestanden ✓ |
| **Commit-Kriterium** | Alle Tests grün |
| **Nächster Schritt** | Step 1.3 |

### Step 1.3 — Tests für checkTaxonSeedMorphologyPresent (taxonSeedPolicy.test.ts)

| Feld | Inhalt |
|---|---|
| **Ziel** | Neue `describe`-Gruppe: erlaubt wenn `morphology.length > 0`, blockt wenn `morphology` leer |
| **Erlaubte Dateien** | `src/domain/plant-identification/taxonSeedPolicy.test.ts` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; alle Tests bestanden ✓ |
| **Commit-Kriterium** | Alle Tests grün |
| **Nächster Schritt** | Step 1.4 |

### Step 1.4 — domainQualityReport.ts + .test.ts synchronisieren

| Feld | Inhalt |
|---|---|
| **Ziel** | `passingUnitTests` auf neuen Stand; `openNextSteps` aktualisieren |
| **Erlaubte Dateien** | `domainQualityReport.ts`, danach `domainQualityReport.test.ts` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; alle Tests bestanden ✓ |
| **Commit-Kriterium** | Alle Tests grün |
| **Nächster Schritt** | Step 1.5 |

### Step 1.5 — README.md + HANDOFF.md synchronisieren

---

## PHASE 2 — Audit-Metadaten (Review-Pflichtfelder)

*Nachvollziehbarkeit: Wer hat wann einen Seed-Eintrag ergänzt und freigegeben?*

### Step 2.1 — TaxonSeedEntry erweitern (taxonSeedSchema.ts)

| Feld | Inhalt |
|---|---|
| **Ziel** | Pflichtfelder `addedAt: string` und `reviewNote: string` zu `TaxonSeedEntry` ergänzen |
| **Erlaubte Dateien** | `src/domain/plant-identification/taxonSeedSchema.ts` |
| **Verboten** | Taxa, Seed-Daten, Bildanalyse, alle anderen TS-Dateien |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓ |
| **Nächster Schritt** | Step 2.2 |

### Step 2.2 — checkTaxonSeedReviewNote (taxonSeedPolicy.ts)

| Feld | Inhalt |
|---|---|
| **Ziel** | Funktion prüft, ob `reviewNote.trim().length > 0`; gibt `blocked: "review_note_required"` zurück wenn leer |
| **Erlaubte Dateien** | `src/domain/plant-identification/taxonSeedPolicy.ts` |
| **Nächster Schritt** | Step 2.3 |

### Step 2.3 — Integration in validateTaxonSeedEntry + Tests

### Step 2.4 — domainQualityReport, README, HANDOFF synchronisieren

---

## PHASE 3 — Erste fachlich kontrollierte Taxon-Seed-Daten

⚠ **Nur nach expliziter fachlicher Entscheidung und Freigabe.**

### Bedingungen für jeden Eintrag

- Quelle: `"Rothmaler"` oder `"Strasburger"`
- `reference` nicht leer
- `germanyRelevant: true` und `taxon.germanyRelevance.occursInGermany: true`
- Mindestens 1 morphologisches Merkmal in `taxon.morphology`
- `addedAt` gesetzt (ISO-Datum)
- `reviewNote` gesetzt (nicht leer)
- `validateTaxonSeedEntry` liefert `valid: true`
- `createdFromImageOnly: false`
- `createsFinalIdentification: false`

### Step 3.1 — Erster Eintrag in PLANT_TAXON_SEED_DATA

| Feld | Inhalt |
|---|---|
| **Ziel** | `PLANT_TAXON_SEED_DATA` erhält ersten validierten Eintrag; `PLANT_TAXON_SEED_DATA.length === 1` |
| **Erlaubte Dateien** | `src/domain/plant-identification/taxonSeedData.ts` |
| **Pflichtprüfungen** | `tsc --strict --noEmit` ✓; alle Tests ✓; `validateTaxonSeedEntry(eintrag).valid === true` ✓ |
| **Abbruchkriterium** | `validateTaxonSeedEntry` liefert `valid: false` |
| **Commit-Kriterium** | Alle Tests grün, Validierung positiv |
| **Nächster Schritt** | Weitere Einträge nach demselben Schema, schrittweise |

### Step 3.2+ — Weitere Einträge

Jeder weitere Eintrag folgt denselben Bedingungen wie Step 3.1.
Keine Batch-Ergänzungen. Jeder Eintrag wird einzeln geprüft und committed.
