# Plant Identification – Morphologische Merkmalsmatrix

## Fachlicher Stand

### Bereits umgesetzt

#### Merkmalsmatrix (morphologicalFeatureMatrix.ts)

Alle 16 geplanten Merkmalsgruppen sind vollständig implementiert:

1. **Wuchsform** – wuchsform, lebensform
2. **Spross/Stängel** – sprossform, sprossoberflaeche, milchsaft
3. **Blattstellung** – blattstellung
4. **Blattform** – blattform, blattgliederung
5. **Blattrand** – blattrand
6. **Blattnervatur** – nervatur
7. **Blattoberfläche/Behaarung** – blattoberflaeche, behaarung
8. **Blüte** – bluetentyp, bluetengroesse
9. **Blütenfarbe** – bluetenfarbe
10. **Blütensymmetrie** – bluetensymmetrie
11. **Blütenstand** – bluetenstand
12. **Frucht** – fruchttyp
13. **Samen/Ausbreitung** – ausbreitungseinheit
14. **Unterirdische Organe** – unterirdisches_organ
15. **Standortkontext** – standorttyp, feuchte, licht
16. **Phänologie** – bluetezeit, fruchtzeit

Die Merkmalsmatrix ist abgeschlossen. Es gibt keine offenen Merkmalsgruppen.

#### Scoring-Modell (featureScoring.ts)

**Typen:** `ObservedFeature`, `TaxonFeatureProfile`, `FeatureComparisonResult`

**Funktionen:** `diagnosticWeightToNumber`, `compareFeature`, `compareFeatureSet`, `calculateFeatureScore`

**Fachliche Einordnung:** Hilfsmodell zur merkmalsbasierten Eingrenzung, keine abschließende Artbestimmung.

#### Taxon-Profil-Schema (taxonProfile.ts)

**Typen:** `TaxonomicRank`, `FloristicStatus`, `GermanyRelevance`, `TaxonomicIdentity`, `EcologyProfile`, `PhenologyProfile`, `VisualReferenceProfile`, `PlantTaxonProfile`

**Fachliche Einordnung:** Nur ein Schema. Keine echten Pflanzenarten, keine Artenliste, keine Bestimmungslogik.

#### Taxon-Vergleichsfunktion (taxonComparison.ts)

**Typen:** `TaxonComparisonStatus`, `TaxonComparisonResult`

**Funktionen:** `determineTaxonComparisonStatus`, `getTaxonComparisonReason`, `compareObservedFeaturesWithTaxon`

**Fachliche Einordnung:** Bewertet ausschließlich morphologische Merkmalsübereinstimmung. Ein Status `high_match` ist keine sichere Artbestimmung.

#### Plausibilitätsmodell (plausibilityScoring.ts)

**Typen:** `ObservationContext`, `PlausibilityComponent`, `PlausibilityCheckResult`, `PlausibilityStatus`, `TaxonPlausibilityResult`

**Funktionen:** `floristicStatusToWeight`, `checkGermanyRelevance`, `checkFloristicStatus`, `checkHabitat`, `checkMoisture`, `checkLight`, `checkPhenology`, `calculatePlausibilityScore`, `determinePlausibilityStatus`, `getPlausibilityReason`, `evaluateTaxonPlausibility`

**Fachliche Einordnung:** Prüft Kontext- und Verbreitungsplausibilität. Deutschland-Relevanz ist harter Anker. Ein Status `high_plausibility` ist keine sichere Artbestimmung.

#### Kombinierte Gesamtbewertung (combinedAssessment.ts)

Kombiniert morphologische Taxon-Übereinstimmung und Kontextplausibilität zu einer Gesamtbewertung.

**Typen:**
- `CombinedAssessmentStatus` – insufficient_data, unlikely_candidate, possible_candidate, probable_candidate, strong_candidate_requires_review
- `CombinedAssessmentResult` – Gesamtergebnis mit Morphologie, Plausibilität, combinedScore, Status und Begründung

