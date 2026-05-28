export type DomainModuleStatus = {
  moduleName: string;
  purpose: string;
  implemented: boolean;
  hasUnitTests: boolean;
  createsFinalIdentification: boolean;
  performsImageAnalysis: boolean;
  usesRealTaxa: boolean;
};

export type DomainQualityReport = {
  domain: "plant-identification";
  scope: "Deutschland";
  primaryMethod: "merkmalsbasiert";
  visualControlRole: "abschließender_kontrollschritt";
  finalSpeciesIdentificationImplemented: false;
  imageAnalysisImplemented: false;
  realTaxaImplemented: false;
  testFramework: "vitest";
  passingUnitTests: number;
  modules: DomainModuleStatus[];
  openNextSteps: string[];
};

export const PLANT_IDENTIFICATION_DOMAIN_QUALITY_REPORT: DomainQualityReport = {
  domain: "plant-identification",
  scope: "Deutschland",
  primaryMethod: "merkmalsbasiert",
  visualControlRole: "abschließender_kontrollschritt",
  finalSpeciesIdentificationImplemented: false,
  imageAnalysisImplemented: false,
  realTaxaImplemented: false,
  testFramework: "vitest",
  passingUnitTests: 186,
  modules: [
    {
      moduleName: "morphologicalFeatureMatrix",
      purpose: "Vollständige morphologische Merkmalsmatrix mit 16 Merkmalsgruppen",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "featureScoring",
      purpose: "Generischer Vergleich einzelner Merkmale und Merkmalssets",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "taxonProfile",
      purpose: "Schema für spätere Familien-, Gattungs- und Artprofile",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "taxonComparison",
      purpose: "Morphologischer Vergleich beobachteter Merkmale mit einem Taxonprofil",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "plausibilityScoring",
      purpose: "Deutschland-, Status-, Standort- und Phänologie-Plausibilitätsprüfung",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "combinedAssessment",
      purpose: "Kombinierte Bewertung aus Morphologie und Plausibilität",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "identificationResult",
      purpose: "Strukturierte Ergebnisdarstellung mit expliziter Unsicherheit",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "visualControl",
      purpose: "Schema für späteren visuellen Kontrollschritt ohne Bildanalyse",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "identificationPipeline",
      purpose: "Technische Klammerung der merkmalsbasierten Pipeline",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "taxonSeedPolicy",
      purpose: "Regelwerk für quellenbasierte Taxon-Seed-Daten inkl. checkTaxonSeedMorphologyPresent und checkTaxonSeedReviewNote (Audit-Metadaten)",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "taxonSeedSchema",
      purpose: "Schema mit Pflichtfeldern addedAt/reviewNote; validateTaxonSeedEntry führt 6 Checks durch inkl. Morphologie- und Review-Pflichtprüfung",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
    {
      moduleName: "taxonSeedData",
      purpose: "Leere technische Seed-Daten-Struktur für spätere validierte Taxon-Seed-Einträge",
      implemented: true,
      hasUnitTests: true,
      createsFinalIdentification: false,
      performsImageAnalysis: false,
      usesRealTaxa: false,
    },
  ],
  openNextSteps: [
    "domainQualityReport.test.ts nach Phase 2.3 auf 186 Tests synchronisieren",
    "README.md nach Phase 2.3 (Audit-Metadaten) synchronisieren",
    "HANDOFF.md auf 186 Tests und Audit-Metadaten aktualisieren",
    "Entscheidung über Aufbau erster fachlich kontrollierter Taxon-Seed-Daten treffen",
    "Taxon-Seed-Daten nur quellenbasiert und schrittweise ergänzen",
    "Taxon-Seed-Daten nur nach taxonSeedPolicy, taxonSeedSchema und taxonSeedData ergänzen",
    "Keine finale sichere Artbestimmung ohne konsistente Morphologie, Taxonomie, Deutschland-Plausibilität und visuellen Kontrollschritt",
  ],
};
