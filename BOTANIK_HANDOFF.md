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
| P2.2 Statuslabels übersetzen | `0509ca9` | optional | — |
| P2.3 Hinweis bei LIMIT-Erreichen | `05cbffa` | ausstehend | — |

## Current open point

**P2.4 — API_BASE konfigurierbar machen**

Ziel: `API_BASE` in `botanik.html` auf `window.location.origin` als Default umstellen. Optionaler Override per `?api_base=http(s)://...`. Ungültige Werte Fallback auf `window.location.origin`.

## Pending verification

1. Live-API-Verifikation für P1.4 und P2.3 nach Render-Deploy:
   ```bash
   ./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
   ```

2. Jam-Verifikation für P2.1 (Überschriften), optional P2.2 (Statuslabels), P2.3 (Truncation-Hinweis).

Diese Punkte blockieren P2.4 nicht.

## Next safe Claude Code command

```text
Synchronisiere zuerst den aktuellen GitHub-Stand:

git pull origin TU

Lies danach:
- AGENTS.md
- BOTANIK_DEVELOPMENT_PLAN.md
- BOTANIK_WORKLOG.md
- BOTANIK_HANDOFF.md

Starte P2.4 — API_BASE konfigurierbar machen — nach BOTANIK_DEVELOPMENT_PLAN.md im erweiterten teilautonomen Gate-Modus.

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
- const API_BASE = "https://overleaf-tdkd.onrender.com" ersetzen durch window.location.origin als Default.
- Optionaler Override per URL-Parameter ?api_base=http(s)://...
- Ungültige Werte (kein http/https-Prefix) Fallback auf window.location.origin.
- Keine Backend-Änderung.
- Alle bestehenden API-Aufrufe funktionieren weiterhin.

Tests:
- python3.13 -m pytest tests/test_frontend_workflow.py -v
- python3.13 -m pytest tests/ --ignore=tests/test_analyze.py -v

Wenn alle Auto-Gates erfüllt sind:
- Commit automatisch mit: chore(botanik): make API base configurable
- Push automatisch auf origin TU
- BOTANIK_WORKLOG.md und BOTANIK_HANDOFF.md im selben Commit aktualisieren.

Stoppe nur bei:
- Testfehlern
- unklarem Validierungsverhalten
- notwendiger Änderung außerhalb des erlaubten Scopes
- Issue-Kommentar oder Issue-Schließung
```

## Gate-Modus

Erweiterter teilautonomer Modus aktiv.

- Auto-Commit und Auto-Push bei erfüllten Bedingungen erlaubt.
- Claude Code dokumentiert Fehler oder Stopppunkte in `BOTANIK_WORKLOG.md` und `BOTANIK_HANDOFF.md`.
- Issue-Kommentare und Issue-Schließungen bleiben freigabepflichtig.
