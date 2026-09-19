import type { JobMatch } from "@/lib/api";
import {
  cacheJobMatch,
  cacheJobMatches,
  clearJobMatchCache,
  getCachedJobMatch,
} from "@/lib/jobSearch/matchCache";

function match(id: string, title = "Nurse"): JobMatch {
  return {
    id,
    title,
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
    url: "https://jobs.example.com/1",
    source: "jobs.example.com",
    status: "new",
    notes: null,
    found_at: "2026-09-18T00:00:00Z",
  };
}

afterEach(() => clearJobMatchCache());

test("caches and returns matches by id", () => {
  cacheJobMatches([match("a"), match("b")]);
  expect(getCachedJobMatch("b")?.id).toBe("b");
  expect(getCachedJobMatch("missing")).toBeNull();
});

test("single-match cache updates an existing entry", () => {
  cacheJobMatches([match("a")]);
  cacheJobMatch({ ...match("a"), status: "saved" });
  expect(getCachedJobMatch("a")?.status).toBe("saved");
});
