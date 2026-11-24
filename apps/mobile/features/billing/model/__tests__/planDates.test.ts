import { nextChargeDate } from "@/features/billing/model/planDates";

const day = (date: Date) => [date.getFullYear(), date.getMonth() + 1, date.getDate()];

describe("nextChargeDate", () => {
  it("is a month on for the monthly plan, kept to the month's last day", () => {
    expect(day(nextChargeDate(undefined, "monthly", new Date(2026, 10, 23)))).toEqual([2026, 12, 23]);
    expect(day(nextChargeDate(undefined, "monthly", new Date(2026, 0, 31)))).toEqual([2026, 2, 28]);
    expect(day(nextChargeDate(undefined, "monthly", new Date(2026, 11, 15)))).toEqual([2027, 1, 15]);
  });

  it("is a year on for the yearly plan", () => {
    expect(day(nextChargeDate(undefined, "yearly", new Date(2026, 10, 23)))).toEqual([2027, 11, 23]);
    expect(day(nextChargeDate(undefined, "yearly", new Date(2028, 1, 29)))).toEqual([2029, 2, 28]);
  });

  it("is the day a free trial ends", () => {
    const now = new Date(2026, 10, 23);
    expect(day(nextChargeDate({ count: 7, unit: "day", priceString: "$0.00" }, "monthly", now))).toEqual([2026, 11, 30]);
    expect(day(nextChargeDate({ count: 2, unit: "week", priceString: "$0.00" }, "monthly", now))).toEqual([2026, 12, 7]);
    expect(day(nextChargeDate({ count: 1, unit: "month", priceString: "$0.00" }, "monthly", now))).toEqual([2026, 12, 23]);
    expect(day(nextChargeDate({ count: 1, unit: "year", priceString: "$0.00" }, "monthly", now))).toEqual([2027, 11, 23]);
  });
});
