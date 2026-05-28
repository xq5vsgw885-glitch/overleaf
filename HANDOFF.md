# HANDOFF – Pflanzenbestimmungslogik

## Zweck

Diese Datei ist die zentrale Übergabedatei zwischen fachlicher Planung und technischer Umsetzung.

Claude Code darf diese Datei lesen, um den aktuellen Projektstand zu verstehen.
Claude Code darf daraus aber keine eigenen botanischen Entscheidungen ableiten.

## Grundregel

Claude Code setzt ausschließlich technisch um, was fachlich vorgegeben wurde.

Claude Code ergänzt keine eigenen:
- botanischen Merkmale
- Gewichtungen
- Taxa
- Artenlisten
- Scoring-Regeln
- Bildanalyse
- UI-Elemente

## Fachlicher Rahmen

Die App ist eine Pflanzenbestimmungs-App für Deutschland.

Die Bestimmung erfolgt primär:
- merkmalsbasiert
- taxonomisch
- plausibilitätsgeprüft für Deutschland

Der visuelle Fotoabgleich ist nur ein späterer Kontrollschritt.
Er darf niemals allein eine Bestimmung erzeugen.

Eine sichere finale Artbestimmung ist aktuell nicht implementiert.

## Aktueller technischer Stand

- TypeScript strict check: erfolgreich
- Testframework: Vitest
- npm test: 190/190 Tests bestanden

## Aktuelle Domänenmodule

Die Domänenlogik liegt unter:

src/domain/plant-identification/

Aktuelle Module:

1. morphologicalFeatureMatrix.ts
2. featureScoring.ts
3. taxonProfile.ts
4. taxonComparison.ts
5. plausibilityScoring.ts
6. combinedAssessment.ts
7. identificationResult.ts
8. visualControl.ts
9. identificationPipeline.ts
10. domainQualityReport.ts
11. taxonSeedPolicy.ts
12. taxonSeedSchema.ts
13. taxonSeedData.ts

## Aktuelle Testdateien

1. morphologicalFeatureMatrix.test.ts
2. featureScoring.test.ts
3. taxonProfile.test.ts
4. taxonComparison.test.ts
5. plausibilityScoring.test.ts
6. combinedAssessment.test.ts
7. identificationResult.test.ts
8. visualControl.test.ts
9. identificationPipeline.test.ts
10. domainQualityReport.test.ts
11. taxonSeedPolicy.test.ts
12. taxonSeedSchema.test.ts
13. taxonSeedData.test.ts

## Methodische Sicherungen

Aktuell gilt:

- keine echte Taxon-Datenbank
- keine echten Pflanzenarten
- keine Taxon-Seed-Daten (PLANT_TAXON_SEED_DATA bleibt [])
- keine Bildanalyse
- kein echter visueller Fotoabgleich
- keine finale sichere Artbestimmung

In domainQualityReport.ts müssen diese Sicherungen false bleiben:

- finalSpeciesIdentificationImplemented: false
- imageAnalysisImplemented: false
- realTaxaImplemented: false

## Synchronisierungsstand (nach Phase 2.5)

Folgende Dateien sind nach addedAt-Härtung vollständig synchronisiert:

- domainQualityReport.ts: passingUnitTests: 190, 13 Module, alle hasUnitTests: true
- domainQualityReport.test.ts: passingUnitTests === 190, openNextSteps synchronisiert
- README.md: 190/190 Tests dokumentiert, Phase 2.5 (checkTaxonSeedAddedAt) vollständig dokumentiert

Technische Härtung Phase 0 – checkTaxonSeedGermanyConsistency:
- taxonSeedPolicy.ts: checkTaxonSeedGermanyConsistency als 4. Policy-Check (blocked wenn germanyRelevant und taxon.germanyRelevance.occursInGermany nicht übereinstimmen)
- taxonSeedSchema.ts: validateTaxonSeedEntry führte nach Phase 0 vier Checks durch

Technische Härtung Phase 1 – morphologische Mindestbindung:
- taxonSeedPolicy.ts: checkTaxonSeedMorphologyPresent als 5. Policy-Check ergänzt (blocked: morphology_required wenn taxon.morphology leer)
- taxonSeedSchema.ts: validateTaxonSeedEntry führte nach Phase 1 fünf Checks durch
- taxonSeedPolicy.test.ts: 20 Tests nach Phase 1
- taxonSeedSchema.test.ts: 12 Tests nach Phase 1

Technische Härtung Phase 2 – Audit-Metadaten (addedAt, reviewNote):
- taxonSeedSchema.ts: TaxonSeedEntry um addedAt: string und reviewNote: string erweitert
- taxonSeedPolicy.ts: checkTaxonSeedReviewNote als 6. Policy-Check ergänzt (blocked: review_note_required wenn reviewNote leer oder whitespace)
- taxonSeedSchema.ts: validateTaxonSeedEntry führte nach Phase 2 sechs Checks durch
- taxonSeedPolicy.test.ts: 23 Tests nach Phase 2
- taxonSeedSchema.test.ts: 13 Tests nach Phase 2

Technische Härtung Phase 2.5 – addedAt-Pflichtprüfung:
- taxonSeedPolicy.ts: checkTaxonSeedAddedAt als 7. Policy-Check ergänzt (blocked: addedAt_required wenn addedAt leer oder whitespace)
- taxonSeedSchema.ts: validateTaxonSeedEntry führt jetzt sieben Checks durch
- taxonSeedPolicy.test.ts: 26 Tests (3 neue Tests für checkTaxonSeedAddedAt)
- taxonSeedSchema.test.ts: 14 Tests (1 neuer Test für addedAt_required, toHaveLength(6)→7)

## Taxon-Seed-Regeln

Spätere Taxon-Seed-Daten dürfen nur ergänzt werden, wenn sie:

- nach taxonSeedPolicy.ts zulässig sind
- nach taxonSeedSchema.ts strukturiert sind
- eine zugelassene Quelle besitzen
- eine Quellenangabe besitzen
- Deutschland-Relevanz besitzen
- mindestens ein morphologisches Merkmal in taxon.morphology besitzen
- ein nicht-leeres addedAt-Datum besitzen
- eine nicht-leere reviewNote besitzen
- nicht rein bildbasiert begründet sind
- keine finale sichere Artbestimmung allein erzeugen

Zugelassene Quellen sind aktuell nur:

- Rothmaler
- Strasburger

## Aktueller nächster fachlicher Entscheidungspunkt

Phase 2.5 (addedAt-Härtung) ist abgeschlossen.
190/190 Tests bestanden. Alle Synchronisierungsdateien aktuell.

Vor dem Aufbau echter Taxon-Seed-Daten muss fachlich entschieden werden:

1. Soll direkt mit ersten fachlich kontrollierten Taxon-Seed-Daten (Phase 3) begonnen werden?
2. Oder soll zunächst weitere technische Härtung erfolgen?

Wenn Taxon-Seed-Daten ergänzt werden, dann nur:
- quellenbasiert (Rothmaler oder Strasburger)
- schrittweise
- nach expliziter fachlicher Vorgabe
- ohne eigene botanische Interpretation durch Claude Code

## Arbeitsregel für jeden nächsten Schritt

Vor jeder Änderung:

1. relevante Datei lesen
2. nur die explizit genannte Datei ändern
3. keine fachlichen Ergänzungen vornehmen
4. tsc --strict --noEmit ausführen
5. npm test ausführen
6. kurzes Umsetzungsprotokoll ausgeben

Erwartung nach Umsetzung:

- tsc --strict --noEmit erfolgreich
- npm test: 190/190 Tests bestanden
- Testdateien: 13
