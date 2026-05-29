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

Ziel: `statusLabel(status)`-Funktion in `botanik.html` einführen. Mapping: active → geprüft, stub → vorläufig, context → Kontext, structured_paraphrase → strukturierte Paraphrase.

## Pending human actions

1. Live-API-Verifikation für P1.4 ausführen oder bestätigen:
   ```
   ./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
   ```

2. Jam-Verifikation für P2.1 (Überschriften in #results):
   - Suche auslösen → Überschrift „Suchergebnisse" prüfen.
   - „Foto-Merkmale anzeigen" → Überschrift „Foto-diagnostische Merkmale" prüfen.

3. Danach P2.2 im erweiterten teilautonomen Modus starten (oder direkt freigeben).

## Next safe Claude Code command

Start P2.2 according to BOTANIK_DEVELOPMENT_PLAN.md using the extended partially autonomous gate mode. Only `botanik.html` may be changed. No issue comment or issue closing without explicit approval.

## Gate-Modus

Erweiterter teilautonomer Modus aktiv.
- Auto-Commit und Auto-Push bei erfüllten Bedingungen erlaubt (Details in BOTANIK_DEVELOPMENT_PLAN.md).
- Issue-Kommentare und Issue-Schließungen bleiben freigabepflichtig.
