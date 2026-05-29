# Botanik-App Worklog

## Zweck

Chronologisches technisches Arbeitsprotokoll.

**Regeln:**
- Pro P-Punkt oder Verifikationsblock einen Abschnitt ergänzen.
- Beobachtung, Interpretation, Unsicherheit und nächste Aktion trennen.
- Tests exakt dokumentieren.
- Nicht ausführbare Tests mit Grund dokumentieren.
- Commit-Hash und Push-Status dokumentieren.
- Jam-ID dokumentieren, falls verwendet.
- Keine spekulative Planung — Planung bleibt in BOTANIK_DEVELOPMENT_PLAN.md.

---

## P1.2 — Quellenanzeige in Suchergebnissen

**Status:** Abgeschlossen.

**Commit:** `6ff39d6` — `feat(botanik): show source labels in search results`
**Push:** origin/TU ✓
**Jam:** `68cb929f`
**Issue:** #4 geschlossen.

**Beobachtung:** Quellenlabels in Suchergebnissen werden korrekt normalisiert angezeigt (Rothmaler, Strasburger, Rothmaler + Strasburger). `sourceLabel()`-Funktion normalisiert `source_pdf`-Werte.

**Tests:** pytest 15/15 passed.

**Unsicherheiten:** keine offen.

---

## P1.3 — Sichere Taxon-Auswahl ohne inline onclick

**Status:** Abgeschlossen.

**Commit:** `28ec2fa` — `fix(botanik): replace inline taxon click handler with event binding`
**Push:** origin/TU ✓
**Jam:** `23d49de8`
**Issue:** #5 geschlossen.

**Beobachtung:** inline `onclick="loadTaxon('...')"` durch `data-taxon-id` + `addEventListener` in `searchTaxa()` und `loadPhotoFeatures()` ersetzt. Stub-Logik und Quellenlabels erhalten. `|| ""`-Guards für `taxon_id` gesetzt.

**Tests:** pytest 15/15 passed.

**Unsicherheiten:** keine offen.

---

## P1.4 — API-Check robuster machen

**Status:** Implementiert und gepusht. Live-API-Verifikation empfohlen.

**Commit:** `dd4ae15` — `test(botanik): make API check resilient to data changes`
**Push:** origin/TU ✓
**Jam:** nicht erforderlich (kein UI-Bezug).

**Beobachtung:**
- Hard-codierte Acer-Counts (2, 5) durch relationale Checks ersetzt: `std > 0`, `stub >= std`.
- Neue Helper `check_json_field_nonempty()` und `get_response_count()` ergänzt.
- Health-Felder `release.version` und `release.release_stage` werden auf Nichtleere geprüft (nested unter `release`).
- P0.2-Ausschluss-Checks: `q=festuca_rubra` und `q=ranunculus_auricomus` müssen count=0 in Standardsuche liefern.

**Tests:**
- `bash -n scripts/check_botanik_api.sh`: OK.
- pytest 15/15 passed.
- Live-API (`https://overleaf-tdkd.onrender.com`): **nicht ausführbar** — Host nicht in Allowlist (Umgebungsrestriktion, kein Scriptfehler).

**Unsicherheiten:** Live-API-Verifikation nach Deploy ausstehend.

**Nächste Aktion:** Nach Render-Deploy prüfen:
```
./scripts/check_botanik_api.sh https://overleaf-tdkd.onrender.com
```

---

## P2.1 — Modusindikator für #results

**Status:** Abgeschlossen.

**Commit:** `ea5fa6e` — `feat(botanik): add result mode headings`
**Push:** origin/TU ✓
**Jam:** erforderlich (UI-Überschrift) — Verifikation ausstehend.

**Beobachtung:** `<h3>Suchergebnisse</h3>` in `searchTaxa()` und `<h3>Foto-diagnostische Merkmale</h3>` in `loadPhotoFeatures()` ergänzt. Leer- und Fehlerzustände (`box.textContent`) unverändert.

**Tests:** pytest 15/15 passed.

**Unsicherheiten:** Jam-Verifikation der visuellen Überschriften ausstehend.

---

## Nächster offener Punkt: P2.2 — Statuslabels übersetzen

Bereit zur Implementierung im erweiterten teilautonomen Gate-Modus.
