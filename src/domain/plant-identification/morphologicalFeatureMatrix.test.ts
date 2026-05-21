import { describe, it, expect } from "vitest";
import {
  MORPHOLOGICAL_FEATURE_MATRIX,
  getFeaturesByGroup,
  getFeatureById,
  getHighDiagnosticFeatures,
} from "./morphologicalFeatureMatrix.js";

describe("MORPHOLOGICAL_FEATURE_MATRIX", () => {
  it("contains all 16 planned feature groups", () => {
    const groups = new Set(MORPHOLOGICAL_FEATURE_MATRIX.map((f) => f.group));
    expect(groups.has("Wuchsform")).toBe(true);
    expect(groups.has("Spross/Stängel")).toBe(true);
    expect(groups.has("Blattstellung")).toBe(true);
    expect(groups.has("Blattform")).toBe(true);
    expect(groups.has("Blattrand")).toBe(true);
    expect(groups.has("Blattnervatur")).toBe(true);
    expect(groups.has("Blattoberfläche/Behaarung")).toBe(true);
    expect(groups.has("Blüte")).toBe(true);
    expect(groups.has("Blütenfarbe")).toBe(true);
    expect(groups.has("Blütensymmetrie")).toBe(true);
    expect(groups.has("Blütenstand")).toBe(true);
    expect(groups.has("Frucht")).toBe(true);
    expect(groups.has("Samen/Ausbreitung")).toBe(true);
    expect(groups.has("Unterirdische Organe")).toBe(true);
    expect(groups.has("Standortkontext")).toBe(true);
    expect(groups.has("Phänologie")).toBe(true);
  });

  it("contains all expected central feature IDs", () => {
    const ids = new Set(MORPHOLOGICAL_FEATURE_MATRIX.map((f) => f.id));
    const expectedIds = [
      "wuchsform", "lebensform",
      "sprossform", "sprossoberflaeche", "milchsaft",
      "blattstellung",
      "blattform", "blattgliederung",
      "blattrand",
      "nervatur",
      "blattoberflaeche", "behaarung",
      "bluetentyp", "bluetengroesse",
      "bluetenfarbe",
      "bluetensymmetrie",
      "bluetenstand",
      "fruchttyp",
      "ausbreitungseinheit",
      "unterirdisches_organ",
      "standorttyp", "feuchte", "licht",
      "bluetezeit", "fruchtzeit",
    ];
    for (const id of expectedIds) {
      expect(ids.has(id), `expected feature id "${id}" to be present`).toBe(true);
    }
  });

  it("has unique feature IDs", () => {
    const ids = MORPHOLOGICAL_FEATURE_MATRIX.map((f) => f.id);
    const uniqueIds = new Set(ids);
    expect(ids.length).toBe(uniqueIds.size);
  });

  it("has all required fields on every feature", () => {
    const validWeights = ["niedrig", "mittel", "hoch", "sehr_hoch"];
    const validVisibility = ["true", "bedingt", "false"];

    for (const feature of MORPHOLOGICAL_FEATURE_MATRIX) {
      expect(typeof feature.id).toBe("string");
      expect(feature.id.length).toBeGreaterThan(0);

      expect(typeof feature.group).toBe("string");
      expect(feature.group.length).toBeGreaterThan(0);

      expect(typeof feature.name).toBe("string");
      expect(feature.name.length).toBeGreaterThan(0);

      expect(Array.isArray(feature.possibleValues)).toBe(true);
      expect(feature.possibleValues.length).toBeGreaterThan(0);

      expect(validWeights).toContain(feature.diagnosticWeight);

      expect(validVisibility).toContain(feature.photoVisibility);

      expect(Array.isArray(feature.requiredPhotoTypes)).toBe(true);

      expect(typeof feature.userExplanation).toBe("string");
      expect(feature.userExplanation.length).toBeGreaterThan(0);
    }
  });

  it("no possibleValue entry is empty", () => {
    for (const feature of MORPHOLOGICAL_FEATURE_MATRIX) {
      for (const value of feature.possibleValues) {
        expect(typeof value).toBe("string");
        expect(value.length).toBeGreaterThan(0);
      }
    }
  });
});

describe("getFeaturesByGroup", () => {
  it("returns exactly the features for Standortkontext", () => {
    const result = getFeaturesByGroup("Standortkontext");
    const ids = result.map((f) => f.id);
    expect(ids).toContain("standorttyp");
    expect(ids).toContain("feuchte");
    expect(ids).toContain("licht");
    expect(result).toHaveLength(3);
  });

  it("returns empty array for unknown group", () => {
    expect(getFeaturesByGroup("Unbekannte Gruppe")).toEqual([]);
  });
});

describe("getFeatureById", () => {
  it("finds blattstellung and returns correct fields", () => {
    const feature = getFeatureById("blattstellung");
    expect(feature).toBeDefined();
    expect(feature!.id).toBe("blattstellung");
    expect(feature!.group).toBe("Blattstellung");
  });

  it("returns undefined for unknown ID", () => {
    expect(getFeatureById("unbekanntes_merkmal")).toBeUndefined();
  });
});

describe("getHighDiagnosticFeatures", () => {
  it("returns only features with diagnosticWeight hoch or sehr_hoch", () => {
    const result = getHighDiagnosticFeatures();
    for (const feature of result) {
      expect(["hoch", "sehr_hoch"]).toContain(feature.diagnosticWeight);
    }
  });

  it("contains key strongly diagnostic feature IDs", () => {
    const ids = getHighDiagnosticFeatures().map((f) => f.id);
    expect(ids).toContain("blattstellung");
    expect(ids).toContain("bluetentyp");
    expect(ids).toContain("bluetenstand");
    expect(ids).toContain("unterirdisches_organ");
  });
});
