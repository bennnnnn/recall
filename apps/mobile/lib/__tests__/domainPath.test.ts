import { domainAccess, groupPathByDomain } from "@/lib/projects/domainPath";
import type { PathChapterProgress } from "@/lib/api";

const path: PathChapterProgress[] = [
  { title: "Hello and goodbye", domain: "Greetings", mastered: 4, total: 4, complete: true },
  { title: "Courtesy", domain: "Greetings", mastered: 4, total: 4, complete: true },
  { title: "Immediate family", domain: "Family", mastered: 1, total: 12, complete: false },
  { title: "Extended family", domain: "Family", mastered: 0, total: 12, complete: false },
  { title: "Drinks", domain: "Food", mastered: 0, total: 12, complete: false },
];

describe("domainPath", () => {
  it("rolls chapters up into domains in catalog order", () => {
    const domains = groupPathByDomain(path);
    expect(domains.map((domain) => domain.title)).toEqual(["Greetings", "Family", "Food"]);
    expect(domains[0]?.complete).toBe(true);
    expect(domains[1]?.complete).toBe(false);
    expect(domains[1]?.mastered).toBe(1);
    expect(domains[1]?.total).toBe(24);
  });

  it("locks later domains until the current domain is done", () => {
    const domains = groupPathByDomain(path);
    expect(domainAccess(domains, "Greetings", "Immediate family")).toBe("done");
    expect(domainAccess(domains, "Family", "Immediate family")).toBe("current");
    expect(domainAccess(domains, "Food", "Immediate family")).toBe("locked");
  });
});
