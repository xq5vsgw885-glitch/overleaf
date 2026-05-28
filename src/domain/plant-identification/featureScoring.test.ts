import { describe, it, expect } from "vitest";
import {
  diagnosticWeightToNumber,
  compareFeature,
  compareFeatureSet,
  calculateFeatureScore,
  ObservedFeature,
  TaxonFeatureProfile,
  FeatureComparisonResult,
} from "./featureScoring.js";

describe("diagnosticWeightToNumber", () => {
  it('returns 1 for "niedrig"', () => {
    expect(diagnosticWeightToNumber("niedrig")).toBe(1);
  });
  it('returns 2 for "mittel"', () => {
    expect(diagnosticWeightToNumber("mittel")).toBe(2);
  });
  it('returns 3 for "hoch"', () => {
    expect(diagnosticWeightToNumber("hoch")).toBe(3);
  });
  it('returns 4 for "sehr_hoch"', () => {
    expect(diagnosticWeightToNumber("sehr_hoch")).toBe(4);
  });
});

describe("compareFeature", () => {
  it("returns matched result when observed value is accepted", () => {
    const observed: ObservedFeature = {
      featureId: "blattstellung",
      observedValue: "gegenständig",
      confidence: 0.8,
      source: "user_input",
      isVisible: true,
    };
    const profile: TaxonFeatureProfile = {
      featureId: "blattstellung",
      acceptedValues: ["gegenständig"],
      requiredForStrongIdentification: true,
    };
    const result = compareFeature(observed, profile);
    expect(result.matched).toBe(true);
    expect(result.diagnosticWeight).toBe("hoch");
    expect(result.maxScore).toBe(3);
    expect(result.score).toBeCloseTo(2.4);
    expect(result.reason).toBe("matched");
  });

  it("returns value_mismatch when observed value is not accepted", () => {
    const observed: ObservedFeature = {
      featureId: "blattstellung",
      observedValue: "wechselständig",
      confidence: 0.8,
      source: "user_input",
      isVisible: true,
    };
    const profile: TaxonFeatureProfile = {
      featureId: "blattstellung",
      acceptedValues: ["gegenständig"],
      requiredForStrongIdentification: true,
    };
    const result = compareFeature(observed, profile);
    expect(result.matched).toBe(false);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(3);
    expect(result.reason).toBe("value_mismatch");
  });

  it("returns feature_not_visible when isVisible is false", () => {
    const observed: ObservedFeature = {
      featureId: "blattstellung",
      observedValue: "gegenständig",
      confidence: 1,
      source: "photo",
      isVisible: false,
    };
    const profile: TaxonFeatureProfile = {
      featureId: "blattstellung",
      acceptedValues: ["gegenständig"],
      requiredForStrongIdentification: true,
    };
    const result = compareFeature(observed, profile);
    expect(result.matched).toBe(false);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(3);
    expect(result.reason).toBe("feature_not_visible");
  });

  it("returns unknown_feature for unrecognised featureId", () => {
    const observed: ObservedFeature = {
      featureId: "unbekanntes_merkmal",
      observedValue: "irgendwas",
      confidence: 1,
      source: "user_input",
      isVisible: true,
    };
    const profile: TaxonFeatureProfile = {
      featureId: "unbekanntes_merkmal",
      acceptedValues: ["irgendwas"],
      requiredForStrongIdentification: false,
    };
    const result = compareFeature(observed, profile);
    expect(result.matched).toBe(false);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(0);
    expect(result.reason).toBe("unknown_feature");
  });
});

describe("compareFeatureSet", () => {
  it("returns matched results for all provided observed features", () => {
    const observed: ObservedFeature[] = [
      {
        featureId: "blattstellung",
        observedValue: "gegenständig",
        confidence: 1,
        source: "user_input",
        isVisible: true,
      },
      {
        featureId: "bluetenfarbe",
        observedValue: "gelb",
        confidence: 1,
        source: "user_input",
        isVisible: true,
      },
    ];
    const taxonProfile: TaxonFeatureProfile[] = [
      {
        featureId: "blattstellung",
        acceptedValues: ["gegenständig"],
        requiredForStrongIdentification: true,
      },
      {
        featureId: "bluetenfarbe",
        acceptedValues: ["gelb"],
        requiredForStrongIdentification: false,
      },
    ];
    const results = compareFeatureSet(observed, taxonProfile);
    expect(results).toHaveLength(2);
    expect(results.every((r) => r.reason === "matched")).toBe(true);
  });

  it("ignores taxon profile entries for which no observed feature exists", () => {
    const observed: ObservedFeature[] = [
      {
        featureId: "blattstellung",
        observedValue: "gegenständig",
        confidence: 1,
        source: "user_input",
        isVisible: true,
      },
    ];
    const taxonProfile: TaxonFeatureProfile[] = [
      {
        featureId: "blattstellung",
        acceptedValues: ["gegenständig"],
        requiredForStrongIdentification: true,
      },
      {
        featureId: "bluetenfarbe",
        acceptedValues: ["gelb"],
        requiredForStrongIdentification: false,
      },
    ];
    const results = compareFeatureSet(observed, taxonProfile);
    expect(results).toHaveLength(1);
    expect(results[0].featureId).toBe("blattstellung");
    expect(results[0].reason).toBe("matched");
  });
});

describe("calculateFeatureScore", () => {
  it("returns correct ratio for non-empty result list", () => {
    const results: FeatureComparisonResult[] = [
      {
        featureId: "a",
        matched: true,
        score: 2,
        maxScore: 4,
        diagnosticWeight: "mittel",
        reason: "matched",
      },
      {
        featureId: "b",
        matched: true,
        score: 1,
        maxScore: 2,
        diagnosticWeight: "niedrig",
        reason: "matched",
      },
    ];
    expect(calculateFeatureScore(results)).toBe(0.5);
  });

  it("returns 0 for empty result list", () => {
    expect(calculateFeatureScore([])).toBe(0);
  });

  it("returns 0 when maxScore sum is 0", () => {
    const results: FeatureComparisonResult[] = [
      {
        featureId: "x",
        matched: false,
        score: 0,
        maxScore: 0,
        diagnosticWeight: "niedrig",
        reason: "unknown_feature",
      },
    ];
    expect(calculateFeatureScore(results)).toBe(0);
  });
});
