import { replaceFirstClosedFenceBody } from "@/lib/mdFenceScan";

describe("replaceFirstClosedFenceBody", () => {
  it("rewrites the first closed fence and keeps surrounding prose", () => {
    const text = "Intro\n```email\nTo: a@b.com\nSubject: Hi\n\nHello\n```\nOutro\n";
    const next = replaceFirstClosedFenceBody(
      text,
      "email",
      "To: b@c.com\nSubject: Bye\n\nShorter",
    );
    expect(next).toBe(
      "Intro\n```email\nTo: b@c.com\nSubject: Bye\n\nShorter\n```\nOutro\n",
    );
  });

  it("returns null when the language fence is missing", () => {
    expect(replaceFirstClosedFenceBody("plain", "email", "Hi")).toBeNull();
  });
});
