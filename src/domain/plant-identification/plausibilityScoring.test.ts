import { describe, it, expect } from "vitest";
import {
  floristicStatusToWeight,
  checkGermanyRelevance,
  checkFloristicStatus,
  checkHabitat,
  checkMoisture,
  checkLight,
  checkPhenology,
  calculatePlausibilityScore,
  determinePlausibilityStatus,
  getPlausibilityReason,
  evaluateTaxonPlausibility,
  PlausibilityCheckResult,
  PlausibilityStatus,
  ObservationContext,
} from "./plausibilityScoring.js";
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
  morphology: [],
  ecology: {
    habitatTypes: ["wiese", "waldrand"],
    moisture: ["frisch", "feucht"],
    light: ["vollsonnig", "halbschattig"],
  },
  phenology: {
    floweringMonths: ["mai", "juni"],
    fruitingMonths: ["juli", "august"],
  },
  visualReferences: {
    habitusImages: [],
    leafImages: [],
    flowerImages: [],
    fruitImages: [],
    detailImages: [],
  },
};

const notInGermanyTaxon: PlantTaxonProfile = {
  ...testTaxon,
  germanyRelevance: {
    occursInGermany: false,
    floristicStatus: "wildwachsend",
    statusWeight: 0,
  },
};

const kulturpflanzeTaxon: PlantTaxonProfile = {
  ...testTaxon,
  germanyRelevance: {
    occursInGermany: true,
    floristicStatus: "kulturpflanze_nachrangig",
    statusWeight: 0.3,
  },
};

const germanyResultPresent: PlausibilityCheckResult = {
  component: "germany_relevance",
  score: 1,
  maxScore: 1,
  reason: "occurs_in_germany",
};

const germanyResultAbsent: PlausibilityCheckResult = {
  component: "germany_relevance",
  score: 0,
  maxScore: 1,
  reason: "not_known_from_germany",
};

const contextFull: ObservationContext = {
  country: "Deutschland",
  habitatType: "wiese",
  moisture: "frisch",
  light: "vollsonnig",
  month: "mai",
};

const contextEmpty: ObservationContext = {
  country: "Deutschland",
};

describe("floristicStatusToWeight", () => {
  it('returns 1.0 for "wildwachsend"', () => {
    expect(floristicStatusToWeight("wildwachsend")).toBe(1.0);
  });
  it('returns 0.9 for "etablierter_neophyt"', () => {
    expect(floristicStatusToWeight("etablierter_neophyt")).toBe(0.9);
  });
  it('returns 0.7 for "haeufig_verwildernd"', () => {
    expect(floristicStatusToWeight("haeufig_verwildernd")).toBe(0.7);
  });
  it('returns 0.3 for "kulturpflanze_nachrangig"', () => {
    expect(floristicStatusToWeight("kulturpflanze_nachrangig")).toBe(0.3);
  });
});

describe("checkGermanyRelevance", () => {
  it("returns score 1 when taxon occurs in Germany", () => {
    const result = checkGermanyRelevance(testTaxon);
    expect(result.component).toBe("germany_relevance");
    expect(result.score).toBe(1);
    expect(result.maxScore).toBe(1);
    expect(result.reason).toBe("occurs_in_germany");
  });

  it("returns score 0 when taxon does not occur in Germany", () => {
    const result = checkGermanyRelevance(notInGermanyTaxon);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(1);
    expect(result.reason).toBe("not_known_from_germany");
  });
});

describe("checkFloristicStatus", () => {
  it('returns score 1 for "wildwachsend"', () => {
    const result = checkFloristicStatus(testTaxon);
    expect(result.component).toBe("floristic_status");
    expect(result.score).toBe(1);
    expect(result.maxScore).toBe(1);
    expect(result.reason).toBe("wildwachsend");
  });

  it('returns score 0.3 for "kulturpflanze_nachrangig"', () => {
    const result = checkFloristicStatus(kulturpflanzeTaxon);
    expect(result.score).toBe(0.3);
    expect(result.reason).toBe("kulturpflanze_nachrangig");
  });
});

describe("checkHabitat", () => {
  it("returns score 1 when habitatType matches", () => {
    const result = checkHabitat(testTaxon, { ...contextEmpty, habitatType: "wiese" });
    expect(result.score).toBe(1);
    expect(result.maxScore).toBe(1);
    expect(result.reason).toBe("habitat_matched");
  });

  it("returns score 0.5 when habitatType does not match", () => {
    const result = checkHabitat(testTaxon, { ...contextEmpty, habitatType: "moor" });
    expect(result.score).toBe(0.5);
    expect(result.maxScore).toBe(1);
    expect(result.reason).toBe("habitat_not_matched");
  });

  it("returns score 0 and maxScore 0 when habitatType is not provided", () => {
    const result = checkHabitat(testTaxon, contextEmpty);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(0);
    expect(result.reason).toBe("habitat_not_provided");
  });
});

describe("checkMoisture", () => {
  it("returns score 1 when moisture matches", () => {
    const result = checkMoisture(testTaxon, { ...contextEmpty, moisture: "frisch" });
    expect(result.score).toBe(1);
    expect(result.reason).toBe("moisture_matched");
  });

  it("returns score 0.5 when moisture does not match", () => {
    const result = checkMoisture(testTaxon, { ...contextEmpty, moisture: "trocken" });
    expect(result.score).toBe(0.5);
    expect(result.reason).toBe("moisture_not_matched");
  });

  it("returns score 0 and maxScore 0 when moisture is not provided", () => {
    const result = checkMoisture(testTaxon, contextEmpty);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(0);
    expect(result.reason).toBe("moisture_not_provided");
  });
});

