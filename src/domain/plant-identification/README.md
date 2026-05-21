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

## Noch nicht implementiert

- Echte Bildanalyse
- Bildähnlichkeitsberechnung
- Referenzbild-Datenbank
- Echte Pflanzenarten oder Taxon-Datenbank
- Finale sichere Artbestimmung
- Unit-Tests
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die **Qualitätssicherung der Domänenlogik durch Unit-Tests**.

Unit-Tests sollen die Kernfunktionen der Pipeline prüfen: Scoring-Modell, Taxon-Vergleich, Plausibilitätsbewertung, kombinierte Bewertung und Bestimmungsausgabe.

Unit-Tests sind noch nicht implementiert.
