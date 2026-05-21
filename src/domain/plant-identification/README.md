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

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

## Noch nicht implementiert

- Finale Bestimmungsausgabe-Struktur
- Echte Pflanzenarten oder Taxon-Datenbank
- Taxonomische Hierarchielogik
- Visueller Fotoabgleich
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die Entwicklung einer **finalen Bestimmungsausgabe-Struktur**.

Diese Struktur soll das Ergebnis einer vollständigen Bestimmungsanfrage repräsentieren: geordnete Kandidatenliste, Konfidenz-Einschätzung, Hinweise auf fehlende Merkmale und Anforderungen für den abschließenden visuellen Kontrollschritt.

Die finale Bestimmungsausgabe-Struktur ist noch nicht implementiert.

Der visuelle Fotoabgleich bleibt weiterhin ein späterer abschließender Kontrollschritt und ist nicht implementiert.
