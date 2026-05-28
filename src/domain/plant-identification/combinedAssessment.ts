import { ObservedFeature } from "./featureScoring.js";
import { PlantTaxonProfile } from "./taxonProfile.js";
import {
  TaxonComparisonResult,
  compareObservedFeaturesWithTaxon,
} from "./taxonComparison.js";
import {
  ObservationContext,
  TaxonPlausibilityResult,
  evaluateTaxonPlausibility,
} from "./plausibilityScoring.js";

export type CombinedAssessmentStatus =
  | "insufficient_data"
  | "unlikely_candidate"
  | "possible_candidate"
  | "probable_candidate"
  | "strong_candidate_requires_review";

export type CombinedAssessmentResult = {
  taxon: PlantTaxonProfile;
  morphology: TaxonComparisonResult;
  plausibility: TaxonPlausibilityResult;
  combinedScore: number;
  status: CombinedAssessmentStatus;
  reason: string;
};

export function calculateCombinedScore(
  morphologyScore: number,
  plausibilityScore: number
): number {
  return morphologyScore * 0.75 + plausibilityScore * 0.25;
}

export function determineCombinedAssessmentStatus(
  combinedScore: number,
  morphology: TaxonComparisonResult,
  plausibility: TaxonPlausibilityResult
): CombinedAssessmentStatus {
  if (morphology.featureResults.length === 0) {
    return "insufficient_data";
  }
  if (plausibility.status === "not_plausible") {
    return "unlikely_candidate";
  }
  if (combinedScore < 0.4) {
    return "unlikely_candidate";
  }
  if (combinedScore < 0.7) {
    return "possible_candidate";
  }
  if (combinedScore < 0.85) {
    return "probable_candidate";
  }
  return "strong_candidate_requires_review";
}

export function getCombinedAssessmentReason(
  status: CombinedAssessmentStatus
): string {
  switch (status) {
    case "insufficient_data":
      return "insufficient_morphological_data";
    case "unlikely_candidate":
      return "low_combined_support";
    case "possible_candidate":
      return "possible_candidate_based_on_current_evidence";
    case "probable_candidate":
      return "probable_candidate_based_on_morphology_and_plausibility";
    case "strong_candidate_requires_review":
      return "strong_candidate_but_requires_taxonomic_and_visual_review";
  }
}

export function assessTaxonCandidate(
  observedFeatures: ObservedFeature[],
  context: ObservationContext,
  taxon: PlantTaxonProfile
): CombinedAssessmentResult {
  const morphology: TaxonComparisonResult = compareObservedFeaturesWithTaxon(
    observedFeatures,
    taxon
  );
  const plausibility: TaxonPlausibilityResult = evaluateTaxonPlausibility(
    taxon,
    context
  );
  const combinedScore: number = calculateCombinedScore(
    morphology.morphologyScore,
    plausibility.plausibilityScore
  );
  const status: CombinedAssessmentStatus = determineCombinedAssessmentStatus(
    combinedScore,
    morphology,
    plausibility
  );
  const reason: string = getCombinedAssessmentReason(status);

  return {
    taxon,
    morphology,
    plausibility,
    combinedScore,
    status,
    reason,
  };
}

export function assessTaxonCandidates(
  observedFeatures: ObservedFeature[],
  context: ObservationContext,
  taxa: PlantTaxonProfile[]
): CombinedAssessmentResult[] {
  return taxa
    .map((taxon) => assessTaxonCandidate(observedFeatures, context, taxon))
    .sort((a, b) => b.combinedScore - a.combinedScore);
}
