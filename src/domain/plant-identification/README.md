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

**Typen:**
- `ObservedFeature` – ein beobachtetes Merkmal aus Foto, Nutzerangabe oder Ableitung
- `TaxonFeatureProfile` – Merkmalsangabe eines späteren Art- oder Gattungsprofils
- `FeatureComparisonResult` – Ergebnis eines einzelnen Merkmalsvergleichs

**Funktionen:**
- `diagnosticWeightToNumber` – übersetzt DiagnosticWeight in einen numerischen Wert
- `compareFeature` – vergleicht ein beobachtetes Merkmal mit einem Profil-Eintrag
- `compareFeatureSet` – vergleicht eine Menge beobachteter Merkmale mit einem Taxon-Profil
- `calculateFeatureScore` – berechnet einen Gesamtscore zwischen 0 und 1

**Fachliche Einordnung:**
Das Scoring ist ein Hilfsmodell zur merkmalsbasierten Eingrenzung, keine abschließende Artbestimmung. Fehlende Merkmale werden nicht negativ bewertet. Sichtbare, passende Merkmale werden nach diagnostischem Gewicht und Beobachtungssicherheit gewichtet. Eine sichere Bestimmung erfordert morphologische Konsistenz, taxonomische Plausibilität, Deutschland-/Status-/Standortprüfung und visuellen Fotoabgleich als abschließenden Kontrollschritt.

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

## Noch nicht implementiert

- Taxon-/Artprofil-Schema
- Pflanzenarten oder Taxon-Datenbank
- Taxonomische Hierarchie
- Verbreitungs- und Statusprüfung
- Visueller Fotoabgleich
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die Definition eines **Taxon-/Artprofil-Schemas**.

Dieses Schema soll beschreiben, wie ein Art- oder Gattungsprofil strukturiert ist, das später mit dem Scoring-Modell verglichen werden kann.

Das Taxon-/Artprofil-Schema ist noch nicht implementiert.
