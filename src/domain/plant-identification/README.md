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

**Fachliche Einordnung:** Das Scoring ist ein Hilfsmodell zur merkmalsbasierten Eingrenzung, keine abschließende Artbestimmung. Eine sichere Bestimmung erfordert morphologische Konsistenz, taxonomische Plausibilität, Deutschland-/Status-/Standortprüfung und visuellen Fotoabgleich als abschließenden Kontrollschritt.

#### Taxon-Profil-Schema (taxonProfile.ts)

Ein Schema für spätere Familien-, Gattungs- und Artprofile ist definiert.

**Typen:**
- `TaxonomicRank` – Hierarchieebene: familie, gattung, art
- `FloristicStatus` – wildwachsend, etablierter_neophyt, haeufig_verwildernd, kulturpflanze_nachrangig
- `GermanyRelevance` – Deutschland-Relevanz und floristische Statusgewichtung
- `TaxonomicIdentity` – wissenschaftlicher Name, Deutschname, Familie, Gattung, Art, Rang
- `EcologyProfile` – Habitattypen, Feuchte, Licht, Hinweise
- `PhenologyProfile` – Blüte- und Fruchtmonate
- `VisualReferenceProfile` – Platzhalter für spätere Referenzbilder (nur für visuellen Kontrollschritt)
- `PlantTaxonProfile` – Gesamtprofil: verbindet Identität, Deutschland-Relevanz, Morphologie, Ökologie, Phänologie und optionale Referenzbilder

**Fachliche Einordnung:** `taxonProfile.ts` ist nur ein Schema. Es enthält keine echten Pflanzenarten, keine Artenliste und keine Bestimmungslogik. Es dient als Grundlage für spätere strukturierte Familien-, Gattungs- und Artprofile.

### Technische Hinweise

`DiagnosticWeight` enthält die Werte: `"sehr_hoch"`, `"hoch"`, `"mittel"`, `"niedrig"`.

`RequiredPhotoType` enthält die Werte: `"habitus"`, `"standort"`, `"detail"`, `"blatt"`, `"bluete"`, `"frucht"`.

## Noch nicht implementiert

- Echte Pflanzenarten oder Taxon-Datenbank
- Taxon-Vergleichsfunktion
- Taxonomische Entscheidungslogik
- Verbreitungs- und Statusprüfung
- Visueller Fotoabgleich
- UI

## Nächster Entwicklungsschritt

Der nächste fachliche Schritt ist die Entwicklung einer **Taxon-Vergleichsfunktion**, die ein `PlantTaxonProfile` mit einer Menge von `ObservedFeature[]` vergleicht und einen Ähnlichkeitsscore zurückgibt.

Diese Taxon-Vergleichsfunktion ist noch nicht implementiert.
