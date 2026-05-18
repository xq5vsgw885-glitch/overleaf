# Botanik API

Produktive Basis-URL:

https://overleaf-tdkd.onrender.com

## Endpunkte

### Status

GET /api/botanik/health

Test:

curl "https://overleaf-tdkd.onrender.com/api/botanik/health"

### Taxa suchen

GET /api/botanik/taxa?q=Acer

Test:

curl "https://overleaf-tdkd.onrender.com/api/botanik/taxa?q=Acer"


#### Stub-Taxa einschließen

Standardmäßig blendet `/api/botanik/taxa` vorbereitete, aber noch nicht diagnostisch ausgearbeitete Taxa mit `status=stub` aus.

Mit folgendem Parameter werden sie zusätzlich angezeigt:

    GET /api/botanik/taxa?q=Acer&include_stubs=1

Interpretation:

- `include_stubs=false`: Standardmodus für normale Bestimmung; nur ausgearbeitete Taxa.
- `include_stubs=true`: Datenpflege-/Expertenmodus; vorbereitete Taxa werden zusätzlich angezeigt.
- `deprecated` und `reference_only` bleiben ausgeschlossen.

### Taxon-Details

GET /api/botanik/taxon/berberis_vulgaris

Test:

curl "https://overleaf-tdkd.onrender.com/api/botanik/taxon/berberis_vulgaris"

### Foto-diagnostische Merkmale

GET /api/botanik/features/photo

Standardfilter:

visibility=high
weight=high

Test:

curl "https://overleaf-tdkd.onrender.com/api/botanik/features/photo"

Mit Filter:

curl "https://overleaf-tdkd.onrender.com/api/botanik/features/photo?visibility=medium&weight=medium"

## Frontend

https://overleaf-tdkd.onrender.com/botanik.html

Funktionen:

- Taxa suchen
- Taxon-Details anzeigen
- Foto-Merkmale anzeigen
- Foto-Merkmale nach Sichtbarkeit filtern
- Foto-Merkmale nach Diagnosegewicht filtern
- Foto-Merkmale per Textsuche filtern
- Von Merkmal direkt zur Taxon-Detailansicht springen

## Datenbasis

Die Daten sind auf Rothmaler und Strasburger ausgerichtet. Datensätze mit status=review oder leeren Detailfeldern sind fachlich noch nachzuprüfen.
