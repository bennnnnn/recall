import { canToggleApplied, hasApplied } from "@/features/job-search/model/stages";

test.each(["applied", "interviewing", "offer", "rejected"] as const)(
  "%s remains part of the applied journey",
  (stage) => {
    expect(hasApplied(stage)).toBe(true);
  },
);

test("new is not applied", () => {
  expect(hasApplied("new")).toBe(false);
});

test("only new and applied can use the applied toggle", () => {
  expect(canToggleApplied("new")).toBe(true);
  expect(canToggleApplied("applied")).toBe(true);
  expect(canToggleApplied("interviewing")).toBe(false);
  expect(canToggleApplied("offer")).toBe(false);
  expect(canToggleApplied("rejected")).toBe(false);
});
