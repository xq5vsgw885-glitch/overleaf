import { describe, it, expect } from "vitest";
import {
  TaxonomicRank,
  FloristicStatus,
  GermanyRelevance,
  TaxonomicIdentity,
  EcologyProfile,
  PhenologyProfile,
  VisualReferenceProfile,
  PlantTaxonProfile,
} from "./taxonProfile.js";

describe("TaxonomicRank", () => {
  it("accepts all predefined rank values", () => {
    const ranks: TaxonomicRank[] = ["familie", "gattung", "art"];
    expect(ranks).toContain("familie");
    expect(ranks).toContain("gattung");
    expect(ranks).toContain("art");
    expect(ranks).toHaveLength(3);
  });
});

describe("FloristicStatus", () => {
  it("accepts all predefined status values", () => {
    const statuses: FloristicStatus[] = [
      "wildwachsend",
      "etablierter_neophyt",
      "haeufig_verwildernd",
      "kulturpflanze_nachrangig",
    ];
    expect(statuses).toContain("wildwachsend");
    expect(statuses).toContain("etablierter_neophyt");
    expect(statuses).toContain("haeufig_verwildernd");
    expect(statuses).toContain("kulturpflanze_nachrangig");
    expect(statuses).toHaveLength(4);
  });
});

describe("GermanyRelevance", () => {
  it("accepts a typkonform structure", () => {
    const germanyRelevance: GermanyRelevance = {
      occursInGermany: true,
      floristicStatus: "wildwachsend",
      statusWeight: 1,
    };
    expect(germanyRelevance.occursInGermany).toBe(true);
    expect(germanyRelevance.floristicStatus).toBe("wildwachsend");
    expect(germanyRelevance.statusWeight).toBe(1);
  });
});

describe("TaxonomicIdentity", () => {
  it("accepts a typkonform structure", () => {
    const identity: TaxonomicIdentity = {
      taxonId: "test-taxon-1",
      scientificName: "Test taxon",
      germanName: "Testpflanze",
      family: "Testaceae",
      genus: "Testgenus",
      species: "testensis",
      rank: "art",
    };
    expect(identity.taxonId).toBe("test-taxon-1");
    expect(identity.scientificName).toBe("Test taxon");
    expect(identity.rank).toBe("art");
  });
});

describe("EcologyProfile", () => {
  it("accepts a typkonform structure", () => {
    const ecology: EcologyProfile = {
      habitatTypes: ["wiese", "waldrand"],
      moisture: ["frisch", "feucht"],
      light: ["vollsonnig", "halbschattig"],
      notes: "Künstliches Testprofil",
    };
    expect(ecology.habitatTypes).toContain("wiese");
    expect(ecology.moisture).toContain("frisch");
    expect(ecology.light).toContain("vollsonnig");
    expect(ecology.notes).toBe("Künstliches Testprofil");
  });
});

describe("PhenologyProfile", () => {
  it("accepts a typkonform structure", () => {
    const phenology: PhenologyProfile = {
      floweringMonths: ["mai", "juni"],
      fruitingMonths: ["juli", "august"],
    };
    expect(phenology.floweringMonths).toContain("mai");
    expect(phenology.fruitingMonths).toContain("juli");
  });
});

describe("VisualReferenceProfile", () => {
  it("accepts a typkonform structure with empty arrays", () => {
    const visualReferences: VisualReferenceProfile = {
      habitusImages: [],
      leafImages: [],
      flowerImages: [],
      fruitImages: [],
      detailImages: [],
    };
    expect(Array.isArray(visualReferences.habitusImages)).toBe(true);
    expect(Array.isArray(visualReferences.leafImages)).toBe(true);
    expect(Array.isArray(visualReferences.flowerImages)).toBe(true);
    expect(Array.isArray(visualReferences.fruitImages)).toBe(true);
    expect(Array.isArray(visualReferences.detailImages)).toBe(true);
    expect(visualReferences.habitusImages).toHaveLength(0);
    expect(visualReferences.leafImages).toHaveLength(0);
    expect(visualReferences.flowerImages).toHaveLength(0);
    expect(visualReferences.fruitImages).toHaveLength(0);
    expect(visualReferences.detailImages).toHaveLength(0);
  });
});

