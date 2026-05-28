import { describe, it, expect } from "vitest";
import {
  hasUsableCitation,
  validateTaxonSeedEntry,
  createBlockedTaxonSeedValidationResult,
} from "./taxonSeedSchema.js";
import { TaxonSeedEntry } from "./taxonSeedSchema.js";
import { PlantTaxonProfile } from "./taxonProfile.js";

const testTaxon: PlantTaxonProfile = {
  identity: {
    taxonId: "test-taxon-1",
    scientificName: "Test taxon",
    germanName: "Testpflanze",
    family: "Testaceae",
    genus: "Testgenus",
    species: "testensis",
    rank: "art",
  },
  germanyRelevance: {
    occursInGermany: true,
    floristicStatus: "wildwachsend",
    statusWeight: 1,
  },
  morphology: [{ featureId: "test-feature", acceptedValues: ["test"], requiredForStrongIdentification: false }],
  ecology: {
    habitatTypes: ["wiese"],
    moisture: ["frisch"],
    light: ["vollsonnig"],
  },
  phenology: {
    floweringMonths: ["mai"],
    fruitingMonths: ["juni"],
  },
  visualReferences: {
    habitusImages: [],
    leafImages: [],
    flowerImages: [],
    fruitImages: [],
    detailImages: [],
  },
};

describe("hasUsableCitation", () => {
  it("returns true for non-empty reference", () => {
    expect(hasUsableCitation({ source: "Rothmaler", reference: "Band 1, S. 10" })).toBe(true);
  });

  it("returns false for empty reference", () => {
    expect(hasUsableCitation({ source: "Rothmaler", reference: "" })).toBe(false);
  });

  it("returns false for whitespace-only reference", () => {
    expect(hasUsableCitation({ source: "Rothmaler", reference: "   " })).toBe(false);
  });
});

describe("validateTaxonSeedEntry", () => {
  it("allows valid entry with Rothmaler, citation, and Germany relevance", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "Rothmaler", reference: "Band 1, S. 10" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(true);
    expect(result.reason).toBe("taxon_seed_entry_valid");
    expect(result.checks).toHaveLength(7);
    expect(result.checks.every((c) => c.status === "allowed")).toBe(true);
  });

  it("allows valid entry with Strasburger, citation, and Germany relevance", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "Strasburger", reference: "Kapitel Morphologie" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(true);
    expect(result.reason).toBe("taxon_seed_entry_valid");
    expect(result.checks.every((c) => c.status === "allowed")).toBe(true);
  });

  it("blocks entry with disallowed source", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "extern_nicht_zugelassen", reference: "Irgendeine Quelle" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "source_not_allowed"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry with missing citation", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "Rothmaler", reference: "" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "citation_required"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry without Germany relevance", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "Rothmaler", reference: "Band 1, S. 10" },
      germanyRelevant: false,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "germany_relevance_required"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry where germanyRelevant contradicts taxon occursInGermany", () => {
    const taxonNotInGermany: PlantTaxonProfile = {
      ...testTaxon,
      germanyRelevance: { occursInGermany: false, floristicStatus: "wildwachsend", statusWeight: 0 },
    };
    const entry: TaxonSeedEntry = {
      taxon: taxonNotInGermany,
      citation: { source: "Rothmaler", reference: "Band 1, S. 10" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "germany_relevance_inconsistent"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry with empty morphology", () => {
    const taxonNoMorphology: PlantTaxonProfile = { ...testTaxon, morphology: [] };
    const entry: TaxonSeedEntry = {
      taxon: taxonNoMorphology,
      citation: { source: "Rothmaler", reference: "Band 1, S. 10" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "morphology_required"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry with empty reviewNote", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "Rothmaler", reference: "Band 1, S. 10" },
      germanyRelevant: true,
      addedAt: "2026-05-28",
      reviewNote: "",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "review_note_required"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry with empty addedAt", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "Rothmaler", reference: "Band 1, S. 10" },
      germanyRelevant: true,
      addedAt: "",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    expect(result.reason).toBe("taxon_seed_entry_blocked_by_policy");
    const blocked = result.checks.find(
      (c) => c.status === "blocked" && c.reason === "addedAt_required"
    );
    expect(blocked).toBeDefined();
  });

  it("blocks entry with multiple policy violations", () => {
    const entry: TaxonSeedEntry = {
      taxon: testTaxon,
      citation: { source: "extern_nicht_zugelassen", reference: " " },
      germanyRelevant: false,
      addedAt: "2026-05-28",
      reviewNote: "Testnotiz für automatisierte Tests",
      createdFromImageOnly: false,
      createsFinalIdentification: false,
    };
    const result = validateTaxonSeedEntry(entry);
    expect(result.valid).toBe(false);
    const reasons = result.checks.filter((c) => c.status === "blocked").map((c) => c.reason);
    expect(reasons).toContain("source_not_allowed");
    expect(reasons).toContain("citation_required");
    expect(reasons).toContain("germany_relevance_required");
  });
});

describe("createBlockedTaxonSeedValidationResult", () => {
  it("creates a blocked result with empty checks and given reason", () => {
    const result = createBlockedTaxonSeedValidationResult("manual_block");
    expect(result.valid).toBe(false);
    expect(result.checks).toHaveLength(0);
    expect(result.reason).toBe("manual_block");
  });
});
