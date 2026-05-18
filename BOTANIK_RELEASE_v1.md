# Botanik-Integration v1

Status: Die Botanik-Integration ist produktiv erreichbar, dokumentiert und prüfbar.

Produktive Basis-URL:
https://overleaf-tdkd.onrender.com

Produktive Komponenten:
- Node/Express-API auf Render
- SQLite-Datenbank botanik_v4_0_production_ready.db
- Testfrontend botanik.html
- API-Dokumentation BOTANIK_API.md
- README-Verlinkung
- Health-Check-Script scripts/check_botanik_api.sh
- npm-Script npm run check:botanik

Produktive Endpunkte:
- GET /api/botanik/health
- GET /api/botanik/taxa?q=Acer
- GET /api/botanik/taxon/berberis_vulgaris
- GET /api/botanik/features/photo
- GET /api/botanik/features/photo?visibility=medium&weight=medium
- GET /botanik.html

Frontend-Funktionen:
- Taxa suchen
- Taxon-Details anzeigen
- Merkmale pro Taxon anzeigen
- Foto-diagnostische Merkmale anzeigen
- Foto-Merkmale nach Sichtbarkeit filtern
- Foto-Merkmale nach Diagnosegewicht filtern
- Foto-Merkmale per Textsuche filtern
- Von Merkmal direkt zur Taxon-Detailansicht springen

Validierung:
npm run check:botanik

Erwartete Schlusszeile:
All Botanik API checks passed.

Fachlicher Status:
Die Datenbasis ist auf Rothmaler und Strasburger ausgerichtet. Datensätze mit status=review, leeren Detailfeldern oder auffälligen Namenskonzepten sind fachlich weiter zu prüfen.

Offene fachliche Qualitätskontrollen:
- Namensprüfung auffälliger Taxa, z. B. Ranunculus acer versus Ranunculus acris
- Ergänzung fehlender Familien-/Gattungsfelder bei importierten Taxa
- Ausbau artspezifischer Merkmale für häufige Fototaxa
- Prüfung von Quellenhinweisen mit Rothmaler und Strasburger
- Trennung sicherer Foto-Merkmale von Merkmalen, die Präparation oder Mikroskopie benötigen
