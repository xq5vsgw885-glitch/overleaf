# TAXON_SEED_CANDIDATES

Nicht-produktive Vorprüfdatei für Phase 3.1 – Kandidaten für `PLANT_TAXON_SEED_DATA`.

**Status:** Keine Einträge bereit. Extern fachlich zu liefern.

---

## Zweck

Diese Datei dient als Schleuse zwischen lokaler Quellenanalyse und
`TAXON_SEED_ENTRY_TEMPLATE.md`. Sie enthält keine produktiven Taxa und
keinen Code.

Ein Kandidat darf erst in `TAXON_SEED_ENTRY_TEMPLATE.md` übertragen und dann
in `taxonSeedData.ts` eingetragen werden, wenn er **alle 8 Policy-Checks** in
`validateTaxonSeedEntry` besteht (Stand Phase 2.6, `tsc` und `npm test` grün).

---

## Strikte Regeln

- Claude Code ergänzt keine eigenen Taxa, Merkmale oder Quelleninterpretationen.
- Alle Pflichtfelder müssen extern fachlich geliefert werden.
- Ein Kandidat wird nur eingetragen, wenn er durch lokale Quellendaten belegbar ist.
- Status `bereit_fuer_template` erfordert alle Pflichtfelder lückenlos.
- `PLANT_TAXON_SEED_DATA` bleibt leer, bis Phase 3.1 explizit gestartet wird.

---

## Vorhandene lokale Datenquellen

### Lokale SQLite-Datenbank

**Datei:** `database/botanik_v4_0_production_ready.db`

**Analyse-Ergebnis (Stand 2026-05-28):**

| Kennzahl | Wert |
|---|---|
| Gesamt-Taxa | 855 |
| Zugelassene Quellen | `Rothmaler`, `Strasburger` (einzeln und kombiniert) |
| Taxa mit Status `active`, Rang `species` | 132 |
| Aktive Species mit Morphologie-Features | **0** |
| Aktive Species mit `source_note` (Seitenangabe) | **0** |
| Taxa mit Features gesamt | 320 (davon keine auf Species-Rang) |

**Bewertung:** Die Datenbank ist als Quellindex für Rothmaler und Strasburger
angelegt. Aktive Species-Einträge existieren (scientific_name, family, genus),
haben jedoch keine Morphologie-Features und keine seitenspezifischen
Quellenangaben. Damit fehlen für Phase 3.1 zwei der acht Pflichtfelder:
`taxon.morphology` und `citation.reference`.

**Datenbankstruktur (für Referenz):**

```
botanik_taxa:   taxon_id, rank, scientific_name, german_name,
                family, genus, species, source_pdf, source_note,
                app_scope, status

botanik_features: feature_id, taxon_id, organ, feature_group,
                  character, state, visibility_in_photo,
                  diagnostic_weight, source_pdf, source_note
```

---

## Kandidaten-Tabelle

| # | scientificName | Status | featureId vorhanden | citation.reference vorhanden | Blocker |
|---|---|---|---|---|---|
| – | *(leer)* | – | – | – | Extern fachlich zu liefern |

**Legende:**
- `unvollständig` — Pflichtfelder fehlen, Eintrag nicht prüfbar
- `prüfbar` — Alle Felder ausgefüllt, Policy-Check noch ausstehend
- `bereit_fuer_template` — Alle 8 Checks bestanden, bereit für TAXON_SEED_ENTRY_TEMPLATE.md

---

## Offene Pflichtfelder für jeden Kandidaten

Jeder Kandidat muss folgende Felder vollständig extern geliefert bekommen,
bevor Claude Code ihn in `TAXON_SEED_ENTRY_TEMPLATE.md` eintragen darf:

| Feld | Typ | Pflicht-Check | Aktuell |
|---|---|---|---|
| `taxon.identity.taxonId` | string | — | offen |
| `taxon.identity.scientificName` | string | — | offen |
| `taxon.identity.rank` | `"art"` | — | offen |
| `taxon.germanyRelevance.occursInGermany` | `true` | Check 3+4 | offen |
| `taxon.germanyRelevance.floristicStatus` | FloristicStatus | — | offen |
| `taxon.morphology` | mind. 1 Eintrag | Check 5 | offen |
| `taxon.morphology[].featureId` | ID aus morphologicalFeatureMatrix.ts | — | offen |
| `taxon.ecology.habitatTypes` | string[] | — | offen |
| `taxon.phenology.floweringMonths` | string[] | — | offen |
| `citation.source` | `"Rothmaler"` oder `"Strasburger"` | Check 1 | offen |
| `citation.reference` | nicht-leere Seitenangabe | Check 2 | offen |
| `germanyRelevant` | `true` | Check 3 | offen |
| `addedAt` | YYYY-MM-DD | Check 7+8 | offen |
| `reviewNote` | nicht-leer | Check 6 | offen |

---

## Quellenprüfung

Die lokale Datenbank bestätigt: Rothmaler und Strasburger sind die einzigen
zugelassenen Quellen (`ALLOWED_SOURCES` in `taxonSeedPolicy.ts`).

Ein `citation.reference`-Wert muss eine konkrete Seitenangabe enthalten
(z. B. `"Band 2, S. 234"` oder `"Kap. 23, S. 512"`), die aus dem physischen
Werk stammt. Die Datenbank enthält keine seitenspezifischen Angaben auf
Species-Rang — diese müssen extern fachlich geliefert werden.

---

## Übergabekriterium an TAXON_SEED_ENTRY_TEMPLATE.md

Ein Kandidat darf in `TAXON_SEED_ENTRY_TEMPLATE.md` übertragen werden, wenn:

- [ ] Status `bereit_fuer_template`
- [ ] Alle 14 Pflichtfelder oben ausgefüllt
- [ ] `featureId`-Wert in `morphologicalFeatureMatrix.ts` vorhanden
- [ ] `citation.reference` ist eine nachprüfbare Seitenangabe aus Rothmaler oder Strasburger
- [ ] Claude Code hat **keine** eigenen botanischen Interpretationen vorgenommen

---

## Nicht produktiv

Diese Datei ist ausschließlich ein Planungs- und Prüfdokument.

- Kein Einfluss auf `taxonSeedData.ts`
- Kein Einfluss auf `PLANT_TAXON_SEED_DATA`
- Keine TypeScript-Änderungen
- Keine Teständerungen
- Keine echten Taxa oder Seed-Daten
- `PLANT_TAXON_SEED_DATA` bleibt `[]`
- `realTaxaImplemented: false` bleibt `false`
- `finalSpeciesIdentificationImplemented: false` bleibt `false`
- `imageAnalysisImplemented: false` bleibt `false`
