import type { ProjectDetail } from "@/lib/api";
import { projectHasExportableItems } from "@/lib/exportProjectPdf";

function baseDetail(overrides: Partial<ProjectDetail> = {}): ProjectDetail {
  return {
    id: "proj-1",
    title: "Words",
    description: "",
    kind: "language",
    target_language: "en",
    native_language: null,
    level: "level1",
    daily_goal: 5,
    archived: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    mastered_count: 0,
    total_count: 0,
    stats: {
      total: 0,
      new_count: 0,
      learning_count: 0,
      mastered_count: 0,
      added_this_week: 0,
      due_for_review: 0,
      mastered_today: 0,
      pending_today: 0,
      last_mastery_at: null,
    },
    daily_history: [],
    daily_items_by_date: {},
    lists: [],
    ...overrides,
  };
}

describe("projectHasExportableItems", () => {
  it("uses total_count when lists are omitted (slim detail)", () => {
    expect(projectHasExportableItems(baseDetail({ total_count: 36, lists: [] }))).toBe(true);
  });

  it("uses stats.total when lists are empty", () => {
    expect(
      projectHasExportableItems(
        baseDetail({
          total_count: 0,
          stats: {
            total: 1,
            new_count: 1,
            learning_count: 0,
            mastered_count: 0,
            added_this_week: 0,
            due_for_review: 0,
            mastered_today: 0,
            pending_today: 0,
            last_mastery_at: null,
          },
          lists: [],
        }),
      ),
    ).toBe(true);
  });

  it("returns false when empty", () => {
    expect(projectHasExportableItems(baseDetail())).toBe(false);
  });
});
