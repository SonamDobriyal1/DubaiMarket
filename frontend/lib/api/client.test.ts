import { describe, expect, it } from "vitest";
import { ApiError, mapHasVerifiedGeometry } from "./client";
import { comparisonObservations } from "../insights";
import type { ComparisonCommunity } from "./types";

describe("map geometry", () => {
  it("stays closed when the payload says geometry is unavailable", () => {
    expect(mapHasVerifiedGeometry({ geometry_available: false, communities: [{ geometry: { type: "Point" }, latitude: 25, longitude: 55 }] })).toBe(false);
  });

  it("opens only when a verified geometry or coordinate exists", () => {
    expect(mapHasVerifiedGeometry({ geometry_available: true, communities: [{ geometry: null, latitude: null, longitude: null }] })).toBe(false);
    expect(mapHasVerifiedGeometry({ geometry_available: true, communities: [{ geometry: { type: "Polygon" }, latitude: null, longitude: null }] })).toBe(true);
    expect(mapHasVerifiedGeometry({ geometry_available: true, communities: [{ geometry: null, latitude: 25.08, longitude: 55.14 }] })).toBe(true);
  });
});

describe("comparison notes", () => {
  it("does not invent a ranking when only one community has enough sales", () => {
    const rows = [{ community_id: "a", community_name: "A", transactions: 10, insufficient_sample: true, metrics: null }] as unknown as ComparisonCommunity[];
    expect(comparisonObservations(rows)[0]).toMatch(/Fewer than two/);
  });
});

describe("api errors", () => {
  it("keeps the status used for an unsupported valuation", () => {
    const error = new ApiError(422, "unknown_or_unsupported_community", "The Gardens has 0 primary residential dwelling sales.");
    expect(error.status).toBe(422);
    expect(error.message).toMatch(/The Gardens/);
  });
});