describe("checkLight", () => {
  it("returns score 1 when light matches", () => {
    const result = checkLight(testTaxon, { ...contextEmpty, light: "vollsonnig" });
    expect(result.score).toBe(1);
    expect(result.reason).toBe("light_matched");
  });

  it("returns score 0.5 when light does not match", () => {
    const result = checkLight(testTaxon, { ...contextEmpty, light: "schattig" });
    expect(result.score).toBe(0.5);
    expect(result.reason).toBe("light_not_matched");
  });

  it("returns score 0 and maxScore 0 when light is not provided", () => {
    const result = checkLight(testTaxon, contextEmpty);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(0);
    expect(result.reason).toBe("light_not_provided");
  });
});

describe("checkPhenology", () => {
  it("returns score 1 for month in floweringMonths", () => {
    const result = checkPhenology(testTaxon, { ...contextEmpty, month: "mai" });
    expect(result.score).toBe(1);
    expect(result.reason).toBe("phenology_matched");
  });

  it("returns score 1 for month in fruitingMonths", () => {
    const result = checkPhenology(testTaxon, { ...contextEmpty, month: "august" });
    expect(result.score).toBe(1);
    expect(result.reason).toBe("phenology_matched");
  });

  it("returns score 0.5 for month not in flowering or fruiting", () => {
    const result = checkPhenology(testTaxon, { ...contextEmpty, month: "dezember" });
    expect(result.score).toBe(0.5);
    expect(result.reason).toBe("phenology_not_matched");
  });

  it("returns score 0 and maxScore 0 when month is not provided", () => {
    const result = checkPhenology(testTaxon, contextEmpty);
    expect(result.score).toBe(0);
    expect(result.maxScore).toBe(0);
    expect(result.reason).toBe("month_not_provided");
  });
});

describe("calculatePlausibilityScore", () => {
  it("returns 0.75 for mixed result list", () => {
    const results: PlausibilityCheckResult[] = [
      { component: "germany_relevance", score: 1,   maxScore: 1, reason: "occurs_in_germany" },
      { component: "habitat",           score: 0.5, maxScore: 1, reason: "habitat_not_matched" },
      { component: "moisture",          score: 0,   maxScore: 0, reason: "moisture_not_provided" },
    ];
    expect(calculatePlausibilityScore(results)).toBe(0.75);
  });

  it("returns 0 for empty list", () => {
    expect(calculatePlausibilityScore([])).toBe(0);
  });

  it("returns 0 when maxScore sum is 0", () => {
    const results: PlausibilityCheckResult[] = [
      { component: "moisture", score: 0, maxScore: 0, reason: "moisture_not_provided" },
    ];
    expect(calculatePlausibilityScore(results)).toBe(0);
  });
});

describe("determinePlausibilityStatus", () => {
  it("returns not_plausible when germanyResult score is 0", () => {
    expect(determinePlausibilityStatus(1, germanyResultAbsent)).toBe("not_plausible");
  });

  it("returns low_plausibility for score 0.39", () => {
    expect(determinePlausibilityStatus(0.39, germanyResultPresent)).toBe("low_plausibility");
  });

  it("returns moderate_plausibility for score 0.4", () => {
    expect(determinePlausibilityStatus(0.4, germanyResultPresent)).toBe("moderate_plausibility");
  });

  it("returns moderate_plausibility for score 0.74", () => {
    expect(determinePlausibilityStatus(0.74, germanyResultPresent)).toBe("moderate_plausibility");
  });

  it("returns high_plausibility for score 0.75", () => {
    expect(determinePlausibilityStatus(0.75, germanyResultPresent)).toBe("high_plausibility");
  });

  it("returns high_plausibility for score 1", () => {
    expect(determinePlausibilityStatus(1, germanyResultPresent)).toBe("high_plausibility");
  });
});

describe("getPlausibilityReason", () => {
  const cases: [PlausibilityStatus, string][] = [
    ["not_plausible",         "not_plausible_for_germany"],
    ["low_plausibility",      "low_contextual_plausibility"],
    ["moderate_plausibility", "moderate_contextual_plausibility"],
    ["high_plausibility",     "high_contextual_plausibility"],
  ];

  for (const [status, expectedReason] of cases) {
    it(`returns "${expectedReason}" for "${status}"`, () => {
      expect(getPlausibilityReason(status)).toBe(expectedReason);
    });
  }
});

describe("evaluateTaxonPlausibility", () => {
  it("returns high_plausibility for fully matching context", () => {
    const result = evaluateTaxonPlausibility(testTaxon, contextFull);
    expect(result.componentResults).toHaveLength(6);
    expect(result.plausibilityScore).toBe(1);
    expect(result.status).toBe("high_plausibility");
    expect(result.reason).toBe("high_contextual_plausibility");
  });

  it("returns not_plausible for taxon not occurring in Germany", () => {
    const result = evaluateTaxonPlausibility(notInGermanyTaxon, contextFull);
    expect(result.status).toBe("not_plausible");
    expect(result.reason).toBe("not_plausible_for_germany");
  });
});
