export type TaxonSeedSourceType =
  | "Rothmaler"
  | "Strasburger"
  | "extern_nicht_zugelassen";

export type TaxonSeedPolicyStatus = "allowed" | "blocked";

export type TaxonSeedPolicyCheck = {
  status: TaxonSeedPolicyStatus;
  reason: string;
};

export type TaxonSeedPolicy = {
  allowedSources: TaxonSeedSourceType[];
  requiresSourceCitation: true;
  requiresGermanyRelevance: true;
  allowsUncitedTaxa: false;
  allowsImageOnlyTaxa: false;
  allowsFinalSpeciesIdentificationFromSeedAlone: false;
};

export const PLANT_TAXON_SEED_POLICY: TaxonSeedPolicy = {
  allowedSources: ["Rothmaler", "Strasburger"],
  requiresSourceCitation: true,
  requiresGermanyRelevance: true,
  allowsUncitedTaxa: false,
  allowsImageOnlyTaxa: false,
  allowsFinalSpeciesIdentificationFromSeedAlone: false,
};

export function isAllowedTaxonSeedSource(source: TaxonSeedSourceType): boolean {
  return (
    source === "Rothmaler" || source === "Strasburger"
  );
}

export function checkTaxonSeedSource(source: TaxonSeedSourceType): TaxonSeedPolicyCheck {
  if (isAllowedTaxonSeedSource(source)) {
    return { status: "allowed", reason: "allowed_source" };
  }
  return { status: "blocked", reason: "source_not_allowed" };
}

export function checkTaxonSeedCitation(hasCitation: boolean): TaxonSeedPolicyCheck {
  if (hasCitation) {
    return { status: "allowed", reason: "citation_present" };
  }
  return { status: "blocked", reason: "citation_required" };
}

export function checkTaxonSeedGermanyRelevance(isGermanyRelevant: boolean): TaxonSeedPolicyCheck {
  if (isGermanyRelevant) {
    return { status: "allowed", reason: "germany_relevance_present" };
  }
  return { status: "blocked", reason: "germany_relevance_required" };
}

export function checkTaxonSeedGermanyConsistency(
  germanyRelevant: boolean,
  occursInGermany: boolean
): TaxonSeedPolicyCheck {
  if (germanyRelevant === occursInGermany) {
    return { status: "allowed", reason: "germany_consistency_confirmed" };
  }
  return { status: "blocked", reason: "germany_relevance_inconsistent" };
}

export function checkTaxonSeedMorphologyPresent(morphologyCount: number): TaxonSeedPolicyCheck {
  if (morphologyCount > 0) {
    return { status: "allowed", reason: "morphology_present" };
  }
  return { status: "blocked", reason: "morphology_required" };
}

export function checkTaxonSeedReviewNote(reviewNote: string): TaxonSeedPolicyCheck {
  if (reviewNote.trim().length > 0) {
    return { status: "allowed", reason: "review_note_present" };
  }
  return { status: "blocked", reason: "review_note_required" };
}

export function checkTaxonSeedAddedAt(addedAt: string): TaxonSeedPolicyCheck {
  if (addedAt.trim().length > 0) {
    return { status: "allowed", reason: "addedAt_present" };
  }
  return { status: "blocked", reason: "addedAt_required" };
}
