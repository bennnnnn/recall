import { countryCurrency } from "@/features/job-search/model/countryCurrency";
import { COUNTRIES } from "@/features/job-search/model/geoData";

test("each selectable country has a pay-unit default", () => {
  for (const country of COUNTRIES) expect(countryCurrency(country)).toMatch(/^[A-Z]{3}$/);
});

test.each([
  ["United States", "USD"], ["Canada", "CAD"], ["Germany", "EUR"],
  ["United Kingdom", "GBP"], ["India", "INR"], ["Japan", "JPY"],
])("uses %s's currency for numeric-only pay", (country, currency) => {
  expect(countryCurrency(country)).toBe(currency);
});

test("does not default an unknown country to USD", () => {
  expect(countryCurrency("unknown")).toBeNull();
});
