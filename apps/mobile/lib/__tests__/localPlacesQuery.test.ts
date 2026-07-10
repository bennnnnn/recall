import {
  isAmbiguousLocalPlacesQuery,
  isDistanceQuery,
  isGeoQuery,
  isLocationQuestion,
  isPlacesListQuery,
  isProximityQuery,
} from "@/lib/localPlacesQuery";

describe("geo intent", () => {
  it("detects proximity for any category", () => {
    expect(isProximityQuery("The nearest gas station")).toBe(true);
    expect(isProximityQuery("nearest hospital")).toBe(true);
    expect(isProximityQuery("closest casino")).toBe(true);
    expect(isPlacesListQuery("The nearest gas station")).toBe(true);
  });

  it("detects distance and directions", () => {
    expect(isDistanceQuery("how far is the airport")).toBe(true);
    expect(isDistanceQuery("driving time to work")).toBe(true);
    expect(isGeoQuery("how far is the airport")).toBe(true);
    expect(isPlacesListQuery("how far is the airport")).toBe(false);
  });

  it("detects where-am-I asks and requires geo", () => {
    expect(isLocationQuestion("Where am I right now")).toBe(true);
    expect(isLocationQuestion("where am i right nwo")).toBe(true);
    expect(isGeoQuery("Where am I right now")).toBe(true);
    expect(isPlacesListQuery("Where am I right now")).toBe(false);
    expect(isLocationQuestion("where am I going tomorrow")).toBe(false);
  });

  it("ignores non-geographic or fixed A–B distance", () => {
    expect(isGeoQuery("explain Python decorators")).toBe(false);
    expect(isGeoQuery("distance between NYC and LA")).toBe(false);
    expect(isProximityQuery("find the nearest prime number")).toBe(false);
  });

  it("flags ambiguous property asks", () => {
    expect(isAmbiguousLocalPlacesQuery("Nearest house")).toBe(true);
    expect(isAmbiguousLocalPlacesQuery("nearest house for sale")).toBe(false);
    expect(isAmbiguousLocalPlacesQuery("Places near me")).toBe(false);
  });
});
