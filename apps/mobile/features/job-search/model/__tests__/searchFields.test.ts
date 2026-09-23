import type { TFunction } from "i18next";

import type { JobSearchProfile } from "@/lib/api";
import { searchProfileFields } from "@/features/job-search/model/searchFields";

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

test("builds a labeled field for every set profile value", () => {
  const byKey = Object.fromEntries(
    searchProfileFields(profile(), t).map((field) => [field.key, field]),
  );
  expect(byKey.location.label).toBe("my_job.location_label");
  expect(byKey.location.values).toEqual(["Berlin, Germany"]);
  expect(byKey.work_mode.label).toBe("my_job.work_mode_label");
  expect(byKey.work_mode.values).toEqual(["my_job.work_hybrid"]);
  expect(byKey.experience.values).toEqual(["my_job.level_mid"]);
  expect(byKey.salary.values[0]).toContain("my_job.salary_min_chip");
  expect(byKey.salary.values[0]).toContain("100,000");
  expect(byKey.count.values).toEqual(["5 my_job.count_jobs"]);
  expect(byKey.frequency.values).toEqual(["my_job.freq_weekly"]);
  expect(byKey.next.label).toBe("my_job.field_next_delivery");
  expect(byKey.next.values[0]).toContain("Sep 19");
});

test("omits fields whose profile value is unset", () => {
  const keys = searchProfileFields(
    profile({ location: null, work_modes: [], experience_levels: [], salary_min: null }),
    t,
  ).map((field) => field.key);
  expect(keys).not.toContain("location");
  expect(keys).not.toContain("work_mode");
  expect(keys).not.toContain("experience");
  expect(keys).not.toContain("salary");
  // Count and frequency always describe the search.
  expect(keys).toContain("count");
  expect(keys).toContain("frequency");
});

test("omits the next-delivery field when the date is invalid", () => {
  const keys = searchProfileFields(profile({ next_run_at: "not-a-date" }), t).map(
    (field) => field.key,
  );
  expect(keys).not.toContain("next");
});

test("multi-value fields produce one value chip per selection", () => {
  const byKey = Object.fromEntries(
    searchProfileFields(
      profile({ work_modes: ["remote", "onsite"], experience_levels: ["entry", "mid"] }),
      t,
    ).map((field) => [field.key, field]),
  );
  expect(byKey.work_mode.values).toEqual(["my_job.work_remote", "my_job.work_onsite"]);
  expect(byKey.experience.values).toEqual(["my_job.level_entry", "my_job.level_mid"]);
});
