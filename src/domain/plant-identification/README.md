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

**Fachliche Einordnung:** Das Scoring ist ein Hilfsmodell zur merkmalsbasierten Eingrenzung, keine abschließende Artbestimmung.

#### Taxon-Profil-Schema (taxonProfile.ts)

Ein Schema für spätere Familien-, Gattungs- und Artprofile ist definiert.

**Typen:** `TaxonomicRank`, `FloristicStatus`, `GermanyRelevance`, `TaxonomicIdentity`, `EcologyProfile`, `PhenologyProfile`, `VisualReferenceProfile`, `PlantTaxonProfile`

**Fachliche Einordnung:** Nur ein Schema. Keine echten Pflanzenarten, keine Artenliste, keine Bestimmungslogik.

#### Taxon-Vergleichsfunktion (taxonComparison.ts)

Eine erste Taxon-Vergleichsfunktion ist implementiert.

**Typen:**
- `TaxonComparisonStatus` – no_observable_features, low_match, moderate_match, high_match
- `TaxonComparisonResult` – Vergleichsergebnis mit Score, Status und Begründung

**Funktionen:**
- `determineTaxonComparisonStatus` – leitet den Status aus Score und Vergleichsergebnissen ab
- `getTaxonComparisonReason` – liefert eine textuelle Begründung zum Status
- `compareObservedFeaturesWithTaxon` – vergleicht beobachtete Merkmale mit einem PlantTaxonProfile

**Fachliche Einordnung:** `taxonComparison.ts` bewertet ausschließlich morphologische Merkmalsübereinstimmung. Sie führt keine taxonomische Entscheidung allein herbei, keine Deutschland-/Status-/Standortprüfung und keinen visuellen Fotoabgleich. Ein Status `high_match` bedeutet nur hohe morphologische Übereinstimmung – er darf nicht automatisch als sichere Artbestimmung ausgegeben werden.

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

## Noch nicht implementiert

- Echte Pflanzenarten oder Taxon-Datenbank
- Deutschland-/Status-/Standort-Plausibilitätsmodell
- Taxonomische Entscheidungslogik
- Verbreitungs- und Statusprüfung
- Visueller Fotoabgleich
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die Entwicklung eines **Deutschland-/Status-/Standort-Plausibilitätsmodells**.

Dieses Modell soll prüfen, ob ein Taxon für den deutschen Bestimmungsraum relevant ist, welchen floristischen Status es hat und ob der beobachtete Standort zur Art plausibel ist.

Das Deutschland-/Status-/Standort-Plausibilitätsmodell ist noch nicht implementiert.
