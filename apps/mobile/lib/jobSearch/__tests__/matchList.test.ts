import type { JobMatch } from "@/lib/api";
import { filterAndSortMatches } from "@/lib/jobSearch/matchList";

function match(
  id: string,
  overrides: Partial<JobMatch> = {},
): JobMatch {
  return {
    id,
    title: `Job ${id}`,
    company: "Acme",
    location: null,
    work_mode: null,
    salary: null,
    experience: null,
    match_score: null,
    posted_at: null,
    summary: null,
    match_reasons: [],
    gap: null,
    url: `https://jobs.example.com/${id}`,
    source: "jobs.example.com",
    status: "new",
    notes: null,
    found_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

const matches = [
  match("a", { match_score: 50, found_at: "2026-09-03T00:00:00Z" }),
  match("b", { match_score: 90, found_at: "2026-09-01T00:00:00Z" }),
  match("c", { status: "saved", found_at: "2026-09-05T00:00:00Z" }),
  match("d", { status: "hidden", match_score: 99 }),
  match("e", { status: "applied", match_score: 70, found_at: "2026-09-04T00:00:00Z" }),
];

test("all filter excludes hidden but keeps every other status", () => {
  const ids = filterAndSortMatches(matches, "all", "newest").map((m) => m.id);
  expect(ids).toEqual(["c", "e", "a", "b"]);
});

test("status filters keep only that status", () => {
  expect(filterAndSortMatches(matches, "new", "best").map((m) => m.id)).toEqual(["b", "a"]);
  expect(filterAndSortMatches(matches, "saved", "best").map((m) => m.id)).toEqual(["c"]);
  expect(filterAndSortMatches(matches, "applied", "best").map((m) => m.id)).toEqual(["e"]);
});

test("best sort orders by score, unknown scores last, ties newest first", () => {
  const withTie = [
    match("x", { match_score: 80, found_at: "2026-09-01T00:00:00Z" }),
    match("y", { match_score: 80, found_at: "2026-09-06T00:00:00Z" }),
    match("z"),
  ];
  const ids = filterAndSortMatches(withTie, "all", "best").map((m) => m.id);
  expect(ids).toEqual(["y", "x", "z"]);
});

test("newest sort ignores score", () => {
  const ids = filterAndSortMatches(matches, "all", "newest").map((m) => m.id);
  expect(ids[0]).toBe("c");
});
