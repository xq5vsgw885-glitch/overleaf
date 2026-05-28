import { describe, it, expect } from "vitest";
import {
  calculateCombinedScore,
  determineCombinedAssessmentStatus,
  getCombinedAssessmentReason,
  assessTaxonCandidate,
  assessTaxonCandidates,
  CombinedAssessmentStatus,
} from "./combinedAssessment.js";
import { TaxonComparisonResult } from "./taxonComparison.js";
import { TaxonPlausibilityResult } from "./plausibilityScoring.js";
import { PlantTaxonProfile } from "./taxonProfile.js";
import { ObservedFeature } from "./featureScoring.js";
import { ObservationContext } from "./plausibilityScoring.js";

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

const testTaxon2: PlantTaxonProfile = {
  ...testTaxon,
  identity: {
    taxonId: "test-taxon-2",
    scientificName: "Test taxon 2",
    germanName: "Testpflanze2",
    family: "Testaceae2",
    genus: "Testgenus",
    species: "testensis2",
    rank: "art",
  },
  morphology: [
    {
      featureId: "blattstellung",
      acceptedValues: ["wechselständig"],
      requiredForStrongIdentification: true,
    },
    {
      featureId: "bluetenfarbe",
      acceptedValues: ["rot"],
      requiredForStrongIdentification: false,
    },
  ],
};

const notInGermanyTaxon: PlantTaxonProfile = {
  ...testTaxon,
  germanyRelevance: {
    occursInGermany: false,
    floristicStatus: "wildwachsend",
    statusWeight: 0,
  },
};

const matchingObserved: ObservedFeature[] = [
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

const matchingContext: ObservationContext = {
  country: "Deutschland",
  habitatType: "wiese",
  moisture: "frisch",
  light: "vollsonnig",
  month: "mai",
};

function makeMorphologyStub(
  featureResultsLength: number
): TaxonComparisonResult {
  const featureResults = Array.from({ length: featureResultsLength }, () => ({
    featureId: "blattstellung",
    matched: true,
    score: 1,
    maxScore: 1,
    diagnosticWeight: "hoch" as const,
    reason: "matched",
  }));
  return {
    taxon: testTaxon,
    featureResults,
    morphologyScore: featureResultsLength > 0 ? 1 : 0,
    status: featureResultsLength > 0 ? "high_match" : "no_observable_features",
    reason: featureResultsLength > 0 ? "high_morphological_match" : "no_observable_features",
  };
}

function makePlausibilityStub(
  status: TaxonPlausibilityResult["status"]
): TaxonPlausibilityResult {
  return {
    taxon: testTaxon,
    componentResults: [],
    plausibilityScore: status === "not_plausible" ? 0 : 1,
    status,
    reason: status,
  };
}

describe("calculateCombinedScore", () => {
  it("returns 1 when both scores are 1", () => {
    expect(calculateCombinedScore(1, 1)).toBe(1);
  });

  it("returns 0.75 when morphologyScore=1 and plausibilityScore=0", () => {
    expect(calculateCombinedScore(1, 0)).toBe(0.75);
  });

  it("returns 0.25 when morphologyScore=0 and plausibilityScore=1", () => {
    expect(calculateCombinedScore(0, 1)).toBe(0.25);
  });

  it("returns 0.7 when morphologyScore=0.8 and plausibilityScore=0.4", () => {
    expect(calculateCombinedScore(0.8, 0.4)).toBeCloseTo(0.7);
  });
});

describe("determineCombinedAssessmentStatus", () => {
  it("returns insufficient_data when featureResults is empty", () => {
    const result = determineCombinedAssessmentStatus(
      0.9,
      makeMorphologyStub(0),
      makePlausibilityStub("high_plausibility")
    );
    expect(result).toBe("insufficient_data");
  });

  it("returns unlikely_candidate when plausibility status is not_plausible", () => {
    const result = determineCombinedAssessmentStatus(
      0.9,
      makeMorphologyStub(1),
      makePlausibilityStub("not_plausible")
    );
    expect(result).toBe("unlikely_candidate");
  });

  const scoreCases: [number, CombinedAssessmentStatus][] = [
    [0.39, "unlikely_candidate"],
    [0.4,  "possible_candidate"],
    [0.69, "possible_candidate"],
    [0.7,  "probable_candidate"],
    [0.84, "probable_candidate"],
    [0.85, "strong_candidate_requires_review"],
    [1,    "strong_candidate_requires_review"],
  ];

  for (const [score, expectedStatus] of scoreCases) {
    it(`returns "${expectedStatus}" for combinedScore ${score}`, () => {
      const result = determineCombinedAssessmentStatus(
        score,
        makeMorphologyStub(1),
        makePlausibilityStub("high_plausibility")
      );
      expect(result).toBe(expectedStatus);
    });
  }
});

describe("getCombinedAssessmentReason", () => {
  const cases: [CombinedAssessmentStatus, string][] = [
    ["insufficient_data",             "insufficient_morphological_data"],
    ["unlikely_candidate",            "low_combined_support"],
    ["possible_candidate",            "possible_candidate_based_on_current_evidence"],
    ["probable_candidate",            "probable_candidate_based_on_morphology_and_plausibility"],
    ["strong_candidate_requires_review", "strong_candidate_but_requires_taxonomic_and_visual_review"],
  ];

  for (const [status, expectedReason] of cases) {
    it(`returns correct reason for "${status}"`, () => {
      expect(getCombinedAssessmentReason(status)).toBe(expectedReason);
    });
  }
});

describe("assessTaxonCandidate", () => {
  it("returns strong_candidate_requires_review for perfectly matching taxon", () => {
    const result = assessTaxonCandidate(matchingObserved, matchingContext, testTaxon);
    expect(result.morphology.morphologyScore).toBe(1);
    expect(result.plausibility.plausibilityScore).toBe(1);
    expect(result.combinedScore).toBe(1);
    expect(result.status).toBe("strong_candidate_requires_review");
    expect(result.reason).toBe("strong_candidate_but_requires_taxonomic_and_visual_review");
    expect(result.taxon.identity.taxonId).toBe("test-taxon-1");
  });

  it("returns insufficient_data when observedFeatures is empty", () => {
    const result = assessTaxonCandidate([], matchingContext, testTaxon);
    expect(result.morphology.featureResults).toHaveLength(0);
    expect(result.status).toBe("insufficient_data");
    expect(result.reason).toBe("insufficient_morphological_data");
  });

  it("returns unlikely_candidate when taxon does not occur in Germany", () => {
    const result = assessTaxonCandidate(matchingObserved, matchingContext, notInGermanyTaxon);
    expect(result.plausibility.status).toBe("not_plausible");
    expect(result.status).toBe("unlikely_candidate");
    expect(result.reason).toBe("low_combined_support");
  });
});

describe("assessTaxonCandidates", () => {
  it("sorts results descending by combinedScore", () => {
    const results = assessTaxonCandidates(matchingObserved, matchingContext, [
      testTaxon,
      testTaxon2,
    ]);
    expect(results).toHaveLength(2);
    expect(results[0].combinedScore).toBeGreaterThanOrEqual(results[1].combinedScore);
    expect(results[0].taxon.identity.taxonId).toBe("test-taxon-1");
  });

  it("returns empty list when taxa list is empty", () => {
    const results = assessTaxonCandidates(matchingObserved, matchingContext, []);
    expect(results).toHaveLength(0);
  });
});
