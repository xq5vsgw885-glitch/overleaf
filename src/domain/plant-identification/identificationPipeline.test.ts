import { describe, it, expect } from "vitest";
import { runIdentificationPipeline } from "./identificationPipeline.js";
import { PlantTaxonProfile } from "./taxonProfile.js";
import { ObservedFeature } from "./featureScoring.js";
import { ObservationContext } from "./plausibilityScoring.js";

const testTaxon1: PlantTaxonProfile = {
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
  ...testTaxon1,
  identity: {
    taxonId: "test-taxon-2",
    scientificName: "Test taxon 2",
    germanName: "Testpflanze2",
    family: "Testaceae2",
    genus: "Testgenus2",
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
  ...testTaxon1,
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

describe("runIdentificationPipeline", () => {
  it("returns empty result for empty candidateTaxa list", () => {
    const result = runIdentificationPipeline({
      observedFeatures: [],
      observationContext: { country: "Deutschland" },
      candidateTaxa: [],
    });

    expect(result.assessments).toHaveLength(0);
    expect(result.identification.primaryCandidate).toBeUndefined();
    expect(result.identification.alternativeCandidates).toHaveLength(0);
    expect(result.identification.resultSummary).toBe("no_candidates_available");
    expect(result.identification.isFinalSpeciesIdentification).toBe(false);
    expect(result.identification.visualControlPending).toBe(true);
    expect(result.identificationWithVisualControl.visualControl.status).toBe("not_performed");
    expect(result.identificationWithVisualControl.visualControl.reason).toBe(
      "visual_control_not_performed"
    );
  });

  it("returns strong_candidate_requires_review for perfectly matching taxon", () => {
    const result = runIdentificationPipeline({
      observedFeatures: matchingObserved,
      observationContext: matchingContext,
      candidateTaxa: [testTaxon1],
    });

    expect(result.assessments).toHaveLength(1);
    expect(result.assessments[0].taxon.identity.taxonId).toBe("test-taxon-1");
    expect(result.assessments[0].combinedScore).toBe(1);
    expect(result.assessments[0].status).toBe("strong_candidate_requires_review");

    expect(result.identification.primaryCandidate).toBeDefined();
    expect(result.identification.primaryCandidate!.taxon.identity.taxonId).toBe("test-taxon-1");
    expect(result.identification.primaryCandidate!.confidence).toBe("high_but_not_final");
    expect(result.identification.resultSummary).toBe("strong_candidate_requires_review");
    expect(result.identification.isFinalSpeciesIdentification).toBe(false);
    expect(result.identification.visualControlPending).toBe(true);
    expect(result.identificationWithVisualControl.visualControl.status).toBe("not_performed");
  });

  it("sorts two taxa descending by combinedScore", () => {
    const result = runIdentificationPipeline({
      observedFeatures: matchingObserved,
      observationContext: matchingContext,
      candidateTaxa: [testTaxon1, testTaxon2],
    });

    expect(result.assessments).toHaveLength(2);
    expect(result.assessments[0].combinedScore).toBeGreaterThanOrEqual(
      result.assessments[1].combinedScore
    );
    expect(result.assessments[0].taxon.identity.taxonId).toBe("test-taxon-1");

    expect(result.identification.primaryCandidate!.taxon.identity.taxonId).toBe("test-taxon-1");
    expect(result.identification.alternativeCandidates).toHaveLength(1);
    expect(result.identification.isFinalSpeciesIdentification).toBe(false);
    expect(result.identification.visualControlPending).toBe(true);
    expect(result.identificationWithVisualControl.visualControl.status).toBe("not_performed");
  });

  it("returns unlikely_candidate for taxon not occurring in Germany", () => {
    const result = runIdentificationPipeline({
      observedFeatures: matchingObserved,
      observationContext: matchingContext,
      candidateTaxa: [notInGermanyTaxon],
    });

    expect(result.assessments).toHaveLength(1);
    expect(result.assessments[0].plausibility.status).toBe("not_plausible");
    expect(result.assessments[0].status).toBe("unlikely_candidate");

    expect(result.identification.primaryCandidate).toBeDefined();
    expect(result.identification.primaryCandidate!.confidence).toBe("low");
    expect(result.identification.resultSummary).toBe("weak_candidate");
    expect(result.identification.isFinalSpeciesIdentification).toBe(false);
    expect(result.identification.visualControlPending).toBe(true);
    expect(result.identificationWithVisualControl.visualControl.status).toBe("not_performed");
  });

  it("returns insufficient_data when no observed features are provided", () => {
    const result = runIdentificationPipeline({
      observedFeatures: [],
      observationContext: matchingContext,
      candidateTaxa: [testTaxon1],
    });

    expect(result.assessments).toHaveLength(1);
    expect(result.assessments[0].morphology.featureResults).toHaveLength(0);
    expect(result.assessments[0].status).toBe("insufficient_data");

    expect(result.identification.primaryCandidate).toBeDefined();
    expect(result.identification.primaryCandidate!.confidence).toBe("insufficient");
    expect(result.identification.resultSummary).toBe("insufficient_data");
    expect(result.identification.isFinalSpeciesIdentification).toBe(false);
    expect(result.identification.visualControlPending).toBe(true);
    expect(result.identificationWithVisualControl.visualControl.status).toBe("not_performed");
  });
});
