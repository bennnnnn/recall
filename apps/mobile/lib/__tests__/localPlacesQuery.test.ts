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
    expect(isProximityQuery("Best coffee shops near me")).toBe(true);
    expect(isGeoQuery("Best coffee shops near me")).toBe(true);
    expect(isPlacesListQuery("Best coffee shops near me")).toBe(true);
    expect(isPlacesListQuery("The nearest gas station")).toBe(true);
  });

  it("detects distance and directions", () => {
    expect(isDistanceQuery("how far is the airport")).toBe(true);
    expect(isDistanceQuery("driving time to work")).toBe(true);
    expect(isDistanceQuery("how long does it take to get to the airport")).toBe(
      true,
    );
    expect(isDistanceQuery("how long is the drive")).toBe(true);
    expect(isGeoQuery("how far is the airport")).toBe(true);
    expect(isPlacesListQuery("how far is the airport")).toBe(false);
  });

  it.each([
    "car doing 90km/h, how far does it go in 4 s in metres",
    "a cyclist rides at 5m/s for 2 minutes how far does she go",
    "A ball is kicked at 40° with a speed of 20m/s. how far does it go?",
    "A ball is thrown at 30° above the horizontal. how far does it go?",
    "How far is the image from the lens?",
  ])("reads %s as homework, like the server", (prompt) => {
    expect(isDistanceQuery(prompt)).toBe(false);
    expect(isGeoQuery(prompt)).toBe(false);
  });

  it.each([
    "how far is the airport",
    "how far is the stadium from here",
    "how long is the drive to work",
    "how many minutes to drive to the airport",
    "how many mins away is the mall",
    "how many minutes from here to the stadium",
    "how many minutes to Bole",
    "how many miles to the airport",
    "how many km to Adama",
  ])("still reads %s as a trip", (prompt) => {
    expect(isDistanceQuery(prompt)).toBe(true);
  });

  it.each([
    "how many minutes in a good nap",
    "how many minutes to boil an egg",
    "how many minutes should I walk a day",
    "how many minutes to the end of the movie",
    "how many miles is a 5k run?",
    "how many km in a mile",
  ])("reads %s as a duration or a length, not a trip, like the server", (prompt) => {
    expect(isDistanceQuery(prompt)).toBe(false);
    expect(isGeoQuery(prompt)).toBe(false);
  });

  it("does not treat kinematics homework as a maps distance ask", () => {
    const kinematics =
      "A car starts from rest and accelerates at a constant rate of 1.2 m/s^2. How long does it take the car to travel a distance of 500 meters?";
    expect(isDistanceQuery(kinematics)).toBe(false);
    expect(isGeoQuery(kinematics)).toBe(false);
    expect(
      isDistanceQuery("How long does it take the ball to fall 20 meters?"),
    ).toBe(false);
    expect(
      isDistanceQuery(
        "A car accelerates at 2 m/s^2. How far does it travel in 10 s?",
      ),
    ).toBe(false);
    expect(
      isDistanceQuery(
        "A 5 N force is 2 m from the pivot. How far must a 10 N force be from the pivot to balance the lever?",
      ),
    ).toBe(false);
  });

  it("detects where-am-I asks and requires geo", () => {
    expect(isLocationQuestion("Where am I right now")).toBe(true);
    expect(isLocationQuestion("where am i right nwo")).toBe(true);
    expect(isLocationQuestion("Where am iI")).toBe(true);
    expect(isGeoQuery("Where am I right now")).toBe(true);
    expect(isGeoQuery("Where am iI")).toBe(true);
    expect(isPlacesListQuery("Where am I right now")).toBe(false);
    expect(isLocationQuestion("where am I going tomorrow")).toBe(false);
  });

  it("ignores non-geographic or fixed A–B distance", () => {
    expect(isGeoQuery("explain Python decorators")).toBe(false);
    expect(isGeoQuery("distance between NYC and LA")).toBe(false);
    expect(
      isGeoQuery(
        "A circle has radius 3 and a chord of length 8. Find distance from center to chord.",
      ),
    ).toBe(false);
    expect(isGeoQuery("distance from here to the airport")).toBe(true);
    expect(isProximityQuery("find the nearest prime number")).toBe(false);
  });

  it("flags ambiguous property asks", () => {
    expect(isAmbiguousLocalPlacesQuery("Nearest house")).toBe(true);
    expect(isAmbiguousLocalPlacesQuery("nearest house for sale")).toBe(false);
    expect(isAmbiguousLocalPlacesQuery("Places near me")).toBe(false);
  });
});