**Funktionen:**
- `calculateCombinedScore` – Morphologie × 0.75 + Plausibilität × 0.25
- `determineCombinedAssessmentStatus` – leitet Status aus combinedScore, Morphologie und Plausibilität ab
- `getCombinedAssessmentReason` – liefert textuelle Begründung zum Status
- `assessTaxonCandidate` – bewertet einen einzelnen Taxon-Kandidaten
- `assessTaxonCandidates` – bewertet eine Liste von Taxa und sortiert absteigend nach combinedScore

**Gewichtung:** Morphologie 0.75 · Plausibilität 0.25. Morphologische Merkmale bleiben primär. Kontext- und Verbreitungsplausibilität stabilisieren die Bewertung, dominieren sie aber nicht.

**Fachliche Einordnung:** Die höchste Statusklasse `strong_candidate_requires_review` bedeutet ausdrücklich keine sichere Artbestimmung. Ein Kandidat ist stark unterstützt, muss aber weiterhin taxonomisch geprüft und später visuell kontrolliert werden. Es gibt keine finale Artbestimmung, keine Taxon-Datenbank, keine Bildanalyse und keinen visuellen Fotoabgleich in dieser Datei.

#### Finale Bestimmungsausgabe-Struktur (identificationResult.ts)

Strukturiert die Ausgabe der merkmalsbasierten Pipeline vor dem visuellen Kontrollschritt. Trennt die Begründung methodisch in Beobachtung, Berechnung, Interpretation und Unsicherheit.

**Typen:**
- `IdentificationConfidence` – insufficient, low, moderate, high_but_not_final
- `IdentificationOutputRank` – familie, gattung, art, nicht_bestimmbar
- `EvidenceSection` – Felder: observations, calculations, interpretation, uncertainty
- `MissingEvidenceHint` – featureId, message, recommendedPhotoType?
- `IdentificationCandidate` – taxon, assessment, confidence, outputRank, evidence, missingEvidence
- `IdentificationResult` – primaryCandidate?, alternativeCandidates, resultSummary, isFinalSpeciesIdentification, visualControlPending

**Funktionen:**
- `confidenceFromCombinedStatus` – mappt CombinedAssessmentStatus auf IdentificationConfidence
- `outputRankFromTaxonRank` – mappt TaxonomicRank auf IdentificationOutputRank
- `buildEvidenceSection` – erzeugt EvidenceSection aus CombinedAssessmentResult
- `buildMissingEvidenceHints` – liefert Hinweise auf fehlende Merkmale
- `buildIdentificationCandidate` – erzeugt IdentificationCandidate aus CombinedAssessmentResult
- `buildIdentificationResult` – erzeugt sortierte IdentificationResult aus Kandidatenliste

**Fachliche Einordnung:**

`isFinalSpeciesIdentification` ist immer `false`. Dieser Wert kann nie `true` sein.

`visualControlPending` ist immer `true`, weil der visuelle Fotoabgleich noch nicht durchgeführt wurde.

Ein `outputRank` „art" bedeutet ausschließlich, dass ein Kandidatenprofil auf Art-Rang liegt. Es bedeutet nicht, dass die Art sicher bestimmt wurde.

Die Datei erzeugt keine finale sichere Artbestimmung. Die Datei führt keinen visuellen Fotoabgleich durch. Die Datei führt keine Bildanalyse durch. Die Datei enthält keine echten Pflanzenarten und keine Taxon-Datenbank.

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

#### Visuelles Kontrollschritt-Schema (visualControl.ts)

Definiert ausschließlich die Struktur des späteren visuellen Kontrollschritts. Die Datei implementiert keine Bildanalyse, berechnet keine Bildähnlichkeit und enthält keine Referenzbilder, keine echten Pflanzenarten und keine Taxon-Datenbank.

**Typen:**
- `VisualControlPhotoType` – habitus, blatt, bluete, frucht, detail, standort
- `VisualControlInput` – photoType, imageUri, quality, notes?
- `VisualControlReference` – taxon, referenceImageUris, photoTypes
- `VisualControlStatus` – not_performed, insufficient_visual_material, visual_support, visual_conflict, visual_review_required
- `VisualControlResult` – status, checkedPhotoTypes, reason, supportsCurrentIdentification, requiresHumanReview
- `IdentificationResultWithVisualControl` – identification, visualControl

