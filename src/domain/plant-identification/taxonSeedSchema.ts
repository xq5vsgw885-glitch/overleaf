import { PlantTaxonProfile } from "./taxonProfile.js";
import {
  TaxonSeedSourceType,
  TaxonSeedPolicyCheck,
  checkTaxonSeedSource,
  checkTaxonSeedCitation,
  checkTaxonSeedGermanyRelevance,
  checkTaxonSeedGermanyConsistency,
  checkTaxonSeedMorphologyPresent,
  checkTaxonSeedReviewNote,
  checkTaxonSeedAddedAt,
  checkTaxonSeedAddedAtFormat,
} from "./taxonSeedPolicy.js";

export type TaxonSeedCitation = {
  source: TaxonSeedSourceType;
  reference: string;
  page?: string;
  note?: string;
};

export type TaxonSeedEntry = {
  taxon: PlantTaxonProfile;
  citation: TaxonSeedCitation;
  germanyRelevant: boolean;
  addedAt: string;
  reviewNote: string;
  createdFromImageOnly: false;
  createsFinalIdentification: false;
};

export type TaxonSeedValidationResult = {
  valid: boolean;
  checks: TaxonSeedPolicyCheck[];
  reason: string;
};

export function hasUsableCitation(citation: TaxonSeedCitation): boolean {
  return citation.reference.trim().length > 0;
}

export function validateTaxonSeedEntry(entry: TaxonSeedEntry): TaxonSeedValidationResult {
  const checks: TaxonSeedPolicyCheck[] = [
    checkTaxonSeedSource(entry.citation.source),
    checkTaxonSeedCitation(hasUsableCitation(entry.citation)),
    checkTaxonSeedGermanyRelevance(entry.germanyRelevant),
    checkTaxonSeedGermanyConsistency(
      entry.germanyRelevant,
      entry.taxon.germanyRelevance.occursInGermany
    ),
    checkTaxonSeedMorphologyPresent(entry.taxon.morphology.length),
    checkTaxonSeedReviewNote(entry.reviewNote),
    checkTaxonSeedAddedAt(entry.addedAt),
    checkTaxonSeedAddedAtFormat(entry.addedAt),
  ];

  const valid = checks.every((c) => c.status === "allowed");

  return {
    valid,
    checks,
    reason: valid ? "taxon_seed_entry_valid" : "taxon_seed_entry_blocked_by_policy",
  };
}

export function createBlockedTaxonSeedValidationResult(reason: string): TaxonSeedValidationResult {
  return {
    valid: false,
    checks: [],
    reason,
  };
}
