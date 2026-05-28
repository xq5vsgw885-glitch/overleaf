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
- npm test: 178/178 Tests bestanden
- Testdateien: 13

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

## Synchronisierungsstand (nach Phase 0)

Folgende Dateien sind nach checkTaxonSeedGermanyConsistency-Härtung vollständig synchronisiert:

- domainQualityReport.ts: passingUnitTests: 178, 12 Module, alle hasUnitTests: true
- domainQualityReport.test.ts: passingUnitTests === 178, 12 Module geprüft
- README.md: 178/178 Tests dokumentiert, checkTaxonSeedGermanyConsistency vollständig dokumentiert

Technische Härtung checkTaxonSeedGermanyConsistency:
- taxonSeedPolicy.ts: checkTaxonSeedGermanyConsistency als 4. Policy-Check (blocked wenn germanyRelevant und taxon.germanyRelevance.occursInGermany nicht übereinstimmen)
- taxonSeedSchema.ts: validateTaxonSeedEntry führt jetzt 4 Checks durch (war: 3)
- taxonSeedPolicy.test.ts: 17 Tests (4 neue Tests für checkTaxonSeedGermanyConsistency)
- taxonSeedSchema.test.ts: 11 Tests (1 neuer Test für germany_relevance_inconsistent)

## Taxon-Seed-Regeln

Spätere Taxon-Seed-Daten dürfen nur ergänzt werden, wenn sie:

- nach taxonSeedPolicy.ts zulässig sind
- nach taxonSeedSchema.ts strukturiert sind
- eine zugelassene Quelle besitzen
- eine Quellenangabe besitzen
- Deutschland-Relevanz besitzen
- nicht rein bildbasiert begründet sind
- keine finale sichere Artbestimmung allein erzeugen

Zugelassene Quellen sind aktuell nur:

- Rothmaler
- Strasburger

## Aktueller nächster fachlicher Entscheidungspunkt

Phase 0 (Synchronisierung nach checkTaxonSeedGermanyConsistency) ist abgeschlossen.
178/178 Tests bestanden. Alle Synchronisierungsdateien aktuell.

Vor dem Aufbau echter Taxon-Seed-Daten muss fachlich entschieden werden:

1. Soll mit Phase 1 (morphologische Mindestbindung) begonnen werden?
2. Oder soll direkt mit ersten fachlich kontrollierten Taxon-Seed-Daten (Phase 3) begonnen werden?

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
- npm test: 178/178 Tests bestanden