**Funktionen:**
- `createNotPerformedVisualControlResult` – erzeugt Ergebnis für nicht durchgeführten Kontrollschritt
- `createInsufficientVisualMaterialResult` – erzeugt Ergebnis bei unzureichendem Bildmaterial
- `createVisualSupportResult` – erzeugt Ergebnis bei visueller Übereinstimmung
- `createVisualConflictResult` – erzeugt Ergebnis bei visuellem Widerspruch
- `attachVisualControlResult` – kombiniert IdentificationResult mit VisualControlResult

**Fachliche Einordnung:**

Der visuelle Kontrollschritt darf eine merkmalsbasierte Bestimmung nur stützen, abschwächen oder zur menschlichen Nachprüfung markieren. Der visuelle Kontrollschritt darf niemals allein eine Bestimmung erzeugen.

Eine sichere Artbestimmung darf nur entstehen, wenn morphologische Konsistenz, taxonomische Plausibilität, Deutschland-/Status-/Standortprüfung und visueller Kontrollschritt konsistent sind.

#### Pipeline-Klammerung (identificationPipeline.ts)

Verbindet die bestehenden Bausteine zu einer ersten merkmalsbasierten Pipeline.

**Typen:**
- `IdentificationPipelineInput` – observedFeatures, observationContext, candidateTaxa
- `IdentificationPipelineResult` – assessments, identification, identificationWithVisualControl

**Funktion:**
- `runIdentificationPipeline` – führt kombinierte Bewertung, Ausgabestrukturierung und visuellen Kontrollstatus in einem Aufruf zusammen

**Fachliche Einordnung:**

Die Pipeline arbeitet ausschließlich mit übergebenen `candidateTaxa`. Es werden keine echten Pflanzenarten oder Taxon-Datenbanken angelegt. Die Pipeline implementiert keine Bildanalyse und keinen echten visuellen Fotoabgleich.

Der visuelle Kontrollstatus ist aktuell immer `not_performed`: Der Kontrollschritt ist strukturell vorgesehen, aber noch nicht durchgeführt.

Wenn `candidateTaxa` leer ist, läuft die Pipeline typkonform und erzeugt eine `IdentificationResult` ohne `primaryCandidate`.

Die Pipeline erzeugt keine finale sichere Artbestimmung. Eine sichere Artbestimmung darf nur entstehen, wenn morphologische Konsistenz, taxonomische Plausibilität, Deutschland-/Status-/Standortprüfung und visueller Kontrollschritt konsistent sind.

### Test-Infrastruktur

**Test-Framework:** Vitest (`vitest run`)

**Test-Script in package.json:** `"test": "vitest run"`

#### Unit-Tests featureScoring.ts (featureScoring.test.ts)

Testet alle vier Kernfunktionen aus `featureScoring.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert.

**Getestete Funktionen:** `diagnosticWeightToNumber`, `compareFeature`, `compareFeatureSet`, `calculateFeatureScore`

**Testumfang (13 Tests, alle bestanden):**
1. Gewichtung niedrig → 1
2. Gewichtung mittel → 2
3. Gewichtung hoch → 3
4. Gewichtung sehr_hoch → 4
5. `compareFeature` mit passendem Wert → matched, score, reason
6. `compareFeature` mit nicht passendem Wert → value_mismatch
7. `compareFeature` mit nicht sichtbarem Merkmal → feature_not_visible
8. `compareFeature` mit unbekanntem Merkmal → unknown_feature
9. `compareFeatureSet` mit zwei passenden Merkmalen → 2 Ergebnisse, alle matched
10. `compareFeatureSet` ignoriert fehlendes beobachtetes Merkmal
11. `calculateFeatureScore` mit normalen Werten → 0.5
12. `calculateFeatureScore` mit leerer Liste → 0
13. `calculateFeatureScore` mit maxScore-Summe 0 → 0

#### Unit-Tests taxonComparison.ts (taxonComparison.test.ts)

Testet alle drei Funktionen aus `taxonComparison.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert. Die Testdaten sind ausschließlich künstliche Testtaxa (`"Test taxon"`, `"Testaceae"`, `"Testgenus"`, `"test-taxon-1"`). Es wurden keine echten Pflanzenarten oder Taxa ergänzt.

