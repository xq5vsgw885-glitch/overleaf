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

## Last completed points

| Punkt | Commit | Jam | Issue |
|-------|--------|-----|-------|
| P1.2 Quellenanzeige in Suchergebnissen | `6ff39d6` | `68cb929f` ✓ | #4 geschlossen |
| P1.3 Sichere Taxon-Auswahl | `28ec2fa` | `23d49de8` ✓ | #5 geschlossen |
| P1.4 API-Check robuster | `dd4ae15` | — (kein UI) | — |
| P2.1 Modusindikator für #results | `ea5fa6e` | ausstehend | — |
| P2.2 Statuslabels übersetzen | `<hash>` | optional | — |

## Current open point

**P2.3 — Hinweis bei LIMIT-Erreichen**

Ziel: Bei 50 Treffern Hinweis anzeigen „Es werden maximal 50 Treffer angezeigt. Bitte Suche verfeinern." Änderungen in `server.js` (`limit`, `maybe_truncated`) und `botanik.html`.

## Pending verification

1. Live-API-Verifikation für P1.4:
   ```bash
   ./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
   ```

2. Jam-Verifikation für P2.1 (Überschriften) und optional P2.2 (Statuslabels).

Diese Punkte blockieren P2.3 nicht.

## Next safe Claude Code command

```text
Synchronisiere zuerst den aktuellen GitHub-Stand:

git pull origin TU

Lies danach:
- AGENTS.md
- BOTANIK_DEVELOPMENT_PLAN.md
- BOTANIK_WORKLOG.md
- BOTANIK_HANDOFF.md

Starte P2.3 — Hinweis bei LIMIT-Erreichen — nach BOTANIK_DEVELOPMENT_PLAN.md im erweiterten teilautonomen Gate-Modus.

Erlaubte Code-Dateien:
- server.js
- botanik.html

Zusätzlich zu aktualisieren:
- BOTANIK_WORKLOG.md
- BOTANIK_HANDOFF.md

Nicht erlaubt:
- database/
- package.json / package-lock.json / requirements.txt
- AGENTS.md
- BOTANIK_DEVELOPMENT_PLAN.md
- Branch-Wechsel, Merge oder Rebase
- Issue-Kommentar oder Issue-Schließung

Ziel:
- server.js: limit: 50 und maybe_truncated: rows.length === 50 im /api/botanik/taxa Response ergänzen.
- botanik.html: bei maybe_truncated Hinweis anzeigen.
- Keine Pagination, keine DB-Änderung.

Tests:
- node --check server.js
- python3.13 -m pytest tests/ --ignore=tests/test_analyze.py -v

Wenn alle Auto-Gates erfüllt sind:
- Commit automatisch mit: feat(botanik): warn when search results may be truncated
- Push automatisch auf origin TU
- BOTANIK_WORKLOG.md und BOTANIK_HANDOFF.md im selben Commit aktualisieren.

Stoppe nur bei:
- Testfehlern
- unklarem API-Verhalten
- notwendiger Änderung außerhalb des erlaubten Scopes
- Issue-Kommentar oder Issue-Schließung
```

## Gate-Modus

Erweiterter teilautonomer Modus aktiv.

- Auto-Commit und Auto-Push bei erfüllten Bedingungen erlaubt.
- Claude Code dokumentiert Fehler oder Stopppunkte in `BOTANIK_WORKLOG.md` und `BOTANIK_HANDOFF.md`.
- Issue-Kommentare und Issue-Schließungen bleiben freigabepflichtig.
