import { describe, it, expect } from "vitest";
import {
  PLANT_TAXON_SEED_POLICY,
  isAllowedTaxonSeedSource,
  checkTaxonSeedSource,
  checkTaxonSeedCitation,
  checkTaxonSeedGermanyRelevance,
  checkTaxonSeedGermanyConsistency,
} from "./taxonSeedPolicy.js";

describe("PLANT_TAXON_SEED_POLICY", () => {
  it("contains only allowed sources", () => {
    expect(PLANT_TAXON_SEED_POLICY.allowedSources).toContain("Rothmaler");
    expect(PLANT_TAXON_SEED_POLICY.allowedSources).toContain("Strasburger");
    expect(PLANT_TAXON_SEED_POLICY.allowedSources).not.toContain("extern_nicht_zugelassen");
    expect(PLANT_TAXON_SEED_POLICY.allowedSources).toHaveLength(2);
  });

  it("requires source citation and Germany relevance", () => {
    expect(PLANT_TAXON_SEED_POLICY.requiresSourceCitation).toBe(true);
    expect(PLANT_TAXON_SEED_POLICY.requiresGermanyRelevance).toBe(true);
  });

  it("blocks uncited, image-only, and seed-alone final identifications", () => {
    expect(PLANT_TAXON_SEED_POLICY.allowsUncitedTaxa).toBe(false);
    expect(PLANT_TAXON_SEED_POLICY.allowsImageOnlyTaxa).toBe(false);
    expect(PLANT_TAXON_SEED_POLICY.allowsFinalSpeciesIdentificationFromSeedAlone).toBe(false);
  });
});

describe("isAllowedTaxonSeedSource", () => {
  it("allows Rothmaler", () => {
    expect(isAllowedTaxonSeedSource("Rothmaler")).toBe(true);
  });

  it("allows Strasburger", () => {
    expect(isAllowedTaxonSeedSource("Strasburger")).toBe(true);
  });

  it("blocks extern_nicht_zugelassen", () => {
    expect(isAllowedTaxonSeedSource("extern_nicht_zugelassen")).toBe(false);
  });
});

describe("checkTaxonSeedSource", () => {
  it("returns allowed for Rothmaler", () => {
    const result = checkTaxonSeedSource("Rothmaler");
    expect(result.status).toBe("allowed");
    expect(result.reason).toBe("allowed_source");
  });

  it("returns allowed for Strasburger", () => {
    const result = checkTaxonSeedSource("Strasburger");
    expect(result.status).toBe("allowed");
    expect(result.reason).toBe("allowed_source");
  });

  it("blocks extern_nicht_zugelassen", () => {
    const result = checkTaxonSeedSource("extern_nicht_zugelassen");
    expect(result.status).toBe("blocked");
    expect(result.reason).toBe("source_not_allowed");
  });
});

describe("checkTaxonSeedCitation", () => {
  it("allows when citation is present", () => {
    const result = checkTaxonSeedCitation(true);
    expect(result.status).toBe("allowed");
    expect(result.reason).toBe("citation_present");
  });

  it("blocks when citation is missing", () => {
    const result = checkTaxonSeedCitation(false);
    expect(result.status).toBe("blocked");
    expect(result.reason).toBe("citation_required");
  });
});

describe("checkTaxonSeedGermanyRelevance", () => {
  it("allows when Germany relevance is present", () => {
    const result = checkTaxonSeedGermanyRelevance(true);
    expect(result.status).toBe("allowed");
    expect(result.reason).toBe("germany_relevance_present");
  });

  it("blocks when Germany relevance is missing", () => {
    const result = checkTaxonSeedGermanyRelevance(false);
    expect(result.status).toBe("blocked");
    expect(result.reason).toBe("germany_relevance_required");
  });
});

describe("checkTaxonSeedGermanyConsistency", () => {
  it("allows when germanyRelevant and occursInGermany are both true", () => {
    const result = checkTaxonSeedGermanyConsistency(true, true);
    expect(result.status).toBe("allowed");
    expect(result.reason).toBe("germany_consistency_confirmed");
  });

  it("allows when germanyRelevant and occursInGermany are both false", () => {
    const result = checkTaxonSeedGermanyConsistency(false, false);
    expect(result.status).toBe("allowed");
    expect(result.reason).toBe("germany_consistency_confirmed");
  });

  it("blocks when germanyRelevant is true but occursInGermany is false", () => {
    const result = checkTaxonSeedGermanyConsistency(true, false);
    expect(result.status).toBe("blocked");
    expect(result.reason).toBe("germany_relevance_inconsistent");
  });

  it("blocks when germanyRelevant is false but occursInGermany is true", () => {
    const result = checkTaxonSeedGermanyConsistency(false, true);
    expect(result.status).toBe("blocked");
    expect(result.reason).toBe("germany_relevance_inconsistent");
  });
});