**Getestete Funktionen:** `determineTaxonComparisonStatus`, `getTaxonComparisonReason`, `compareObservedFeaturesWithTaxon`

**Testumfang (13 Tests, alle bestanden):**
1. `determineTaxonComparisonStatus` → no_observable_features bei leerer Ergebnisliste
2. `determineTaxonComparisonStatus` → low_match bei score 0.39
3. `determineTaxonComparisonStatus` → moderate_match bei score 0.4
4. `determineTaxonComparisonStatus` → moderate_match bei score 0.74
5. `determineTaxonComparisonStatus` → high_match bei score 0.75
6. `determineTaxonComparisonStatus` → high_match bei score 1
7. `getTaxonComparisonReason` → no_observable_features
8. `getTaxonComparisonReason` → low_morphological_match
9. `getTaxonComparisonReason` → moderate_morphological_match
10. `getTaxonComparisonReason` → high_morphological_match
11. `compareObservedFeaturesWithTaxon` mit zwei passenden Merkmalen → high_match, score 1
12. `compareObservedFeaturesWithTaxon` mit einem passenden und einem nicht passenden Merkmal → high_match, score 0.75
13. `compareObservedFeaturesWithTaxon` ohne beobachtete Merkmale → no_observable_features

#### Unit-Tests plausibilityScoring.ts (plausibilityScoring.test.ts)

Testet alle elf Funktionen aus `plausibilityScoring.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert. Die Testdaten sind ausschließlich künstliche Testtaxa (`"Test taxon"`, `"Testaceae"`, `"Testgenus"`, `"test-taxon-1"`). Es wurden keine echten Pflanzenarten oder Taxa ergänzt.

**Getestete Funktionen:** `floristicStatusToWeight`, `checkGermanyRelevance`, `checkFloristicStatus`, `checkHabitat`, `checkMoisture`, `checkLight`, `checkPhenology`, `calculatePlausibilityScore`, `determinePlausibilityStatus`, `getPlausibilityReason`, `evaluateTaxonPlausibility`

**Testumfang (36 Tests, alle bestanden):**
- `floristicStatusToWeight` – alle vier Statusklassen
- `checkGermanyRelevance` – mit und ohne Deutschland-Vorkommen
- `checkFloristicStatus` – wildwachsend und kulturpflanze_nachrangig
- `checkHabitat` – passend, nicht passend, nicht angegeben
- `checkMoisture` – passend, nicht passend, nicht angegeben
- `checkLight` – passend, nicht passend, nicht angegeben
- `checkPhenology` – Blütezeit passend, Fruchtzeit passend, nicht passend, nicht angegeben
- `calculatePlausibilityScore` – normale Werte (→ 0.75), leere Liste (→ 0), maxScore-Summe 0 (→ 0)
- `determinePlausibilityStatus` – not_plausible bei fehlender Deutschland-Relevanz, alle Schwellenwerte
- `getPlausibilityReason` – alle vier Reason-Codes
- `evaluateTaxonPlausibility` – vollständig passender Kontext (→ high_plausibility, score 1), Taxon nicht in Deutschland (→ not_plausible)

#### Unit-Tests combinedAssessment.ts (combinedAssessment.test.ts)

Testet alle fünf Funktionen aus `combinedAssessment.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert. Die Testdaten sind ausschließlich künstliche Testtaxa (`"Test taxon"`, `"Testaceae"`, `"Test taxon 2"`, `"Testaceae2"`, `"test-taxon-1"`, `"test-taxon-2"`). Es wurden keine echten Pflanzenarten oder Taxa ergänzt.

**Getestete Funktionen:** `calculateCombinedScore`, `determineCombinedAssessmentStatus`, `getCombinedAssessmentReason`, `assessTaxonCandidate`, `assessTaxonCandidates`

