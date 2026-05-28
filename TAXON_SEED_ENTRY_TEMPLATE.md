# TAXON_SEED_ENTRY_TEMPLATE

Ausfüllbares Template für genau einen fachlich vorgegebenen `TaxonSeedEntry`.

**Grundregel:** Alle Felder müssen extern fachlich geliefert werden.
Claude Code ergänzt keine eigenen botanischen Daten, Taxa oder Merkmale.

---

## Validierungsregeln (taxonSeedPolicy.ts / taxonSeedSchema.ts)

Ein `TaxonSeedEntry` ist nur gültig (`valid: true`), wenn alle 6 Policy-Checks `allowed` zurückgeben:

| # | Check | Regel |
|---|---|---|
| 1 | `checkTaxonSeedSource` | `citation.source` muss `"Rothmaler"` oder `"Strasburger"` sein |
| 2 | `checkTaxonSeedCitation` | `citation.reference` darf nicht leer oder nur Whitespace sein |
| 3 | `checkTaxonSeedGermanyRelevance` | `germanyRelevant` muss `true` sein |
| 4 | `checkTaxonSeedGermanyConsistency` | `germanyRelevant` und `taxon.germanyRelevance.occursInGermany` müssen übereinstimmen |
| 5 | `checkTaxonSeedMorphologyPresent` | `taxon.morphology` muss mindestens 1 Eintrag enthalten |
| 6 | `checkTaxonSeedReviewNote` | `reviewNote` darf nicht leer oder nur Whitespace sein |

---

## Template

