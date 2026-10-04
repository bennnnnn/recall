import { canToggleApplied, hasApplied } from "@/features/job-search/model/stages";

test("Applied is the only application status", () => {
  expect(hasApplied("applied")).toBe(true);
  expect(hasApplied("new")).toBe(false);
  expect(hasApplied("hidden")).toBe(false);
  expect(canToggleApplied("new")).toBe(true);
  expect(canToggleApplied("applied")).toBe(true);
  expect(canToggleApplied("hidden")).toBe(false);
});
