import { IdentificationResult } from "./identificationResult.js";
import { PlantTaxonProfile } from "./taxonProfile.js";

export type VisualControlPhotoType =
  | "habitus"
  | "blatt"
  | "bluete"
  | "frucht"
  | "detail"
  | "standort";

export type VisualControlInput = {
  photoType: VisualControlPhotoType;
  imageUri: string;
  quality: "niedrig" | "mittel" | "hoch";
  notes?: string;
};

export type VisualControlReference = {
  taxon: PlantTaxonProfile;
  referenceImageUris: string[];
  photoTypes: VisualControlPhotoType[];
};

export type VisualControlStatus =
  | "not_performed"
  | "insufficient_visual_material"
  | "visual_support"
  | "visual_conflict"
  | "visual_review_required";

export type VisualControlResult = {
  status: VisualControlStatus;
  checkedPhotoTypes: VisualControlPhotoType[];
  reason: string;
  supportsCurrentIdentification: boolean;
  requiresHumanReview: boolean;
};

export type IdentificationResultWithVisualControl = {
  identification: IdentificationResult;
  visualControl: VisualControlResult;
};

export function createNotPerformedVisualControlResult(): VisualControlResult {
  return {
    status: "not_performed",
    checkedPhotoTypes: [],
    reason: "visual_control_not_performed",
    supportsCurrentIdentification: false,
    requiresHumanReview: false,
  };
}

export function createInsufficientVisualMaterialResult(
  checkedPhotoTypes: VisualControlPhotoType[]
): VisualControlResult {
  return {
    status: "insufficient_visual_material",
    checkedPhotoTypes,
    reason: "insufficient_visual_material",
    supportsCurrentIdentification: false,
    requiresHumanReview: true,
  };
}

export function createVisualSupportResult(
  checkedPhotoTypes: VisualControlPhotoType[]
): VisualControlResult {
  return {
    status: "visual_support",
    checkedPhotoTypes,
    reason: "visual_features_support_candidate",
    supportsCurrentIdentification: true,
    requiresHumanReview: false,
  };
}

export function createVisualConflictResult(
  checkedPhotoTypes: VisualControlPhotoType[]
): VisualControlResult {
  return {
    status: "visual_conflict",
    checkedPhotoTypes,
    reason: "visual_features_conflict_with_candidate",
    supportsCurrentIdentification: false,
    requiresHumanReview: true,
  };
}

export function attachVisualControlResult(
  identification: IdentificationResult,
  visualControl: VisualControlResult
): IdentificationResultWithVisualControl {
  return { identification, visualControl };
}
