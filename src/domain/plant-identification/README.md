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

Ein erstes generisches Scoring-/Vergleichsmodell ist implementiert.

**Typen:** `ObservedFeature`, `TaxonFeatureProfile`, `FeatureComparisonResult`

**Funktionen:** `diagnosticWeightToNumber`, `compareFeature`, `compareFeatureSet`, `calculateFeatureScore`

**Fachliche Einordnung:** Hilfsmodell zur merkmalsbasierten Eingrenzung, keine abschließende Artbestimmung.

#### Taxon-Profil-Schema (taxonProfile.ts)

Ein Schema für spätere Familien-, Gattungs- und Artprofile ist definiert.

**Typen:** `TaxonomicRank`, `FloristicStatus`, `GermanyRelevance`, `TaxonomicIdentity`, `EcologyProfile`, `PhenologyProfile`, `VisualReferenceProfile`, `PlantTaxonProfile`

**Fachliche Einordnung:** Nur ein Schema. Keine echten Pflanzenarten, keine Artenliste, keine Bestimmungslogik.

#### Taxon-Vergleichsfunktion (taxonComparison.ts)

**Typen:** `TaxonComparisonStatus`, `TaxonComparisonResult`

**Funktionen:** `determineTaxonComparisonStatus`, `getTaxonComparisonReason`, `compareObservedFeaturesWithTaxon`

**Fachliche Einordnung:** Bewertet ausschließlich morphologische Merkmalsübereinstimmung. Ein Status `high_match` bedeutet keine sichere Artbestimmung.

#### Plausibilitätsmodell (plausibilityScoring.ts)

Ein erstes Deutschland-/Status-/Standort-/Phänologie-Plausibilitätsmodell ist implementiert.

**Typen:**
- `ObservationContext` – Beobachtungskontext mit optionalen Standort-, Feuchte-, Licht- und Monatsangaben
- `PlausibilityComponent` – germany_relevance, floristic_status, habitat, moisture, light, phenology
- `PlausibilityCheckResult` – Ergebnis einer einzelnen Plausibilitätsprüfung
- `PlausibilityStatus` – not_plausible, low_plausibility, moderate_plausibility, high_plausibility
- `TaxonPlausibilityResult` – Gesamtergebnis der Plausibilitätsbewertung

**Funktionen:**
- `floristicStatusToWeight` – übersetzt FloristicStatus in einen numerischen Gewichtungsfaktor
- `checkGermanyRelevance` – prüft, ob ein Taxon für Deutschland relevant ist
- `checkFloristicStatus` – gewichtet nach floristischem Status
- `checkHabitat` – prüft Standorttyp-Übereinstimmung
- `checkMoisture` – prüft Feuchte-Übereinstimmung
- `checkLight` – prüft Licht-Übereinstimmung
- `checkPhenology` – prüft phänologische Plausibilität
- `calculatePlausibilityScore` – berechnet Gesamtplausibilität zwischen 0 und 1
- `determinePlausibilityStatus` – leitet Status ab; not_plausible wenn Taxon nicht in Deutschland vorkommt
- `getPlausibilityReason` – liefert textuelle Begründung zum Status
- `evaluateTaxonPlausibility` – führt alle Checks aus und gibt TaxonPlausibilityResult zurück

**Fachliche Einordnung:** `plausibilityScoring.ts` prüft Kontext- und Verbreitungsplausibilität, keine Artidentität. Deutschland-Relevanz ist harter Anker. Fehlende Kontextangaben werden neutral behandelt (maxScore = 0). Standort, Feuchte, Licht und Phänologie schwächen oder stützen Kandidaten, schließen sie aber nicht hart aus. Ein Status `high_plausibility` ist keine sichere Artbestimmung.

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

## Noch nicht implementiert

- Kombinierte Gesamtbewertung aus Morphologie und Plausibilität
- Echte Pflanzenarten oder Taxon-Datenbank
- Taxonomische Entscheidungslogik
- Visueller Fotoabgleich
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die Entwicklung einer **kombinierten Gesamtbewertung**, die folgende Teilmodelle zusammenführt:

- morphologische Taxon-Übereinstimmung aus `taxonComparison.ts`
- Kontext- und Verbreitungsplausibilität aus `plausibilityScoring.ts`

Diese kombinierte Gesamtbewertung ist noch nicht implementiert.

Der visuelle Fotoabgleich bleibt weiterhin ein späterer abschließender Kontrollschritt und ist noch nicht implementiert.
