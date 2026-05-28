import {
  ObservedFeature,
  FeatureComparisonResult,
  compareFeatureSet,
  calculateFeatureScore,
} from "./featureScoring.js";

import { PlantTaxonProfile } from "./taxonProfile.js";

export type TaxonComparisonStatus =
  | "no_observable_features"
  | "low_match"
  | "moderate_match"
  | "high_match";

export type TaxonComparisonResult = {
  taxon: PlantTaxonProfile;
  featureResults: FeatureComparisonResult[];
  morphologyScore: number;
  status: TaxonComparisonStatus;
  reason: string;
};

export function determineTaxonComparisonStatus(
  score: number,
  featureResults: FeatureComparisonResult[]
): TaxonComparisonStatus {
  if (featureResults.length === 0) {
    return "no_observable_features";
  }
  if (score < 0.4) {
    return "low_match";
  }
  if (score < 0.75) {
    return "moderate_match";
  }
  return "high_match";
}

export function getTaxonComparisonReason(status: TaxonComparisonStatus): string {
  switch (status) {
    case "no_observable_features":
      return "no_observable_features";
    case "low_match":
      return "low_morphological_match";
    case "moderate_match":
      return "moderate_morphological_match";
    case "high_match":
      return "high_morphological_match";
  }
}

export function compareObservedFeaturesWithTaxon(
  observedFeatures: ObservedFeature[],
  taxon: PlantTaxonProfile
): TaxonComparisonResult {
  const featureResults: FeatureComparisonResult[] = compareFeatureSet(
    observedFeatures,
    taxon.morphology
  );

  const morphologyScore: number = calculateFeatureScore(featureResults);
  const status: TaxonComparisonStatus = determineTaxonComparisonStatus(
    morphologyScore,
    featureResults
  );
  const reason: string = getTaxonComparisonReason(status);

  return {
    taxon,
    featureResults,
    morphologyScore,
    status,
    reason,
  };
}
