# Overleaf / Botanik API

Dieses Repository enthält den Protokollgenerator und die produktive Botanik-Testintegration.

## Botanik

- Produktive Testseite: https://overleaf-tdkd.onrender.com/botanik.html
- API-Dokumentation: [BOTANIK_API.md](BOTANIK_API.md)
- Release-Notiz: [BOTANIK_RELEASE_v1.md](BOTANIK_RELEASE_v1.md)

## Wichtige Botanik-Endpunkte

- `/api/botanik/health`
- `/api/botanik/taxa?q=Acer`
- `/api/botanik/taxon/berberis_vulgaris`
- `/api/botanik/features/photo`

## Produktivtest

Alle produktiven Botanik-Endpunkte können mit einem Befehl geprüft werden:

    ./scripts/check_botanik_api.sh

Optional kann eine andere Basis-URL übergeben werden:

    ./scripts/check_botanik_api.sh http://localhost:3000

Erwartete Schlusszeile:

    All Botanik API checks passed.
## Botanik-Suchmodi

Die Taxon-Suche nutzt standardmäßig nur fachlich ausgearbeitete Taxa:

    /api/botanik/taxa?q=Acer

Vorbereitete Taxa mit `status=stub` können für Datenpflege oder Expertenansicht zusätzlich eingeblendet werden:

    /api/botanik/taxa?q=Acer&include_stubs=1

`deprecated` und `reference_only` bleiben in der Suche ausgeschlossen.

