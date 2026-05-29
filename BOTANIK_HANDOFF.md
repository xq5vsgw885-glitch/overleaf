# Botanik-App Handoff

Kompakter Synchronisationsstand für Übergaben zwischen Claude Code, ChatGPT-Review und Nutzerfreigaben.

---

## Current branch

`TU`

## Current source of truth

- `AGENTS.md`
- `BOTANIK_DEVELOPMENT_PLAN.md`
- `BOTANIK_WORKLOG.md`
- `BOTANIK_HANDOFF.md`

## Last completed points

| Punkt | Commit | Jam | Issue |
|-------|--------|-----|-------|
| P1.2 Quellenanzeige in Suchergebnissen | `6ff39d6` | `68cb929f` ✓ | #4 geschlossen |
| P1.3 Sichere Taxon-Auswahl | `28ec2fa` | `23d49de8` ✓ | #5 geschlossen |
| P1.4 API-Check robuster | `dd4ae15` | — (kein UI) | — |
| P2.1 Modusindikator für #results | `ea5fa6e` | ausstehend | — |

## Current open point

**P2.2 — Statuslabels übersetzen**

Ziel: `statusLabel(status)`-Funktion in `botanik.html` einführen. Mapping:

- `active` → `geprüft`
- `stub` → `vorläufig`
- `context` → `Kontext`
- `structured_paraphrase` → `strukturierte Paraphrase`

## Pending verification

1. Live-API-Verifikation für P1.4 ausführen oder bestätigen:
   ```bash
   ./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
   ```

2. Jam-Verifikation für P2.1:
   - Suche auslösen → Überschrift „Suchergebnisse" prüfen.
   - „Foto-Merkmale anzeigen" → Überschrift „Foto-diagnostische Merkmale" prüfen.

Diese beiden Punkte blockieren P2.2 nicht, müssen aber im Worklog nachgetragen werden, sobald sie erledigt sind.

## Next safe Claude Code command

```text
Synchronisiere zuerst den aktuellen GitHub-Stand:

git pull origin TU

Lies danach:
- AGENTS.md
- BOTANIK_DEVELOPMENT_PLAN.md
- BOTANIK_WORKLOG.md
- BOTANIK_HANDOFF.md

Starte P2.2 — Statuslabels übersetzen — nach BOTANIK_DEVELOPMENT_PLAN.md im erweiterten teilautonomen Gate-Modus.

Erlaubte Code-Datei:
- botanik.html

Zusätzlich zu aktualisieren:
- BOTANIK_WORKLOG.md
- BOTANIK_HANDOFF.md

Nicht erlaubt:
- server.js
- scripts/check_botanik_api.sh
- database/
- package.json / package-lock.json / requirements.txt
- AGENTS.md
- BOTANIK_DEVELOPMENT_PLAN.md
- Branch-Wechsel, Merge oder Rebase
- Issue-Kommentar oder Issue-Schließung

Ziel:
- statusLabel(status) in botanik.html einführen.
- Statusanzeige in Suchtreffern über statusLabel(...) rendern.
- active → geprüft
- stub → vorläufig
- context → Kontext
- structured_paraphrase → strukturierte Paraphrase
- unbekannte Statuswerte sicher escaped anzeigen.
- .taxon-stub bleibt erhalten.
- Quellenlabel bleibt erhalten.
- Event-Binding aus P1.3 bleibt erhalten.

Tests:
- python3.13 -m pytest tests/test_frontend_workflow.py -v
- python3.13 -m pytest tests/ --ignore=tests/test_analyze.py -v

Wenn alle Auto-Gates erfüllt sind:
- Commit automatisch mit: feat(botanik): translate taxon status labels
- Push automatisch auf origin TU
- BOTANIK_WORKLOG.md und BOTANIK_HANDOFF.md im selben Commit aktualisieren, sofern sie nur den aktuellen P2.2-Stand beschreiben.

Stoppe nur bei:
- Testfehlern
- unklarer Statuslogik
- notwendiger Änderung außerhalb des erlaubten Scopes
- fachlicher botanischer Entscheidung
- Issue-Kommentar oder Issue-Schließung
```

## Gate-Modus

Erweiterter teilautonomer Modus aktiv.

- Auto-Commit und Auto-Push bei erfüllten Bedingungen erlaubt.
- Claude Code dokumentiert Fehler oder Stopppunkte in `BOTANIK_WORKLOG.md` und `BOTANIK_HANDOFF.md`.
- Issue-Kommentare und Issue-Schließungen bleiben freigabepflichtig.