**Testumfang (23 Tests, alle bestanden):**
- `calculateCombinedScore` – Gewichtung Morphologie 0.75 · Plausibilität 0.25 für vier Eingabekombinationen
- `determineCombinedAssessmentStatus` – insufficient_data bei leeren featureResults, unlikely_candidate bei not_plausible, alle Score-Schwellen (0.39/0.4/0.69/0.7/0.84/0.85/1)
- `getCombinedAssessmentReason` – alle fünf Reason-Codes
- `assessTaxonCandidate` – vollständig passendes Taxon (→ strong_candidate_requires_review, score 1), fehlende Merkmale (→ insufficient_data), Taxon nicht in Deutschland (→ unlikely_candidate)
- `assessTaxonCandidates` – Sortierung absteigend nach combinedScore, leere Taxonliste

#### Unit-Tests identificationResult.ts (identificationResult.test.ts)

Testet alle sechs Funktionen aus `identificationResult.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert. Die Testdaten sind ausschließlich künstliche Testtaxa (`"Test taxon"`, `"Testaceae"`, `"Testgenus"`, `"test-taxon-1"` bis `"test-taxon-6"`). Es wurden keine echten Pflanzenarten oder Taxa ergänzt.

**Getestete Funktionen:** `confidenceFromCombinedStatus`, `outputRankFromTaxonRank`, `buildEvidenceSection`, `buildMissingEvidenceHints`, `buildIdentificationCandidate`, `buildIdentificationResult`

**Testumfang (18 Tests, alle bestanden):**
- `confidenceFromCombinedStatus` – alle fünf CombinedAssessmentStatus-Werte
- `outputRankFromTaxonRank` – familie, gattung, art
- `buildEvidenceSection` – methodische Trennung: observations, calculations mit Scores, interpretation mit Reasons, uncertainty mit allen drei Hinweisen
- `buildMissingEvidenceHints` – leeres Array bei vorhandenen featureResults, ein Hinweis bei leeren featureResults (featureId: "unknown", recommendedPhotoType: "habitus")
- `buildIdentificationCandidate` – confidence, outputRank, uncertainty, missingEvidence
- `buildIdentificationResult` – leeres Array (→ no_candidates_available), starker Kandidat (→ strong_candidate_requires_review), moderater Kandidat (→ candidate_plausible_but_not_final), schwacher Kandidat (→ weak_candidate), insufficient (→ insufficient_data), Begrenzung alternativeCandidates auf 4

**Methodische Prüfbestätigung:** Alle `buildIdentificationResult`-Tests prüfen explizit `isFinalSpeciesIdentification === false` und `visualControlPending === true`.

#### Unit-Tests visualControl.ts (visualControl.test.ts)

Testet alle fünf Funktionen aus `visualControl.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert. Die Testdaten enthalten keine echten Pflanzenarten oder Taxa. Es wurde keine Bildanalyse und keine Bildähnlichkeit implementiert.

**Getestete Funktionen:** `createNotPerformedVisualControlResult`, `createInsufficientVisualMaterialResult`, `createVisualSupportResult`, `createVisualConflictResult`, `attachVisualControlResult`

**Testumfang (6 Tests, alle bestanden):**
- `createNotPerformedVisualControlResult` – status, leere checkedPhotoTypes, kein Support, keine Review-Pflicht
- `createInsufficientVisualMaterialResult` – status, checkedPhotoTypes, Review-Pflicht
- `createVisualSupportResult` – status, checkedPhotoTypes, Support ohne Review-Pflicht
- `createVisualConflictResult` – status, checkedPhotoTypes, Review-Pflicht
- `attachVisualControlResult` – verbindet IdentificationResult und VisualControlResult korrekt
- Methodische Sicherung: auch bei visual_support bleibt `isFinalSpeciesIdentification === false`

#### Unit-Tests identificationPipeline.ts (identificationPipeline.test.ts)

