import {
  TaxonSeedEntry,
  TaxonSeedValidationResult,
  validateTaxonSeedEntry,
} from "./taxonSeedSchema.js";

export const PLANT_TAXON_SEED_DATA: TaxonSeedEntry[] = [];

export function getValidatedTaxonSeedData(): TaxonSeedValidationResult[] {
  return PLANT_TAXON_SEED_DATA.map((entry) => validateTaxonSeedEntry(entry));
}

export function getTaxonSeedDataCount(): number {
  return PLANT_TAXON_SEED_DATA.length;
}

export function hasTaxonSeedData(): boolean {
  return PLANT_TAXON_SEED_DATA.length > 0;
}
