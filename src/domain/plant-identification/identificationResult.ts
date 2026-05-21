import {
  CombinedAssessmentResult,
  CombinedAssessmentStatus,
} from "./combinedAssessment.js";
import { PlantTaxonProfile, TaxonomicRank } from "./taxonProfile.js";

export type IdentificationConfidence =
  | "insufficient"
  | "low"
  | "moderate"
  | "high_but_not_final";

export type IdentificationOutputRank =
  | "familie"
  | "gattung"
  | "art"
  | "nicht_bestimmbar";

export type EvidenceSection = {
  observations: string[];
  calculations: string[];
  interpretation: string[];
  uncertainty: string[];
};

export type MissingEvidenceHint = {
  featureId: string;
  message: string;
  recommendedPhotoType?: string;
};

export type IdentificationCandidate = {
  taxon: PlantTaxonProfile;
  assessment: CombinedAssessmentResult;
  confidence: IdentificationConfidence;
  outputRank: IdentificationOutputRank;
  evidence: EvidenceSection;
  missingEvidence: MissingEvidenceHint[];
};

export type IdentificationResult = {
  primaryCandidate?: IdentificationCandidate;
  alternativeCandidates: IdentificationCandidate[];
  resultSummary: string;
  isFinalSpeciesIdentification: false;
  visualControlPending: boolean;
};

export function confidenceFromCombinedStatus(
  status: CombinedAssessmentStatus
): IdentificationConfidence {
  switch (status) {
    case "insufficient_data":
      return "insufficient";
    case "unlikely_candidate":
      return "low";
    case "possible_candidate":
      return "moderate";
    case "probable_candidate":
      return "moderate";
    case "strong_candidate_requires_review":
      return "high_but_not_final";
  }
}

export function outputRankFromTaxonRank(
  rank: TaxonomicRank
): IdentificationOutputRank {
  switch (rank) {
    case "familie": return "familie";
    case "gattung": return "gattung";
    case "art":     return "art";
  }
}

export function buildEvidenceSection(
  assessment: CombinedAssessmentResult
): EvidenceSection {
  return {
    observations: [
      "observed_features_compared",
      "context_plausibility_evaluated",
    ],
    calculations: [
      `morphology_score:${assessment.morphology.morphologyScore}`,
      `plausibility_score:${assessment.plausibility.plausibilityScore}`,
      `combined_score:${assessment.combinedScore}`,
    ],
    interpretation: [
      assessment.reason,
      assessment.morphology.reason,
      assessment.plausibility.reason,
    ],
    uncertainty: [
      "not_final_species_identification",
      "visual_control_not_performed",
      "taxonomic_review_required",
    ],
  };
}

export function buildMissingEvidenceHints(
  assessment: CombinedAssessmentResult
): MissingEvidenceHint[] {
  if (assessment.morphology.featureResults.length === 0) {
    return [
      {
        featureId: "unknown",
        message: "Keine auswertbaren morphologischen Merkmale vorhanden.",
        recommendedPhotoType: "habitus",
      },
    ];
  }
  return [];
}

export function buildIdentificationCandidate(
  assessment: CombinedAssessmentResult
): IdentificationCandidate {
  return {
    taxon: assessment.taxon,
    assessment,
    confidence: confidenceFromCombinedStatus(assessment.status),
    outputRank: outputRankFromTaxonRank(assessment.taxon.identity.rank),
    evidence: buildEvidenceSection(assessment),
    missingEvidence: buildMissingEvidenceHints(assessment),
  };
}

export function buildIdentificationResult(
  assessments: CombinedAssessmentResult[]
): IdentificationResult {
  if (assessments.length === 0) {
    return {
      primaryCandidate: undefined,
      alternativeCandidates: [],
      resultSummary: "no_candidates_available",
      isFinalSpeciesIdentification: false,
      visualControlPending: true,
    };
  }

  const candidates: IdentificationCandidate[] = assessments.map(
    buildIdentificationCandidate
  );

  const primaryCandidate = candidates[0];
  const alternativeCandidates = candidates.slice(1, 5);

  let resultSummary: string;
  if (primaryCandidate.confidence === "high_but_not_final") {
    resultSummary = "strong_candidate_requires_review";
  } else if (primaryCandidate.confidence === "moderate") {
    resultSummary = "candidate_plausible_but_not_final";
  } else if (primaryCandidate.confidence === "low") {
    resultSummary = "weak_candidate";
  } else {
    resultSummary = "insufficient_data";
  }

  return {
    primaryCandidate,
    alternativeCandidates,
    resultSummary,
    isFinalSpeciesIdentification: false,
    visualControlPending: true,
  };
}
