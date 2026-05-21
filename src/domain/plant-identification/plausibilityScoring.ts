import { PlantTaxonProfile, FloristicStatus } from "./taxonProfile.js";

export type ObservationContext = {
  country: "Deutschland";
  habitatType?: string;
  moisture?: string;
  light?: string;
  month?: string;
};

export type PlausibilityComponent =
  | "germany_relevance"
  | "floristic_status"
  | "habitat"
  | "moisture"
  | "light"
  | "phenology";

export type PlausibilityCheckResult = {
  component: PlausibilityComponent;
  score: number;
  maxScore: number;
  reason: string;
};

export type PlausibilityStatus =
  | "not_plausible"
  | "low_plausibility"
  | "moderate_plausibility"
  | "high_plausibility";

export type TaxonPlausibilityResult = {
  taxon: PlantTaxonProfile;
  componentResults: PlausibilityCheckResult[];
  plausibilityScore: number;
  status: PlausibilityStatus;
  reason: string;
};

export function floristicStatusToWeight(status: FloristicStatus): number {
  switch (status) {
    case "wildwachsend":             return 1.0;
    case "etablierter_neophyt":      return 0.9;
    case "haeufig_verwildernd":      return 0.7;
    case "kulturpflanze_nachrangig": return 0.3;
  }
}

export function checkGermanyRelevance(taxon: PlantTaxonProfile): PlausibilityCheckResult {
  if (taxon.germanyRelevance.occursInGermany) {
    return {
      component: "germany_relevance",
      score: 1,
      maxScore: 1,
      reason: "occurs_in_germany",
    };
  }
  return {
    component: "germany_relevance",
    score: 0,
    maxScore: 1,
    reason: "not_known_from_germany",
  };
}

export function checkFloristicStatus(taxon: PlantTaxonProfile): PlausibilityCheckResult {
  return {
    component: "floristic_status",
    score: floristicStatusToWeight(taxon.germanyRelevance.floristicStatus),
    maxScore: 1,
    reason: taxon.germanyRelevance.floristicStatus,
  };
}

export function checkHabitat(
  taxon: PlantTaxonProfile,
  context: ObservationContext
): PlausibilityCheckResult {
  if (context.habitatType === undefined) {
    return {
      component: "habitat",
      score: 0,
      maxScore: 0,
      reason: "habitat_not_provided",
    };
  }
  if (taxon.ecology.habitatTypes.includes(context.habitatType)) {
    return {
      component: "habitat",
      score: 1,
      maxScore: 1,
      reason: "habitat_matched",
    };
  }
  return {
    component: "habitat",
    score: 0.5,
    maxScore: 1,
    reason: "habitat_not_matched",
  };
}

export function checkMoisture(
  taxon: PlantTaxonProfile,
  context: ObservationContext
): PlausibilityCheckResult {
  if (context.moisture === undefined) {
    return {
      component: "moisture",
      score: 0,
      maxScore: 0,
      reason: "moisture_not_provided",
    };
  }
  if (taxon.ecology.moisture.includes(context.moisture)) {
    return {
      component: "moisture",
      score: 1,
      maxScore: 1,
      reason: "moisture_matched",
    };
  }
  return {
    component: "moisture",
    score: 0.5,
    maxScore: 1,
    reason: "moisture_not_matched",
  };
}

export function checkLight(
  taxon: PlantTaxonProfile,
  context: ObservationContext
): PlausibilityCheckResult {
  if (context.light === undefined) {
    return {
      component: "light",
      score: 0,
      maxScore: 0,
      reason: "light_not_provided",
    };
  }
  if (taxon.ecology.light.includes(context.light)) {
    return {
      component: "light",
      score: 1,
      maxScore: 1,
      reason: "light_matched",
    };
  }
  return {
    component: "light",
    score: 0.5,
    maxScore: 1,
    reason: "light_not_matched",
  };
}

export function checkPhenology(
  taxon: PlantTaxonProfile,
  context: ObservationContext
): PlausibilityCheckResult {
  if (context.month === undefined) {
    return {
      component: "phenology",
      score: 0,
      maxScore: 0,
      reason: "month_not_provided",
    };
  }
  const inFlowering = taxon.phenology.floweringMonths.includes(context.month);
  const inFruiting = taxon.phenology.fruitingMonths.includes(context.month);
  if (inFlowering || inFruiting) {
    return {
      component: "phenology",
      score: 1,
      maxScore: 1,
      reason: "phenology_matched",
    };
  }
  return {
    component: "phenology",
    score: 0.5,
    maxScore: 1,
    reason: "phenology_not_matched",
  };
}

export function calculatePlausibilityScore(results: PlausibilityCheckResult[]): number {
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

export function determinePlausibilityStatus(
  score: number,
  germanyResult: PlausibilityCheckResult
): PlausibilityStatus {
  if (germanyResult.score === 0) {
    return "not_plausible";
  }
  if (score < 0.4) {
    return "low_plausibility";
  }
  if (score < 0.75) {
    return "moderate_plausibility";
  }
  return "high_plausibility";
}

export function getPlausibilityReason(status: PlausibilityStatus): string {
  switch (status) {
    case "not_plausible":         return "not_plausible_for_germany";
    case "low_plausibility":      return "low_contextual_plausibility";
    case "moderate_plausibility": return "moderate_contextual_plausibility";
    case "high_plausibility":     return "high_contextual_plausibility";
  }
}

export function evaluateTaxonPlausibility(
  taxon: PlantTaxonProfile,
  context: ObservationContext
): TaxonPlausibilityResult {
  const germanyResult = checkGermanyRelevance(taxon);
  const componentResults: PlausibilityCheckResult[] = [
    germanyResult,
    checkFloristicStatus(taxon),
    checkHabitat(taxon, context),
    checkMoisture(taxon, context),
    checkLight(taxon, context),
    checkPhenology(taxon, context),
  ];

  const plausibilityScore = calculatePlausibilityScore(componentResults);
  const status = determinePlausibilityStatus(plausibilityScore, germanyResult);
  const reason = getPlausibilityReason(status);

  return {
    taxon,
    componentResults,
    plausibilityScore,
    status,
    reason,
  };
}
