import { describe, it, expect } from "vitest";
import {
  PLANT_TAXON_SEED_DATA,
  getValidatedTaxonSeedData,
  getTaxonSeedDataCount,
  hasTaxonSeedData,
} from "./taxonSeedData.js";

describe("PLANT_TAXON_SEED_DATA", () => {
  it("is an empty array", () => {
    expect(Array.isArray(PLANT_TAXON_SEED_DATA)).toBe(true);
    expect(PLANT_TAXON_SEED_DATA.length).toBe(0);
  });
});

describe("getValidatedTaxonSeedData", () => {
  it("returns an empty array", () => {
    expect(Array.isArray(getValidatedTaxonSeedData())).toBe(true);
    expect(getValidatedTaxonSeedData().length).toBe(0);
  });
});

describe("getTaxonSeedDataCount", () => {
  it("returns 0", () => {
    expect(getTaxonSeedDataCount()).toBe(0);
  });
});

describe("hasTaxonSeedData", () => {
  it("returns false", () => {
    expect(hasTaxonSeedData()).toBe(false);
  });
});

describe("methodische Sicherung: keine Seed-Daten vorhanden", () => {
  it("confirms no seed data exists", () => {
    expect(PLANT_TAXON_SEED_DATA.length).toBe(0);
    expect(getValidatedTaxonSeedData().length).toBe(0);
    expect(getTaxonSeedDataCount()).toBe(0);
    expect(hasTaxonSeedData()).toBe(false);
  });
});
