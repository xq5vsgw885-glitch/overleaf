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
- npm test: 168/168 Tests bestanden
- Testdateien: 12

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

## Methodische Sicherungen

Aktuell gilt:

- keine echte Taxon-Datenbank
- keine echten Pflanzenarten
- keine Taxon-Seed-Daten
- keine Bildanalyse
- kein echter visueller Fotoabgleich
- keine finale sichere Artbestimmung

In domainQualityReport.ts müssen diese Sicherungen false bleiben:

- finalSpeciesIdentificationImplemented: false
- imageAnalysisImplemented: false
- realTaxaImplemented: false

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

Vor dem Aufbau echter Taxon-Seed-Daten muss fachlich entschieden werden:

1. Soll mit ersten fachlich kontrollierten Taxon-Seed-Daten begonnen werden?
2. Oder soll zunächst weitere technische Härtung erfolgen?

Wenn Taxon-Seed-Daten ergänzt werden, dann nur:
- quellenbasiert
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
- npm test: 168/168 Tests bestanden
