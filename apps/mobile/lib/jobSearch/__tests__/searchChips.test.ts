import type { TFunction } from "i18next";

import type { JobSearchProfile } from "@/lib/api";
import { searchProfileChips } from "@/lib/jobSearch/searchChips";

const t = ((key: string, options?: Record<string, unknown>) =>
  options ? `${key}:${JSON.stringify(options)}` : key) as TFunction;

function profile(overrides: Partial<JobSearchProfile> = {}): JobSearchProfile {
  return {
    id: "p1",
    target_roles: ["Nurse"],
    skills: [],
    location: "Berlin, Germany",
    work_modes: ["hybrid"],
    experience_levels: ["mid"],
    salary_min: 100_000,
    requires_sponsorship: null,
    excluded_companies: [],
    background: null,
    resume_attachment_id: null,
    resume_filename: null,
    result_count: 5,
    frequency: "weekly",
    next_run_at: "2026-09-19T15:00:00Z",
    status: "active",
    last_run_at: null,
    last_run_status: null,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

test("builds chips for every set field", () => {
  const chips = searchProfileChips(profile(), t);
  const byIcon = Object.fromEntries(chips.map((chip) => [chip.icon, chip.label]));
  expect(byIcon["location-outline"]).toBe("Berlin, Germany");
  expect(byIcon["laptop-outline"]).toBe("my_job.work_hybrid");
  expect(byIcon["bar-chart-outline"]).toBe("my_job.level_mid");
  expect(byIcon["cash-outline"]).toContain("my_job.salary_min_chip");
  expect(byIcon["cash-outline"]).toContain("100,000");
  expect(byIcon["briefcase-outline"]).toBe("5 my_job.count_jobs");
  expect(byIcon["repeat-outline"]).toBe("my_job.freq_weekly");
  expect(byIcon["time-outline"]).toContain("my_job.next_delivery");
});

test("omits chips for unset fields", () => {
  const chips = searchProfileChips(
    profile({ location: null, work_modes: [], experience_levels: [], salary_min: null }),
    t,
  );
  const icons = chips.map((chip) => chip.icon);
  expect(icons).not.toContain("location-outline");
  expect(icons).not.toContain("laptop-outline");
  expect(icons).not.toContain("bar-chart-outline");
  expect(icons).not.toContain("cash-outline");
  // Count and frequency always describe the search.
  expect(icons).toContain("briefcase-outline");
  expect(icons).toContain("repeat-outline");
});

test("omits the next-delivery chip when the date is invalid", () => {
  const chips = searchProfileChips(profile({ next_run_at: "not-a-date" }), t);
  expect(chips.map((chip) => chip.icon)).not.toContain("time-outline");
});

test("joins multiple work modes and levels", () => {
  const chips = searchProfileChips(
    profile({ work_modes: ["remote", "onsite"], experience_levels: ["entry", "mid"] }),
    t,
  );
  const byIcon = Object.fromEntries(chips.map((chip) => [chip.icon, chip.label]));
  expect(byIcon["laptop-outline"]).toBe("my_job.work_remote / my_job.work_onsite");
  expect(byIcon["bar-chart-outline"]).toBe("my_job.level_entry / my_job.level_mid");
});
