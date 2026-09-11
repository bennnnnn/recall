import { mapClosedFences, replaceFirstClosedFenceBody } from "@/lib/mdFenceScan";

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

describe("mapClosedFences", () => {
  it("does not treat a following ```math opener as the previous fence's closer", () => {
    const text = ["```math", "a", "```math", "b"].join("\n");
    const seen: string[] = [];
    const out = mapClosedFences(text, (_info, body, original) => {
      seen.push(body.trim());
      return original;
    });
    expect(seen).toEqual([]);
    expect(out).toContain("```math\na");
    expect(out).toContain("```math\nb");
  });
});
