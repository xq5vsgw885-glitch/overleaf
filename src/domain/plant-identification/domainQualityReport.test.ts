import { describe, it, expect } from "vitest";
import { PLANT_IDENTIFICATION_DOMAIN_QUALITY_REPORT } from "./domainQualityReport.js";

const report = PLANT_IDENTIFICATION_DOMAIN_QUALITY_REPORT;

describe("PLANT_IDENTIFICATION_DOMAIN_QUALITY_REPORT", () => {
  it("has correct basic status fields", () => {
    expect(report.domain).toBe("plant-identification");
    expect(report.scope).toBe("Deutschland");
    expect(report.primaryMethod).toBe("merkmalsbasiert");
    expect(report.visualControlRole).toBe("abschließender_kontrollschritt");
    expect(report.testFramework).toBe("vitest");
    expect(report.passingUnitTests).toBe(114);
  });

  it("enforces methodical safety constraints", () => {
    expect(report.finalSpeciesIdentificationImplemented).toBe(false);
    expect(report.imageAnalysisImplemented).toBe(false);
    expect(report.realTaxaImplemented).toBe(false);
  });

  it("documents exactly 9 domain modules", () => {
    expect(report.modules).toHaveLength(9);
  });

  it("marks all modules as implemented", () => {
    expect(report.modules.every((m) => m.implemented === true)).toBe(true);
  });

  it("confirms no module creates a final species identification", () => {
    expect(report.modules.every((m) => m.createsFinalIdentification === false)).toBe(true);
  });

  it("confirms no module performs image analysis", () => {
    expect(report.modules.every((m) => m.performsImageAnalysis === false)).toBe(true);
  });

  it("confirms no module uses real taxa", () => {
    expect(report.modules.every((m) => m.usesRealTaxa === false)).toBe(true);
  });

  it("documents correct unit test coverage per module", () => {
    const byName = Object.fromEntries(report.modules.map((m) => [m.moduleName, m]));

    expect(byName["morphologicalFeatureMatrix"].hasUnitTests).toBe(false);
    expect(byName["taxonProfile"].hasUnitTests).toBe(false);
    expect(byName["featureScoring"].hasUnitTests).toBe(true);
    expect(byName["taxonComparison"].hasUnitTests).toBe(true);
    expect(byName["plausibilityScoring"].hasUnitTests).toBe(true);
    expect(byName["combinedAssessment"].hasUnitTests).toBe(true);
    expect(byName["identificationResult"].hasUnitTests).toBe(true);
    expect(byName["visualControl"].hasUnitTests).toBe(true);
    expect(byName["identificationPipeline"].hasUnitTests).toBe(true);
  });

  it("contains all expected module names", () => {
    const names = report.modules.map((m) => m.moduleName);
    expect(names).toContain("morphologicalFeatureMatrix");
    expect(names).toContain("featureScoring");
    expect(names).toContain("taxonProfile");
    expect(names).toContain("taxonComparison");
    expect(names).toContain("plausibilityScoring");
    expect(names).toContain("combinedAssessment");
    expect(names).toContain("identificationResult");
    expect(names).toContain("visualControl");
    expect(names).toContain("identificationPipeline");
  });

  it("documents all expected open next steps", () => {
    expect(report.openNextSteps).toContain(
      "README.md mit DomainQualityReport aktualisieren"
    );
    expect(report.openNextSteps).toContain(
      "Unit-Tests für domainQualityReport.ts ergänzen"
    );
    expect(report.openNextSteps).toContain(
      "Spätere Taxon-Datenbank fachlich kontrolliert aufbauen"
    );
    expect(report.openNextSteps).toContain(
      "Visuellen Kontrollschritt erst nach stabiler merkmalsbasierter Pipeline implementieren"
    );
    expect(report.openNextSteps).toContain(
      "Keine finale sichere Artbestimmung ohne konsistente Morphologie, Taxonomie, Deutschland-Plausibilität und visuellen Kontrollschritt"
    );
  });
});
