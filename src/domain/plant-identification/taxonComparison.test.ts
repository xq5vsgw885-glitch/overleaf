import { describe, it, expect } from "vitest";
import {
  determineTaxonComparisonStatus,
  getTaxonComparisonReason,
  compareObservedFeaturesWithTaxon,
  TaxonComparisonStatus,
} from "./taxonComparison.js";
import { FeatureComparisonResult, ObservedFeature } from "./featureScoring.js";
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
  morphology: [
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
  ],
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

const dummyFeatureResult: FeatureComparisonResult = {
  featureId: "blattstellung",
  matched: true,
  score: 1,
  maxScore: 1,
  diagnosticWeight: "hoch",
  reason: "matched",
};

describe("determineTaxonComparisonStatus", () => {
  it("returns no_observable_features for empty featureResults", () => {
    expect(determineTaxonComparisonStatus(0, [])).toBe(
      "no_observable_features"
    );
  });

  it("returns low_match for score 0.39", () => {
    expect(determineTaxonComparisonStatus(0.39, [dummyFeatureResult])).toBe(
      "low_match"
    );
  });

  it("returns moderate_match for score 0.4", () => {
    expect(determineTaxonComparisonStatus(0.4, [dummyFeatureResult])).toBe(
      "moderate_match"
    );
  });

  it("returns moderate_match for score 0.74", () => {
    expect(determineTaxonComparisonStatus(0.74, [dummyFeatureResult])).toBe(
      "moderate_match"
    );
  });

  it("returns high_match for score 0.75", () => {
    expect(determineTaxonComparisonStatus(0.75, [dummyFeatureResult])).toBe(
      "high_match"
    );
  });

  it("returns high_match for score 1", () => {
    expect(determineTaxonComparisonStatus(1, [dummyFeatureResult])).toBe(
      "high_match"
    );
  });
});

describe("getTaxonComparisonReason", () => {
  const cases: [TaxonComparisonStatus, string][] = [
    ["no_observable_features", "no_observable_features"],
    ["low_match", "low_morphological_match"],
    ["moderate_match", "moderate_morphological_match"],
    ["high_match", "high_morphological_match"],
  ];

  for (const [status, expectedReason] of cases) {
    it(`returns "${expectedReason}" for status "${status}"`, () => {
      expect(getTaxonComparisonReason(status)).toBe(expectedReason);
    });
  }
});

describe("compareObservedFeaturesWithTaxon", () => {
  it("returns high_match when both features match", () => {
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
    const result = compareObservedFeaturesWithTaxon(observed, testTaxon);
    expect(result.featureResults).toHaveLength(2);
    expect(result.morphologyScore).toBe(1);
    expect(result.status).toBe("high_match");
    expect(result.reason).toBe("high_morphological_match");
    expect(result.taxon.identity.taxonId).toBe("test-taxon-1");
  });

  it("returns high_match with score 0.75 when one of two features does not match", () => {
    // blattstellung: hoch = 3, match → score 3, maxScore 3
    // bluetenfarbe:  niedrig = 1, no match → score 0, maxScore 1
    // total: 3 / 4 = 0.75
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
        observedValue: "rot",
        confidence: 1,
        source: "user_input",
        isVisible: true,
      },
    ];
    const result = compareObservedFeaturesWithTaxon(observed, testTaxon);
    expect(result.morphologyScore).toBe(0.75);
    expect(result.status).toBe("high_match");
    expect(result.reason).toBe("high_morphological_match");
  });

  it("returns no_observable_features when observedFeatures is empty", () => {
    const result = compareObservedFeaturesWithTaxon([], testTaxon);
    expect(result.featureResults).toHaveLength(0);
    expect(result.morphologyScore).toBe(0);
    expect(result.status).toBe("no_observable_features");
    expect(result.reason).toBe("no_observable_features");
  });
});
