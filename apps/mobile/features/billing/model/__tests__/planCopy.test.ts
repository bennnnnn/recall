import { yearlySaving } from "@/features/billing/model/planCopy";

describe("yearlySaving", () => {
  it.each([
    // An exact 20%: 1 − 0.8 is 0.19999… in floating point, and still says 20.
    [10, 96, 20],
    [5, 48, 20],
    // 59.99 against 95.88: 37.4%, rounded down, never up.
    [7.99, 59.99, 37],
  ])("monthly %s, yearly %s saves %s%%", (monthly, yearly, percent) => {
    expect(yearlySaving({ monthly: { price: monthly }, yearly: { price: yearly } })).toBe(percent);
  });

  it("says no saving when the year costs as much as twelve months, or a price is missing", () => {
    expect(yearlySaving({ monthly: { price: 5 }, yearly: { price: 60 } })).toBeNull();
    expect(yearlySaving({ monthly: { price: 5 } })).toBeNull();
  });
});