Testet `runIdentificationPipeline` aus `identificationPipeline.ts`. Die produktive Domänenlogik wurde durch diesen Testschritt nicht verändert. Die Testdaten sind ausschließlich künstliche Testtaxa (`"Test taxon"`, `"Testaceae"`, `"Testgenus"`, `"Test taxon 2"`, `"Testaceae2"`, `"test-taxon-1"`, `"test-taxon-2"`). Es wurden keine echten Pflanzenarten oder Taxa ergänzt. Es wurde kein echter visueller Fotoabgleich implementiert.

**Getestete Funktion:** `runIdentificationPipeline`

**Testumfang (5 Tests, alle bestanden):**
1. Leere candidateTaxa-Liste → no_candidates_available, kein primaryCandidate
2. Vollständig passendes Taxon → strong_candidate_requires_review, confidence high_but_not_final, score 1
3. Zwei Taxa → Sortierung absteigend nach combinedScore, primaryCandidate = test-taxon-1, 1 alternativeCandidate
4. Taxon nicht in Deutschland → plausibility not_plausible, status unlikely_candidate, confidence low
5. Kandidat ohne beobachtete Merkmale → insufficient_data, confidence insufficient

**Methodische Sicherungen in allen Tests:**
- `isFinalSpeciesIdentification === false` – die Pipeline erzeugt keine finale Artbestimmung
- `visualControl.status === "not_performed"` – kein echter visueller Fotoabgleich
- `visualControlPending === true` – visueller Kontrollschritt steht noch aus

**Testabdeckung der Domänenpipeline vollständig:**
`featureScoring` · `taxonComparison` · `plausibilityScoring` · `combinedAssessment` · `identificationResult` · `visualControl` · `identificationPipeline`

**Gesamtstand Unit-Tests: 114/114 bestanden (7 Testdateien)**

#### Architektur- und Qualitätsstatus (domainQualityReport.ts)

Enthält ausschließlich einen maschinenlesbaren Architektur- und Qualitätsstatus. Keine neue Bestimmungslogik, keine echten Taxa, keine Bildanalyse, kein visueller Fotoabgleich.

**Typen:**
- `DomainModuleStatus` – moduleName, purpose, implemented, hasUnitTests, createsFinalIdentification, performsImageAnalysis, usesRealTaxa
- `DomainQualityReport` – domain, scope, primaryMethod, visualControlRole, finalSpeciesIdentificationImplemented, imageAnalysisImplemented, realTaxaImplemented, testFramework, passingUnitTests, modules, openNextSteps

**Konstante:** `PLANT_IDENTIFICATION_DOMAIN_QUALITY_REPORT`

**Inhalt des Reports:**
- 9 Domänenmodule mit Implementierungs- und Teststatus
- 114 bestandene Unit-Tests dokumentiert
- `finalSpeciesIdentificationImplemented: false`
- `imageAnalysisImplemented: false`
- `realTaxaImplemented: false`
- Kein Modul erzeugt eine finale sichere Artbestimmung
- Kein Modul führt Bildanalyse aus
- Kein Modul verwendet echte Taxa

#### Unit-Tests domainQualityReport.ts (domainQualityReport.test.ts)

Testet `PLANT_IDENTIFICATION_DOMAIN_QUALITY_REPORT` aus `domainQualityReport.ts`. Keine echten Taxa, keine Bildanalyse, keine neue Bestimmungslogik.

**Testumfang (10 Tests, alle bestanden):**
1. Grundstatus – domain, scope, primaryMethod, visualControlRole, testFramework, passingUnitTests
2. Methodische Sicherungen – `finalSpeciesIdentificationImplemented === false`, `imageAnalysisImplemented === false`, `realTaxaImplemented === false`
3. 9 Domänenmodule vorhanden
4. Alle Module `implemented === true`
5. Kein Modul `createsFinalIdentification === true`
6. Kein Modul `performsImageAnalysis === true`
7. Kein Modul `usesRealTaxa === true`
8. Teststatus: morphologicalFeatureMatrix und taxonProfile `hasUnitTests: false`, alle übrigen `hasUnitTests: true`
9. Alle 9 erwarteten Modulnamen vorhanden
10. Alle 5 offenen nächsten Schritte vorhanden

