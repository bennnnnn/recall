import {
  countriesIn,
  countryAt,
  formatCoordinates,
  mapView,
  parseMapFence,
} from "@/lib/map/mapFence";

describe("map fence", () => {
  it("reads the place, point and zoom", () => {
    expect(parseMapFence('{"place":"Kenya","lat":0.02,"lon":37.91,"zoom":"country"}')).toEqual({
      place: "Kenya",
      lat: 0.02,
      lon: 37.91,
      zoom: "country",
    });
    expect(parseMapFence('{"place":"Paris","latitude":"48.86","longitude":"2.35"}')).toEqual({
      place: "Paris",
      lat: 48.86,
      lon: 2.35,
      zoom: null,
    });
  });

  it.each([
    "not json",
    "[]",
    '{"lat":1,"lon":2}',
    '{"place":"","lat":1,"lon":2}',
    '{"place":"X","lat":91,"lon":2}',
    '{"place":"X","lat":1,"lon":181}',
    '{"place":"X","lat":"north","lon":2}',
  ])("refuses %s", (content) => {
    expect(parseMapFence(content)).toBeNull();
  });

  it.each([
    [0.02, 37.91, "Kenya"],
    [9.03, 38.74, "Ethiopia"],
    [48.86, 2.35, "France"],
    [-33.87, 151.21, "Australia"],
    [64.7, 177.5, "Russia"],
  ])("finds the country under %f, %f", (lat, lon, name) => {
    expect(countryAt(lat, lon)?.country.name).toBe(name);
  });

  it("finds no country in the open ocean", () => {
    expect(countryAt(-30, -140)).toBeNull();
  });

  it("frames a country around its point, twice as wide as tall", () => {
    const fence = { place: "Kenya", lat: 0.02, lon: 37.91, zoom: null };
    const view = mapView(fence, countryAt(fence.lat, fence.lon)?.polygon ?? null);
    expect(view.width / view.height).toBeCloseTo(2);
    expect(view.minX).toBeLessThan(fence.lon);
    expect(view.minX + view.width).toBeGreaterThan(fence.lon);
    expect(view.minY).toBeLessThan(-fence.lat);
    expect(view.minY + view.height).toBeGreaterThan(-fence.lat);
    expect(view.height).toBeLessThan(30);
    expect(countriesIn(view).map((c) => c.name)).toEqual(
      expect.arrayContaining(["Kenya", "Ethiopia", "Somalia"]),
    );
  });

  it("zooms a city closer than its country and shows the world when asked", () => {
    const city = mapView({ place: "Nairobi", lat: -1.29, lon: 36.82, zoom: "city" }, null);
    expect(city.height).toBe(6);
    const world = mapView({ place: "Kenya", lat: 0.02, lon: 37.91, zoom: "world" }, null);
    expect(world.width).toBe(360);
  });

  it("writes coordinates with their hemispheres", () => {
    expect(formatCoordinates(-1.29, 36.82)).toBe("1.29° S, 36.82° E");
    expect(formatCoordinates(40.71, -74.01)).toBe("40.71° N, 74.01° W");
  });
});
