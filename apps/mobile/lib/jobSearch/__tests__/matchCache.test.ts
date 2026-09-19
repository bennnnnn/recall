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
  cacheJobMatches("account-a", [match("a"), match("b")]);
  expect(getCachedJobMatch("account-a", "b")?.id).toBe("b");
  expect(getCachedJobMatch("account-a", "missing")).toBeNull();
});

test("single-match cache updates an existing entry", () => {
  cacheJobMatches("account-a", [match("a")]);
  cacheJobMatch("account-a", { ...match("a"), status: "saved" });
  expect(getCachedJobMatch("account-a", "a")?.status).toBe("saved");
});

test("keeps cached matches isolated by account", () => {
  cacheJobMatches("account-a", [match("a")]);
  expect(getCachedJobMatch("account-b", "a")).toBeNull();
});