describe("PlantTaxonProfile", () => {
  it("accepts a complete typkonform structure", () => {
    const testProfile: PlantTaxonProfile = {
      identity: {
        taxonId: "test-taxon-1",
        scientificName: "Test taxon",
        germanName: "Testpflanze",
        family: "Testaceae",
        genus: "Testgenus",
        species: "testensis",
        rank: "art",
      },
      germanyRelevance: {
        occursInGermany: true,
        floristicStatus: "wildwachsend",
        statusWeight: 1,
      },
      morphology: [
        {
          featureId: "blattstellung",
          acceptedValues: ["gegenständig"],
          requiredForStrongIdentification: true,
        },
      ],
      ecology: {
        habitatTypes: ["wiese"],
        moisture: ["frisch"],
        light: ["vollsonnig"],
      },
      phenology: {
        floweringMonths: ["mai"],
        fruitingMonths: ["juni"],
      },
      visualReferences: {
        habitusImages: [],
        leafImages: [],
        flowerImages: [],
        fruitImages: [],
        detailImages: [],
      },
    };

    expect(testProfile.identity.taxonId).toBe("test-taxon-1");
    expect(testProfile.identity.rank).toBe("art");
    expect(testProfile.germanyRelevance.occursInGermany).toBe(true);
    expect(testProfile.morphology).toHaveLength(1);
    expect(testProfile.morphology[0].featureId).toBe("blattstellung");
    expect(testProfile.ecology.habitatTypes).toContain("wiese");
    expect(testProfile.phenology.floweringMonths).toContain("mai");
    expect(testProfile.visualReferences).toBeDefined();
  });

  it("allows optional visualReferences to be absent", () => {
    const testProfile: PlantTaxonProfile = {
      identity: {
        taxonId: "test-taxon-2",
        scientificName: "Test taxon 2",
        rank: "gattung",
      },
      germanyRelevance: {
        occursInGermany: true,
        floristicStatus: "etablierter_neophyt",
        statusWeight: 0.8,
      },
      morphology: [],
      ecology: {
        habitatTypes: [],
        moisture: [],
        light: [],
      },
      phenology: {
        floweringMonths: [],
        fruitingMonths: [],
      },
    };

    expect(testProfile.visualReferences).toBeUndefined();
    expect(testProfile.identity.taxonId).toBe("test-taxon-2");
    expect(testProfile.germanyRelevance.occursInGermany).toBe(true);
  });

  it("can represent Familien- and Gattungsrang profiles", () => {
    const familyProfile: PlantTaxonProfile = {
      identity: {
        taxonId: "test-family-1",
        scientificName: "Testaceae",
        rank: "familie",
      },
      germanyRelevance: {
        occursInGermany: true,
        floristicStatus: "wildwachsend",
        statusWeight: 1,
      },
      morphology: [],
      ecology: { habitatTypes: [], moisture: [], light: [] },
      phenology: { floweringMonths: [], fruitingMonths: [] },
    };

    const genusProfile: PlantTaxonProfile = {
      identity: {
        taxonId: "test-genus-1",
        scientificName: "Testgenus",
        rank: "gattung",
      },
      germanyRelevance: {
        occursInGermany: true,
        floristicStatus: "wildwachsend",
        statusWeight: 1,
      },
      morphology: [],
      ecology: { habitatTypes: [], moisture: [], light: [] },
      phenology: { floweringMonths: [], fruitingMonths: [] },
    };

    expect(familyProfile.identity.rank).toBe("familie");
    expect(genusProfile.identity.rank).toBe("gattung");
  });
});
