import { describe, it, expect } from "vitest";
import {
  confidenceFromCombinedStatus,
  outputRankFromTaxonRank,
  buildEvidenceSection,
  buildMissingEvidenceHints,
  buildIdentificationCandidate,
  buildIdentificationResult,
} from "./identificationResult.js";
import { CombinedAssessmentResult, CombinedAssessmentStatus } from "./combinedAssessment.js";
import { PlantTaxonProfile } from "./taxonProfile.js";
import { TaxonomicRank } from "./taxonProfile.js";

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

const baseAssessment: CombinedAssessmentResult = {
  taxon: testTaxon,
  morphology: {
    taxon: testTaxon,
    featureResults: [
      {
        featureId: "blattstellung",
        matched: true,
        score: 3,
        maxScore: 3,
        diagnosticWeight: "hoch",
        reason: "matched",
      },
    ],
    morphologyScore: 1,
    status: "high_match",
    reason: "high_morphological_match",
  },
  plausibility: {
    taxon: testTaxon,
    componentResults: [],
    plausibilityScore: 1,
    status: "high_plausibility",
    reason: "high_contextual_plausibility",
  },
  combinedScore: 1,
  status: "strong_candidate_requires_review",
  reason: "strong_candidate_but_requires_taxonomic_and_visual_review",
};

function assessmentWithStatus(status: CombinedAssessmentStatus): CombinedAssessmentResult {
  return { ...baseAssessment, status };
}

function assessmentForTaxonId(id: string): CombinedAssessmentResult {
  return {
    ...baseAssessment,
    taxon: {
      ...testTaxon,
      identity: { ...testTaxon.identity, taxonId: id },
    },
  };
}

describe("confidenceFromCombinedStatus", () => {
  const cases: [CombinedAssessmentStatus, string][] = [
    ["insufficient_data",             "insufficient"],
    ["unlikely_candidate",            "low"],
    ["possible_candidate",            "moderate"],
    ["probable_candidate",            "moderate"],
    ["strong_candidate_requires_review", "high_but_not_final"],
  ];

  for (const [status, expected] of cases) {
    it(`maps "${status}" to "${expected}"`, () => {
      expect(confidenceFromCombinedStatus(status)).toBe(expected);
    });
  }
});

describe("outputRankFromTaxonRank", () => {
  const cases: [TaxonomicRank, string][] = [
    ["familie", "familie"],
    ["gattung", "gattung"],
    ["art",     "art"],
  ];

  for (const [rank, expected] of cases) {
    it(`maps "${rank}" to "${expected}"`, () => {
      expect(outputRankFromTaxonRank(rank)).toBe(expected);
    });
  }
});

describe("buildEvidenceSection", () => {
  it("separates observations, calculations, interpretation and uncertainty", () => {
    const evidence = buildEvidenceSection(baseAssessment);

    expect(evidence.observations).toContain("observed_features_compared");
    expect(evidence.observations).toContain("context_plausibility_evaluated");

    expect(evidence.calculations).toContain("morphology_score:1");
    expect(evidence.calculations).toContain("plausibility_score:1");
    expect(evidence.calculations).toContain("combined_score:1");

    expect(evidence.interpretation).toContain(baseAssessment.reason);
    expect(evidence.interpretation).toContain(baseAssessment.morphology.reason);
    expect(evidence.interpretation).toContain(baseAssessment.plausibility.reason);

    expect(evidence.uncertainty).toContain("not_final_species_identification");
    expect(evidence.uncertainty).toContain("visual_control_not_performed");
    expect(evidence.uncertainty).toContain("taxonomic_review_required");
  });
});

describe("buildMissingEvidenceHints", () => {
  it("returns empty array when featureResults are present", () => {
    const hints = buildMissingEvidenceHints(baseAssessment);
    expect(hints).toHaveLength(0);
  });

  it("returns one hint when featureResults is empty", () => {
    const emptyMorphologyAssessment: CombinedAssessmentResult = {
      ...baseAssessment,
      morphology: {
        ...baseAssessment.morphology,
        featureResults: [],
      },
    };
    const hints = buildMissingEvidenceHints(emptyMorphologyAssessment);
    expect(hints).toHaveLength(1);
    expect(hints[0].featureId).toBe("unknown");
    expect(hints[0].message).toBe("Keine auswertbaren morphologischen Merkmale vorhanden.");
    expect(hints[0].recommendedPhotoType).toBe("habitus");
  });
});

describe("buildIdentificationCandidate", () => {
  it("builds correct candidate from strong_candidate_requires_review assessment", () => {
    const candidate = buildIdentificationCandidate(baseAssessment);
    expect(candidate.taxon.identity.taxonId).toBe("test-taxon-1");
    expect(candidate.confidence).toBe("high_but_not_final");
    expect(candidate.outputRank).toBe("art");
    expect(candidate.evidence.uncertainty).toContain("not_final_species_identification");
    expect(candidate.missingEvidence).toHaveLength(0);
  });
});

describe("buildIdentificationResult", () => {
  it("returns no-candidate result for empty assessment list", () => {
    const result = buildIdentificationResult([]);
    expect(result.primaryCandidate).toBeUndefined();
    expect(result.alternativeCandidates).toHaveLength(0);
    expect(result.resultSummary).toBe("no_candidates_available");
    expect(result.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControlPending).toBe(true);
  });

  it("returns strong_candidate_requires_review summary for high_but_not_final confidence", () => {
    const result = buildIdentificationResult([baseAssessment]);
    expect(result.primaryCandidate).toBeDefined();
    expect(result.primaryCandidate!.confidence).toBe("high_but_not_final");
    expect(result.alternativeCandidates).toHaveLength(0);
    expect(result.resultSummary).toBe("strong_candidate_requires_review");
    expect(result.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControlPending).toBe(true);
  });

  it("returns candidate_plausible_but_not_final summary for moderate confidence", () => {
    const result = buildIdentificationResult([assessmentWithStatus("possible_candidate")]);
    expect(result.primaryCandidate!.confidence).toBe("moderate");
    expect(result.resultSummary).toBe("candidate_plausible_but_not_final");
    expect(result.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControlPending).toBe(true);
  });

  it("returns weak_candidate summary for low confidence", () => {
    const result = buildIdentificationResult([assessmentWithStatus("unlikely_candidate")]);
    expect(result.primaryCandidate!.confidence).toBe("low");
    expect(result.resultSummary).toBe("weak_candidate");
    expect(result.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControlPending).toBe(true);
  });

  it("returns insufficient_data summary for insufficient confidence", () => {
    const result = buildIdentificationResult([assessmentWithStatus("insufficient_data")]);
    expect(result.primaryCandidate!.confidence).toBe("insufficient");
    expect(result.resultSummary).toBe("insufficient_data");
    expect(result.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControlPending).toBe(true);
  });

  it("limits alternativeCandidates to 4 when 6 assessments are provided", () => {
    const sixAssessments = [1, 2, 3, 4, 5, 6].map((n) =>
      assessmentForTaxonId(`test-taxon-${n}`)
    );
    const result = buildIdentificationResult(sixAssessments);
    expect(result.primaryCandidate).toBeDefined();
    expect(result.primaryCandidate!.taxon.identity.taxonId).toBe("test-taxon-1");
    expect(result.alternativeCandidates).toHaveLength(4);
    expect(result.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControlPending).toBe(true);
  });
});
