import { chapterAccess, sectionPath } from "@/lib/projects/chapterAccess";

describe("chapterAccess", () => {
  it("marks complete chapters done, the up-next chapter current, and the rest locked", () => {
    expect(chapterAccess({ title: "Hello", mastered: 4, total: 5, complete: true }, "School")).toBe(
      "done",
    );
    expect(chapterAccess({ title: "School", mastered: 0, total: 2, complete: false }, "School")).toBe(
      "current",
    );
    expect(chapterAccess({ title: "Food", mastered: 0, total: 0, complete: false }, "School")).toBe(
      "locked",
    );
  });
});

describe("sectionPath", () => {
  it("encodes the chapter title in the route", () => {
    expect(sectionPath("proj-1", "School 1")).toBe("/projects/proj-1/section/School%201");
  });
});