```typescript
const eintrag: TaxonSeedEntry = {

  // ── AUDIT-METADATEN ─────────────────────────────────────────────────────────
  // addedAt: ISO-Datum (YYYY-MM-DD). Pflichtfeld. Extern fachlich zu liefern.
  addedAt: "YYYY-MM-DD",

  // reviewNote: Freitextbegründung, warum dieser Eintrag aufgenommen wird.
  // Pflichtfeld. Nicht leer. Nicht nur Whitespace. Extern fachlich zu liefern.
  reviewNote: "...",

  // ── QUELLENANGABE ───────────────────────────────────────────────────────────
  citation: {
    // source: Pflichtfeld. Nur "Rothmaler" oder "Strasburger" erlaubt.
    source: "Rothmaler",  // oder "Strasburger"

    // reference: Pflichtfeld. Exakte Quellenangabe (z. B. Band, Seite, Kapitel).
    // Nicht leer. Extern fachlich zu liefern.
    reference: "...",

    // page: Optional. Konkrete Seitenangabe innerhalb des Werks.
    // page: "...",

    // note: Optional. Ergänzende Anmerkung zur Quellenangabe.
    // note: "...",
  },

  // ── DEUTSCHLAND-RELEVANZ ────────────────────────────────────────────────────
  // germanyRelevant: Muss true sein (Deutschland-App). Muss mit
  // taxon.germanyRelevance.occursInGermany übereinstimmen.
  germanyRelevant: true,

  // ── PFLICHT-LITERALFELDER ────────────────────────────────────────────────────
  // Beide Felder sind TypeScript-Literaltypen und dürfen niemals geändert werden.
  createdFromImageOnly: false,
  createsFinalIdentification: false,

  // ── TAXON-PROFIL ─────────────────────────────────────────────────────────────
  taxon: {

    // ── TAXONOMISCHE IDENTITÄT ────────────────────────────────────────────────
    identity: {
      // taxonId: Eindeutige interne ID. Format: "<gattung>-<art>" (Kleinbuchstaben).
      // Extern fachlich zu liefern.
      taxonId: "...",

      // scientificName: Vollständiger wissenschaftlicher Name. Extern fachlich zu liefern.
      scientificName: "...",

      // germanName: Optional. Deutscher Trivialname. Extern fachlich zu liefern.
      // germanName: "...",

      // family: Optional. Familienname. Extern fachlich zu liefern.
      // family: "...",

      // genus: Optional. Gattungsname. Extern fachlich zu liefern.
      // genus: "...",

      // species: Optional. Artepithet. Extern fachlich zu liefern.
      // species: "...",

      // rank: Pflichtfeld. Einer von: "familie" | "gattung" | "art"
      // Extern fachlich zu liefern.
      rank: "art",
    },

    // ── DEUTSCHLAND-RELEVANZ (Taxon-Ebene) ───────────────────────────────────
    germanyRelevance: {
      // occursInGermany: Muss true sein (und muss mit germanyRelevant oben übereinstimmen).
      occursInGermany: true,

      // floristicStatus: Einer von:
      //   "wildwachsend" | "etablierter_neophyt" | "haeufig_verwildernd" | "kulturpflanze_nachrangig"
      // Extern fachlich zu liefern.
      floristicStatus: "wildwachsend",

      // statusWeight: Gewichtungsfaktor (0–1). Extern fachlich zu liefern.
      statusWeight: 1,
    },

    // ── MORPHOLOGIE ───────────────────────────────────────────────────────────
    // Pflichtfeld: mindestens 1 Eintrag erforderlich (Policy-Check 5).
    // Alle featureId-Werte und acceptedValues extern fachlich zu liefern.
    // featureId muss einem gültigen Merkmal aus morphologicalFeatureMatrix.ts entsprechen.
    morphology: [
      {
        // featureId: ID des Merkmals aus morphologicalFeatureMatrix.ts.
        // Extern fachlich zu liefern.
        featureId: "...",

        // acceptedValues: Zulässige Ausprägungen für dieses Taxon.
        // Extern fachlich zu liefern.
        acceptedValues: ["..."],

        // requiredForStrongIdentification: true wenn dieses Merkmal für eine
        // starke Bestimmung zwingend erforderlich ist. Extern fachlich zu liefern.
        requiredForStrongIdentification: false,
      },
      // Weitere Morphologiemerkmale nach demselben Schema ergänzen.
    ],

    // ── ÖKOLOGIE ──────────────────────────────────────────────────────────────
    ecology: {
      // habitatTypes: Liste der Habitattypen. Extern fachlich zu liefern.
      habitatTypes: ["..."],

      // moisture: Feuchtigkeitspräferenzen. Extern fachlich zu liefern.
      moisture: ["..."],

      // light: Lichtpräferenzen. Extern fachlich zu liefern.
      light: ["..."],

      // notes: Optional. Ökologische Zusatzhinweise.
      // notes: "...",
    },

    // ── PHÄNOLOGIE ────────────────────────────────────────────────────────────
    phenology: {
      // floweringMonths: Blütemonate (z. B. ["mai", "juni"]). Extern fachlich zu liefern.
      floweringMonths: ["..."],

      // fruitingMonths: Fruchtreifezeiten. Extern fachlich zu liefern.
      fruitingMonths: ["..."],
    },

    // ── VISUELLE REFERENZEN ───────────────────────────────────────────────────
    // Optional. Aktuell keine Bildanalyse implementiert (imageAnalysisImplemented: false).
    // Alle Arrays leer lassen, bis visuelle Referenzen fachlich freigegeben werden.
    // visualReferences: {
    //   habitusImages: [],
    //   leafImages: [],
    //   flowerImages: [],
    //   fruitImages: [],
    //   detailImages: [],
    // },
  },
};
```

---

## Checkliste vor Übergabe an Claude Code

Jedes Feld mit `"..."` oder `["..."]` muss fachlich gefüllt werden, bevor Claude Code
`taxonSeedData.ts` ändern darf.

- [ ] `addedAt` gesetzt (ISO-Datum, z. B. `"2026-05-28"`)
- [ ] `reviewNote` gesetzt (nicht leer)
- [ ] `citation.source` ist `"Rothmaler"` oder `"Strasburger"`
- [ ] `citation.reference` gesetzt (nicht leer)
- [ ] `germanyRelevant: true`
- [ ] `taxon.germanyRelevance.occursInGermany: true`
- [ ] `taxon.morphology` enthält mindestens 1 Eintrag
- [ ] Alle `featureId`-Werte stammen aus `morphologicalFeatureMatrix.ts`
- [ ] `createdFromImageOnly: false` (unveränderlich)
- [ ] `createsFinalIdentification: false` (unveränderlich)
- [ ] `validateTaxonSeedEntry(eintrag).valid === true` (Pflichtprüfung nach Eintrag)

---

## Hinweis

Dieses Template ist ausschließlich ein strukturelles Hilfsmittel.
Es enthält keine echten Taxa, keine Seed-Daten und keine botanischen Daten.
`PLANT_TAXON_SEED_DATA` bleibt leer, bis Phase 3 explizit gestartet wird.