**Testabdeckung der Domäne vollständig für:**
`featureScoring` · `taxonComparison` · `plausibilityScoring` · `combinedAssessment` · `identificationResult` · `visualControl` · `identificationPipeline` · `domainQualityReport`

**Noch nicht testabgedeckt:** `morphologicalFeatureMatrix`, `taxonProfile`

**Gesamtstand Unit-Tests: 124/124 bestanden (8 Testdateien)**

#### Unit-Tests morphologicalFeatureMatrix.ts (morphologicalFeatureMatrix.test.ts)

Testet `MORPHOLOGICAL_FEATURE_MATRIX`, `getFeaturesByGroup`, `getFeatureById` und `getHighDiagnosticFeatures` aus `morphologicalFeatureMatrix.ts`. Die produktive Domänenlogik und die Merkmalsmatrix wurden durch diesen Testschritt nicht verändert. Es wurden keine echten Pflanzenarten oder Taxa ergänzt. Es wurde keine Bildanalyse implementiert.

**Getestete Exporte:** `MORPHOLOGICAL_FEATURE_MATRIX`, `getFeaturesByGroup`, `getFeatureById`, `getHighDiagnosticFeatures`

**Testumfang (11 Tests, alle bestanden):**
1. Alle 16 geplanten Merkmalsgruppen sind in der Matrix vorhanden
2. Alle zentralen Feature-IDs sind vorhanden (25 IDs geprüft)
3. Jede Feature-ID ist eindeutig (keine Duplikate)
4. Jedes Feature besitzt alle Pflichtfelder: id, group, name, possibleValues, diagnosticWeight, photoVisibility, requiredPhotoTypes, userExplanation
5. Keine possibleValues-Einträge sind leer
6. `getFeaturesByGroup("Standortkontext")` liefert exakt 3 Features: standorttyp, feuchte, licht
7. `getFeaturesByGroup` liefert für unbekannte Gruppen ein leeres Array
8. `getFeatureById("blattstellung")` findet das Feature und gibt korrekte Felder zurück
9. `getFeatureById` liefert für unbekannte IDs `undefined`
10. `getHighDiagnosticFeatures` liefert ausschließlich Merkmale mit `diagnosticWeight === "hoch"` (alle zurückgegebenen Werte sind in der erlaubten Menge `["hoch", "sehr_hoch"]`)
11. `getHighDiagnosticFeatures` enthält die zentralen stark diagnostischen Merkmale: blattstellung, bluetentyp, bluetenstand, unterirdisches_organ

**Befund zu bluetensymmetrie:**

Beim Testen wurde festgestellt, dass `bluetensymmetrie` in der aktuellen Merkmalsmatrix nicht mit `"hoch"` oder `"sehr_hoch"` gewichtet ist und daher nicht von `getHighDiagnosticFeatures()` zurückgegeben wird. Die Implementierung von `getHighDiagnosticFeatures()` filtert ausschließlich nach `diagnosticWeight === "hoch"`. Die Tests folgen dem Ist-Zustand der Matrix. Es wurde keine fachliche Umgewichtung vorgenommen. Die Matrix selbst wurde nicht verändert.

Tatsächlich von `getHighDiagnosticFeatures()` zurückgegebene IDs: `blattstellung`, `bluetentyp`, `bluetenstand`, `unterirdisches_organ`.

**Testabdeckung der Domäne vollständig für:**
`morphologicalFeatureMatrix` · `featureScoring` · `taxonComparison` · `plausibilityScoring` · `combinedAssessment` · `identificationResult` · `visualControl` · `identificationPipeline` · `domainQualityReport`

**Noch nicht testabgedeckt:** `taxonProfile`

**Gesamtstand Unit-Tests: 135/135 bestanden (9 Testdateien)**

## Noch nicht implementiert

- Echte Bildanalyse
- Bildähnlichkeitsberechnung
- Referenzbild-Datenbank
- Echte Pflanzenarten oder Taxon-Datenbank
- Finale sichere Artbestimmung
- Unit-Tests für taxonProfile.ts
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Entwicklungsschritt ist die Ergänzung von Unit-Tests für `taxonProfile.ts`.
