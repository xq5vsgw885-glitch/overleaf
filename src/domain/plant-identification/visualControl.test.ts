import { describe, it, expect } from "vitest";
import {
  createNotPerformedVisualControlResult,
  createInsufficientVisualMaterialResult,
  createVisualSupportResult,
  createVisualConflictResult,
  attachVisualControlResult,
} from "./visualControl.js";
import { IdentificationResult } from "./identificationResult.js";

const testIdentificationResult: IdentificationResult = {
  primaryCandidate: undefined,
  alternativeCandidates: [],
  resultSummary: "no_candidates_available",
  isFinalSpeciesIdentification: false,
  visualControlPending: true,
};

describe("createNotPerformedVisualControlResult", () => {
  it("returns correct not_performed result", () => {
    const result = createNotPerformedVisualControlResult();
    expect(result.status).toBe("not_performed");
    expect(result.checkedPhotoTypes).toHaveLength(0);
    expect(result.reason).toBe("visual_control_not_performed");
    expect(result.supportsCurrentIdentification).toBe(false);
    expect(result.requiresHumanReview).toBe(false);
  });
});

describe("createInsufficientVisualMaterialResult", () => {
  it("returns correct insufficient_visual_material result", () => {
    const result = createInsufficientVisualMaterialResult(["habitus", "blatt"]);
    expect(result.status).toBe("insufficient_visual_material");
    expect(result.checkedPhotoTypes).toEqual(["habitus", "blatt"]);
    expect(result.reason).toBe("insufficient_visual_material");
    expect(result.supportsCurrentIdentification).toBe(false);
    expect(result.requiresHumanReview).toBe(true);
  });
});

describe("createVisualSupportResult", () => {
  it("returns correct visual_support result", () => {
    const result = createVisualSupportResult(["bluete", "detail"]);
    expect(result.status).toBe("visual_support");
    expect(result.checkedPhotoTypes).toEqual(["bluete", "detail"]);
    expect(result.reason).toBe("visual_features_support_candidate");
    expect(result.supportsCurrentIdentification).toBe(true);
    expect(result.requiresHumanReview).toBe(false);
  });
});

describe("createVisualConflictResult", () => {
  it("returns correct visual_conflict result", () => {
    const result = createVisualConflictResult(["frucht"]);
    expect(result.status).toBe("visual_conflict");
    expect(result.checkedPhotoTypes).toEqual(["frucht"]);
    expect(result.reason).toBe("visual_features_conflict_with_candidate");
    expect(result.supportsCurrentIdentification).toBe(false);
    expect(result.requiresHumanReview).toBe(true);
  });
});

describe("attachVisualControlResult", () => {
  it("combines identification and visual control result", () => {
    const visualControl = createNotPerformedVisualControlResult();
    const result = attachVisualControlResult(testIdentificationResult, visualControl);
    expect(result.identification).toBe(testIdentificationResult);
    expect(result.visualControl.status).toBe("not_performed");
    expect(result.visualControl.reason).toBe("visual_control_not_performed");
  });

  it("visual support does not change isFinalSpeciesIdentification on identification", () => {
    const visualControl = createVisualSupportResult(["habitus"]);
    const result = attachVisualControlResult(testIdentificationResult, visualControl);
    expect(result.identification.isFinalSpeciesIdentification).toBe(false);
    expect(result.visualControl.supportsCurrentIdentification).toBe(true);
    expect(result.visualControl.status).toBe("visual_support");
  });
});
