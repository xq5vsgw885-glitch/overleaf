import { TaxonFeatureProfile } from "./featureScoring.js";

export type TaxonomicRank = "familie" | "gattung" | "art";

export type FloristicStatus =
  | "wildwachsend"
  | "etablierter_neophyt"
  | "haeufig_verwildernd"
  | "kulturpflanze_nachrangig";

export type GermanyRelevance = {
  occursInGermany: boolean;
  floristicStatus: FloristicStatus;
  statusWeight: number;
};

export type TaxonomicIdentity = {
  taxonId: string;
  scientificName: string;
  germanName?: string;
  family?: string;
  genus?: string;
  species?: string;
  rank: TaxonomicRank;
};

export type EcologyProfile = {
  habitatTypes: string[];
  moisture: string[];
  light: string[];
  notes?: string;
};

export type PhenologyProfile = {
  floweringMonths: string[];
  fruitingMonths: string[];
};

export type VisualReferenceProfile = {
  habitusImages: string[];
  leafImages: string[];
  flowerImages: string[];
  fruitImages: string[];
  detailImages: string[];
};

export type PlantTaxonProfile = {
  identity: TaxonomicIdentity;
  germanyRelevance: GermanyRelevance;
  morphology: TaxonFeatureProfile[];
  ecology: EcologyProfile;
  phenology: PhenologyProfile;
  visualReferences?: VisualReferenceProfile;
};
