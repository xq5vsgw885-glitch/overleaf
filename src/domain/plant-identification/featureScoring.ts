import {
  DiagnosticWeight,
  MorphologicalFeature,
  MORPHOLOGICAL_FEATURE_MATRIX,
  getFeatureById,
} from "./morphologicalFeatureMatrix.js";

export type ObservedFeature = {
  featureId: string;
  observedValue: string;
  confidence: number;
  source: "photo" | "user_input" | "derived";
  isVisible: boolean;
};

export type TaxonFeatureProfile = {
  featureId: string;
  acceptedValues: string[];
  requiredForStrongIdentification: boolean;
};

export type FeatureComparisonResult = {
  featureId: string;
  matched: boolean;
  score: number;
  maxScore: number;
  diagnosticWeight: DiagnosticWeight;
  reason: string;
};

export function diagnosticWeightToNumber(weight: DiagnosticWeight): number {
  switch (weight) {
    case "niedrig":   return 1;
    case "mittel":    return 2;
    case "hoch":      return 3;
    case "sehr_hoch": return 4;
  }
}

export function compareFeature(
  observed: ObservedFeature,
  profile: TaxonFeatureProfile
): FeatureComparisonResult {
  const feature: MorphologicalFeature | undefined = getFeatureById(observed.featureId);

  if (feature === undefined) {
    return {
      featureId: observed.featureId,
      matched: false,
      score: 0,
      maxScore: 0,
      diagnosticWeight: "niedrig",
      reason: "unknown_feature",
    };
  }

  const weightValue = diagnosticWeightToNumber(feature.diagnosticWeight);

  if (!observed.isVisible) {
    return {
      featureId: observed.featureId,
      matched: false,
      score: 0,
      maxScore: weightValue,
      diagnosticWeight: feature.diagnosticWeight,
      reason: "feature_not_visible",
    };
  }

  if (profile.acceptedValues.includes(observed.observedValue)) {
    return {
      featureId: observed.featureId,
      matched: true,
      score: weightValue * observed.confidence,
      maxScore: weightValue,
      diagnosticWeight: feature.diagnosticWeight,
      reason: "matched",
    };
  }

  return {
    featureId: observed.featureId,
    matched: false,
    score: 0,
    maxScore: weightValue,
    diagnosticWeight: feature.diagnosticWeight,
    reason: "value_mismatch",
  };
}

export function compareFeatureSet(
  observedFeatures: ObservedFeature[],
  taxonProfile: TaxonFeatureProfile[]
): FeatureComparisonResult[] {
  const results: FeatureComparisonResult[] = [];

  for (const profileEntry of taxonProfile) {
    const observed = observedFeatures.find(
      (o) => o.featureId === profileEntry.featureId
    );
    if (observed !== undefined) {
      results.push(compareFeature(observed, profileEntry));
    }
  }

  return results;
}

export function calculateFeatureScore(results: FeatureComparisonResult[]): number {
  if (results.length === 0) {
    return 0;
  }

  const scoreSum = results.reduce((sum, r) => sum + r.score, 0);
  const maxScoreSum = results.reduce((sum, r) => sum + r.maxScore, 0);

  if (maxScoreSum === 0) {
    return 0;
  }

  return scoreSum / maxScoreSum;
}

// Re-export to keep MORPHOLOGICAL_FEATURE_MATRIX available to consumers of this module
export { MORPHOLOGICAL_FEATURE_MATRIX };
